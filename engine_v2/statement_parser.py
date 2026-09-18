from __future__ import annotations

import hashlib
import io
import re
from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any, Iterable

import pdfplumber
from pydantic import BaseModel, Field

from .bank_profiles import detect_bank_profile
from .coverage import calculate_statement_coverage
from .extraction_quality import ExtractionQuality, assess_extraction_quality
from .identifiers import stable_statement_id, stable_transaction_id
from .mca import McaDebit, build_mca_debit
from .models import CoverageStatus, StatementCoverage, TransactionDirection, TransactionRecord
from .pdf_integrity import PdfIntegrityReport, analyze_pdf_integrity
from .period import extract_statement_period
from .reconciliation import reconcile_statement
from .statement_integrity import (
    StatementIntegrityAssessment,
    assess_statement_integrity,
)
from .vision_ledger import (
    extract_page_ledger_with_vision,
    render_pdf_page_png,
)


class ParsedStatement(BaseModel):
    statement_id: str
    source_file: str
    file_sha256: str
    page_count: int = 0
    bank_id: str | None = None
    bank_name: str | None = None
    extraction_quality: ExtractionQuality | None = None
    period_start: date | None = None
    period_end: date | None = None
    coverage: StatementCoverage | None = None
    integrity: PdfIntegrityReport | None = None
    composite_integrity: StatementIntegrityAssessment | None = None
    opening_balance: Decimal | None = None
    closing_balance: Decimal | None = None
    credit_anchor: Decimal | None = None
    credit_anchor_method: str | None = None
    transactions: list[TransactionRecord] = Field(default_factory=list)
    mca_debits: list[McaDebit] = Field(default_factory=list)
    reconciliation_status: str | None = None
    reconciliation_variance: Decimal | None = None
    diagnostics: list[str] = Field(default_factory=list)


MONTH_NUMBERS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}


def parse_money_token(value: object) -> Decimal | None:
    if value is None:
        return None

    raw = str(value).strip().replace("$", "").replace(" ", "")
    if not raw:
        return None

    negative = raw.startswith("(") and raw.endswith(")")
    raw = raw.strip("()")

    if "," in raw and "." in raw:
        if raw.rfind(",") > raw.rfind("."):
            raw = raw.replace(".", "").replace(",", ".")
        else:
            raw = raw.replace(",", "")
    elif "," in raw:
        tail = raw.rsplit(",", 1)[-1]
        if len(tail) == 2:
            raw = raw.replace(".", "").replace(",", ".")
        else:
            raw = raw.replace(",", "")

    try:
        amount = Decimal(raw)
    except Exception:
        return None

    return -amount if negative else amount


def money_from_words(words: Iterable[str]) -> Decimal | None:
    joined = "".join(str(word) for word in words).replace("$", "").replace(" ", "")
    if not joined:
        return None

    matches = re.findall(r"-?\(?\d[\d,]*\.\d{2}\)?", joined)
    if matches:
        value = parse_money_token(matches[-1])
        return abs(value) if value is not None else None

    matches = re.findall(r"-?\(?\d[\d,]{2,}\)?", joined)
    if matches:
        value = parse_money_token(matches[-1])
        return abs(value) if value is not None else None

    return None


def parse_date_from_line(line: str, default_year: int) -> tuple[date | None, str | None]:
    patterns = [
        r"^(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{2,4})\b",
        r"^(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b",
        r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2})\b",
    ]

    for idx, pattern in enumerate(patterns):
        match = re.search(pattern, line, re.IGNORECASE)
        if not match:
            continue

        if idx == 0:
            day = int(match.group(1))
            month = MONTH_NUMBERS[match.group(2).upper()]
            year_raw = match.group(3)
            year = int(year_raw if len(year_raw) == 4 else "20" + year_raw)
        elif idx == 1:
            day = int(match.group(1))
            month = MONTH_NUMBERS[match.group(2).upper()]
            year = int(default_year)
        else:
            month = MONTH_NUMBERS[match.group(1).upper()]
            day = int(match.group(2))
            year = int(default_year)

        try:
            parsed = date(year, month, day)
        except ValueError:
            return None, None
        return parsed, parsed.strftime("%Y-%m")

    return None, None


def extract_opening_closing_balance(full_text: str) -> tuple[Decimal | None, Decimal | None]:
    opening = None
    closing = None

    match = re.search(
        r"(?:Opening\s+balance|BALANCE\s+FORWARD)\s*(?:on[^\d\n]*)?"
        r"[:\s]*\$?\s*([\-\d,]+\.\d{2})",
        full_text,
        re.IGNORECASE,
    )
    if match:
        opening = parse_money_token(match.group(1))

    match = re.search(
        r"Closing\s+balance\s*(?:on[^\d\n]*)?[:\s]*=?\s*\$?\s*"
        r"([\-\d,]+\.\d{2})",
        full_text,
        re.IGNORECASE,
    )
    if match:
        closing = parse_money_token(match.group(1))

    if closing is None:
        match = re.search(
            r"Current\s+Balance:?\s*(?:CA)?\$?\s*([\-\d,]+\.\d{2})",
            full_text,
            re.IGNORECASE,
        )
        if match:
            closing = parse_money_token(match.group(1))

    return opening, closing


def extract_credit_anchor(full_text: str) -> tuple[Decimal | None, str | None]:
    patterns: tuple[tuple[str, str], ...] = (
        (
            r"Total\s+amounts\s+credited\s*\(\$\)[^\d\n]*\+?\s*([\d,]+\.\d{2})",
            "BMO: Total amounts credited",
        ),
        (
            r"Closing\s+totals[\s\S]*?[\d,]+\.\d{2}\s+([\d,]+\.\d{2})",
            "BMO: Closing totals",
        ),
        (
            r"Total\s+deposits\s*&\s*credits\s*\(\d+\)[^\d]*\+?\s*([\d,]+\.\d{2})",
            "RBC: Total deposits & credits",
        ),
        (
            r"(?:Total\s+(?:deposits|credits|amounts\s+deposited)|Amounts\s+deposited)"
            r"[^\d\n]*([\d,]+\.\d{2})",
            "Explicit deposit total",
        ),
    )

    for pattern, method in patterns:
        matches = re.findall(pattern, full_text, re.IGNORECASE)
        if matches:
            values = [parse_money_token(value) or Decimal("0") for value in matches]
            return sum(values, Decimal("0")), method

    return None, None


def group_words_into_lines(raw_words: list[dict]) -> list[tuple[float, list[tuple[float, str]]]]:
    line_dict: dict[float, list[tuple[float, str]]] = {}
    seen: set[tuple[float, float, str]] = set()

    for word_info in raw_words:
        word = str(word_info.get("text", "")).strip()
        if not word:
            continue
        x0 = float(word_info.get("x0", 0))
        y0 = float(word_info.get("top", 0))
        key = (round(x0, 1), round(y0, 1), word)
        if key in seen:
            continue
        seen.add(key)

        y_key = round(y0 / 3.5) * 3.5
        line_dict.setdefault(y_key, []).append((x0, word))

    return [
        (y_key, sorted(words, key=lambda item: item[0]))
        for y_key, words in sorted(line_dict.items(), key=lambda item: item[0])
    ]


def detect_statement_columns(
    sorted_words: list[tuple[float, str]],
    balance_x_min: float,
) -> tuple[float, float, float, float, float] | None:
    withdrawn_x = None
    deposited_x = None

    for x0, word in sorted_words:
        token = word.lower().strip()
        if any(key in token for key in ("withdrawn", "debited", "debit", "outflow", "payments")):
            withdrawn_x = x0
        elif any(key in token for key in ("deposited", "credited", "credit", "inflow", "deposits")):
            deposited_x = x0

    if withdrawn_x is None or deposited_x is None:
        return None

    debit_min = min(withdrawn_x, deposited_x) - 20
    debit_max = max(withdrawn_x, deposited_x) - 5
    credit_min = max(withdrawn_x, deposited_x) - 20
    credit_max = balance_x_min - 5
    return withdrawn_x - 10, debit_min, debit_max, credit_min, credit_max


def extract_text_with_fallbacks(pdf_bytes: bytes, *, enable_ocr: bool = False) -> tuple[str, list[str]]:
    diagnostics: list[str] = []

    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as doc:
            pages = []
            for page_no, page in enumerate(doc.pages, 1):
                try:
                    pages.append(page.extract_text(x_tolerance=2, y_tolerance=3) or "")
                except Exception as exc:
                    diagnostics.append(f"Page {page_no}: pdfplumber text extraction failed: {exc}")
                    pages.append("")
            text = "\n".join(pages).strip()
            if text:
                return text, diagnostics
    except Exception as exc:
        diagnostics.append(f"pdfplumber open failed: {exc}")

    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(pdf_bytes))
        pages = []
        for page_no, page in enumerate(reader.pages, 1):
            try:
                pages.append(page.extract_text() or "")
            except Exception as exc:
                diagnostics.append(f"Page {page_no}: pypdf text extraction failed: {exc}")
        text = "\n".join(pages).strip()
        if text:
            diagnostics.append("Used pypdf text fallback.")
            return text, diagnostics
    except Exception as exc:
        diagnostics.append(f"pypdf fallback unavailable/failed: {exc}")

    try:
        import fitz

        pdf = fitz.open(stream=pdf_bytes, filetype="pdf")
        pages = []
        for page_no, page in enumerate(pdf, 1):
            try:
                pages.append(page.get_text("text") or "")
            except Exception as exc:
                diagnostics.append(f"Page {page_no}: PyMuPDF text extraction failed: {exc}")
        pdf.close()
        text = "\n".join(pages).strip()
        if text:
            diagnostics.append("Used PyMuPDF text fallback.")
            return text, diagnostics
    except Exception as exc:
        diagnostics.append(f"PyMuPDF fallback unavailable/failed: {exc}")

    if enable_ocr:
        try:
            import fitz
            import pytesseract
            from PIL import Image

            pdf = fitz.open(stream=pdf_bytes, filetype="pdf")
            pages = []
            for page_no, page in enumerate(pdf, 1):
                try:
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                    image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    pages.append(
                        pytesseract.image_to_string(
                            image,
                            lang="eng+fra",
                            config="--psm 6",
                        ) or ""
                    )
                except Exception as exc:
                    diagnostics.append(f"Page {page_no}: OCR failed: {exc}")
            pdf.close()
            text = "\n".join(pages).strip()
            if text:
                diagnostics.append("Used OCR fallback.")
                return text, diagnostics
        except Exception as exc:
            diagnostics.append(f"OCR fallback unavailable/failed: {exc}")

    return "", diagnostics


def _default_year(full_text: str, period_start: date | None) -> int:
    if period_start is not None:
        return period_start.year
    years = [int(value) for value in re.findall(r"\b(201[5-9]|202[0-9])\b", full_text)]
    return max(years) if years else date.today().year


def _positioned_words(page, page_no: int, diagnostics: list[str]) -> list[dict]:
    try:
        words = page.extract_words(
            x_tolerance=2,
            y_tolerance=3,
            keep_blank_chars=False,
            use_text_flow=False,
        )
        if not words:
            diagnostics.append(f"Page {page_no}: no positioned words extracted.")
        return words or []
    except Exception as exc:
        diagnostics.append(f"Page {page_no}: positioned extraction failed: {exc}")
        return []


def _build_transaction(
    *,
    statement_id: str,
    source_file: str,
    page: int,
    transaction_date: date,
    description: str,
    amount: Decimal,
    direction: TransactionDirection,
    occurrence: int,
    raw_text: str,
    running_balance: Decimal | None = None,
) -> TransactionRecord:
    return TransactionRecord(
        transaction_id=stable_transaction_id(
            statement_id=statement_id,
            transaction_date=transaction_date,
            description=description,
            amount=amount,
            direction=direction.value,
            page=page,
            occurrence=occurrence,
        ),
        statement_id=statement_id,
        source_file=source_file,
        page=page,
        transaction_date=transaction_date,
        description=description,
        amount=amount,
        direction=direction,
        running_balance=running_balance,
        raw_text=raw_text,
    )


def parse_statement_pdf(
    pdf_bytes: bytes,
    *,
    source_file: str,
    enable_ocr: bool = False,
    vision_client: Any | None = None,
    enable_vision_fallback: bool = False,
    vision_model: str = "gpt-5.6-terra",
) -> ParsedStatement:
    file_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    statement_id = stable_statement_id(file_sha256=file_sha256)
    diagnostics: list[str] = []

    integrity = analyze_pdf_integrity(pdf_bytes)
    full_text, text_diagnostics = extract_text_with_fallbacks(
        pdf_bytes,
        enable_ocr=enable_ocr,
    )
    diagnostics.extend(text_diagnostics)

    if not full_text:
        diagnostics.append("No usable text could be extracted from the PDF.")
        quality = assess_extraction_quality(
            extraction_mode="NO_TEXT",
            bank_id=None,
            page_count=integrity.page_count,
            pages_with_positioned_words=0,
            transaction_count=0,
            period_detected=False,
            credit_anchor_detected=False,
            balances_detected=False,
            reconciliation_status=None,
        )
        diagnostics.extend(quality.warnings)
        return ParsedStatement(
            statement_id=statement_id,
            source_file=source_file,
            file_sha256=file_sha256,
            integrity=integrity,
            extraction_quality=quality,
            page_count=integrity.page_count,
            diagnostics=diagnostics,
        )

    bank_profile = detect_bank_profile(full_text)
    bank_id = bank_profile.bank_id if bank_profile else None
    bank_name = bank_profile.display_name if bank_profile else None

    period = extract_statement_period(full_text)
    coverage = None
    if period.period_start and period.period_end:
        coverage = calculate_statement_coverage(
            statement_id=statement_id,
            period_start=period.period_start,
            period_end=period.period_end,
            transaction_dates=[],
        )
    else:
        diagnostics.append(period.warning or "Statement period not detected.")

    opening_balance, closing_balance = extract_opening_closing_balance(full_text)
    credit_anchor, credit_anchor_method = extract_credit_anchor(full_text)

    transactions: list[TransactionRecord] = []
    mca_debits: list[McaDebit] = []
    occurrence_by_key: dict[tuple, int] = defaultdict(int)
    total_debits = Decimal("0")

    try:
        doc = pdfplumber.open(io.BytesIO(pdf_bytes))
    except Exception as exc:
        diagnostics.append(f"Could not open PDF for positioned parsing: {exc}")
        quality = assess_extraction_quality(
            extraction_mode="TEXT_ONLY",
            bank_id=bank_id,
            page_count=integrity.page_count,
            pages_with_positioned_words=0,
            transaction_count=0,
            period_detected=bool(period.period_start and period.period_end),
            credit_anchor_detected=credit_anchor is not None,
            balances_detected=(
                opening_balance is not None and closing_balance is not None
            ),
            reconciliation_status=None,
        )
        diagnostics.extend(quality.warnings)
        return ParsedStatement(
            statement_id=statement_id,
            source_file=source_file,
            file_sha256=file_sha256,
            page_count=integrity.page_count,
            bank_id=bank_id,
            bank_name=bank_name,
            extraction_quality=quality,
            period_start=period.period_start,
            period_end=period.period_end,
            coverage=coverage,
            integrity=integrity,
            opening_balance=opening_balance,
            closing_balance=closing_balance,
            credit_anchor=credit_anchor,
            credit_anchor_method=credit_anchor_method,
            diagnostics=diagnostics,
        )

    is_nbc = bank_id == "NBC"
    default_year = _default_year(full_text, period.period_start)
    pages_with_positioned_words = 0
    positioned_page_numbers: set[int] = set()
    vision_rows_added = 0
    active_date: date | None = None

    debit_x_min, debit_x_max = 200.0, 370.0
    credit_x_min, credit_x_max = 370.0, 460.0
    desc_x_limit = 200.0
    balance_x_min = 460.0

    try:
        for page_num, page in enumerate(doc.pages, 1):
            raw_words = _positioned_words(page, page_num, diagnostics)
            if not raw_words:
                continue

            pages_with_positioned_words += 1
            positioned_page_numbers.add(page_num)
            grouped_lines = group_words_into_lines(raw_words)

            page_balance_x = None
            for _, words in grouped_lines[:20]:
                for x0, word in words:
                    if word.lower().replace(" ", "") in {"balance", "balance($)", "balance(s)"}:
                        page_balance_x = x0 - 10
                        break
                if page_balance_x is not None:
                    break

            if page_balance_x is not None:
                balance_x_min = page_balance_x
                credit_x_max = balance_x_min - 5

            for line_index, (_, sorted_words) in enumerate(grouped_lines):
                full_line = " ".join(word for _, word in sorted_words)

                lookahead_line = ""
                if line_index + 1 < len(grouped_lines):
                    lookahead_line = " ".join(
                        word for _, word in grouped_lines[line_index + 1][1]
                    )
                combined_lower = f"{full_line} {lookahead_line}".lower()

                header_hit = (
                    any(
                        key in combined_lower
                        for key in (
                            "withdrawn", "debited", "debit", "payments",
                            "deposited", "credited", "credit", "deposits",
                        )
                    )
                    and any(
                        key in combined_lower
                        for key in (
                            "withdrawn", "debited", "debit",
                            "deposited", "credited", "credit",
                        )
                    )
                )
                if header_hit:
                    calibration = detect_statement_columns(sorted_words, balance_x_min)
                    if calibration:
                        (
                            desc_x_limit,
                            debit_x_min,
                            debit_x_max,
                            credit_x_min,
                            credit_x_max,
                        ) = calibration

                if any(
                    key in full_line.upper()
                    for key in (
                        "ACCOUNT/TRANSACTION TYPE",
                        "FEES PAID",
                        "NEXT STATEMENT",
                        "MONTHLY AVER",
                        "DEP CONTENT",
                        "CHQS ENCLOSED",
                    )
                ):
                    continue

                parsed_date, _ = parse_date_from_line(full_line, default_year)
                is_date_row = parsed_date is not None

                if is_nbc:
                    nbc_match = re.match(
                        r"^[\s|]*(0[1-9]|1[0-2])[\s|]+(0[1-9]|[12]\d|3[01])\b",
                        full_line,
                    )
                    if nbc_match:
                        try:
                            parsed_date = date(
                                default_year,
                                int(nbc_match.group(1)),
                                int(nbc_match.group(2)),
                            )
                            is_date_row = True
                        except ValueError:
                            parsed_date = None
                            is_date_row = False

                if is_date_row and parsed_date is not None:
                    active_date = parsed_date

                has_currency = bool(re.search(r"\d+\.\d{2}", full_line))
                if not (is_date_row or (active_date and has_currency)):
                    continue

                debit_parts: list[str] = []
                credit_parts: list[str] = []
                desc_words: list[str] = []

                if is_nbc and is_date_row:
                    for x0, word in sorted_words:
                        if x0 < 90:
                            continue
                        if x0 < 270:
                            if word != "|":
                                desc_words.append(word)
                        elif 270 <= x0 < 375 and re.search(r"[\d,]", word):
                            debit_parts.append(word)
                        elif 375 <= x0 < 465 and re.search(r"[\d,]", word):
                            credit_parts.append(word)
                else:
                    for x0, word in sorted_words:
                        if x0 >= balance_x_min:
                            continue
                        if (
                            x0 < desc_x_limit
                            and not re.match(
                                r"^(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)$",
                                word,
                                re.IGNORECASE,
                            )
                        ):
                            if not desc_words and re.match(r"^\d{1,2}$", word):
                                continue
                            desc_words.append(word)
                        elif debit_x_min <= x0 < debit_x_max and re.search(r"[\d,.\-()]", word):
                            debit_parts.append(word)
                        elif credit_x_min <= x0 < credit_x_max and re.search(r"[\d,.\-()]", word):
                            credit_parts.append(word)

                debit_amount = money_from_words(debit_parts)
                credit_amount = money_from_words(credit_parts)
                description = " ".join(desc_words).strip()
                description_upper = description.upper()

                if any(
                    key in description_upper
                    for key in (
                        "CLOSING",
                        "OPENING",
                        "ITEMS PROCESSED",
                        "BALANCE FORWARD",
                        "TOTALS",
                        "SOLDE PRECEDENT",
                        "FACTURATION",
                        "NEW BALANCE",
                        "TOTAL FUNDS",
                        "TRANSACTIONS",
                    )
                ):
                    continue
                if "TOTAL" in description_upper and len(desc_words) < 3:
                    continue
                if active_date is None:
                    continue

                if credit_amount is not None and credit_amount > 0:
                    key = (
                        page_num,
                        active_date,
                        description or "Deposit",
                        credit_amount,
                        TransactionDirection.CREDIT.value,
                    )
                    occurrence = occurrence_by_key[key]
                    occurrence_by_key[key] += 1
                    transactions.append(
                        _build_transaction(
                            statement_id=statement_id,
                            source_file=source_file,
                            page=page_num,
                            transaction_date=active_date,
                            description=description or "Deposit",
                            amount=credit_amount,
                            direction=TransactionDirection.CREDIT,
                            occurrence=occurrence,
                            raw_text=full_line,
                        )
                    )

                if debit_amount is not None and debit_amount > 0:
                    total_debits += debit_amount
                    key = (
                        page_num,
                        active_date,
                        description or "Debit",
                        debit_amount,
                        TransactionDirection.DEBIT.value,
                    )
                    occurrence = occurrence_by_key[key]
                    occurrence_by_key[key] += 1
                    transaction = _build_transaction(
                        statement_id=statement_id,
                        source_file=source_file,
                        page=page_num,
                        transaction_date=active_date,
                        description=description or "Debit",
                        amount=debit_amount,
                        direction=TransactionDirection.DEBIT,
                        occurrence=occurrence,
                        raw_text=full_line,
                    )
                    transactions.append(transaction)

                    mca = build_mca_debit(
                        transaction_date=active_date,
                        description=description,
                        amount=float(debit_amount),
                        transaction_id=transaction.transaction_id,
                    )
                    if mca:
                        mca_debits.append(mca)

    finally:
        doc.close()

    if enable_vision_fallback and vision_client is not None:
        extracted_pages = {
            transaction.page
            for transaction in transactions
            if transaction.page is not None
        }
        if transactions:
            vision_pages = [
                page_number
                for page_number in range(1, integrity.page_count + 1)
                if (
                    page_number not in positioned_page_numbers
                    and page_number not in extracted_pages
                )
            ]
        else:
            vision_pages = list(range(1, integrity.page_count + 1))

        existing_signatures = {
            (
                transaction.page,
                transaction.transaction_date,
                transaction.direction.value,
                transaction.amount,
                transaction.description.strip().upper(),
            )
            for transaction in transactions
        }

        for page_number in vision_pages:
            try:
                png_bytes = render_pdf_page_png(
                    pdf_bytes,
                    page_number=page_number,
                )
                vision_page = extract_page_ledger_with_vision(
                    client=vision_client,
                    png_bytes=png_bytes,
                    page_number=page_number,
                    model=vision_model,
                )
            except Exception as exc:
                diagnostics.append(
                    f"Page {page_number}: vision fallback failed: {exc}"
                )
                continue

            for warning in vision_page.warnings:
                diagnostics.append(
                    f"Page {page_number}: vision warning: {warning}"
                )

            for vision_transaction in vision_page.transactions:
                if vision_transaction.credit is not None:
                    direction = TransactionDirection.CREDIT
                    amount = vision_transaction.credit
                else:
                    direction = TransactionDirection.DEBIT
                    amount = vision_transaction.debit

                if amount is None:
                    continue

                signature = (
                    page_number,
                    vision_transaction.transaction_date,
                    direction.value,
                    amount,
                    vision_transaction.description.strip().upper(),
                )
                if signature in existing_signatures:
                    continue

                key = (
                    page_number,
                    vision_transaction.transaction_date,
                    vision_transaction.description,
                    amount,
                    direction.value,
                )
                occurrence = occurrence_by_key[key]
                occurrence_by_key[key] += 1

                transaction = _build_transaction(
                    statement_id=statement_id,
                    source_file=source_file,
                    page=page_number,
                    transaction_date=vision_transaction.transaction_date,
                    description=vision_transaction.description,
                    amount=amount,
                    direction=direction,
                    occurrence=occurrence,
                    raw_text=vision_transaction.evidence_text,
                    running_balance=vision_transaction.running_balance,
                )
                transactions.append(transaction)
                existing_signatures.add(signature)
                vision_rows_added += 1

                if direction == TransactionDirection.DEBIT:
                    mca = build_mca_debit(
                        transaction_date=vision_transaction.transaction_date,
                        description=vision_transaction.description,
                        amount=float(amount),
                        transaction_id=transaction.transaction_id,
                    )
                    if mca:
                        mca_debits.append(mca)

        if vision_rows_added:
            diagnostics.append(
                f"Vision fallback added {vision_rows_added} transaction row(s). "
                "These rows remain subject to reconciliation and manual review."
            )

    total_debits = sum(
        (
            transaction.amount
            for transaction in transactions
            if transaction.direction == TransactionDirection.DEBIT
        ),
        Decimal("0"),
    )

    if credit_anchor is None and opening_balance is not None and closing_balance is not None:
        implied_credits = closing_balance - opening_balance + total_debits
        if implied_credits >= 0:
            credit_anchor = implied_credits
            credit_anchor_method = "Balance equation fallback"
            diagnostics.append(
                "No explicit deposit anchor found; derived total credits from "
                "closing - opening + extracted debits."
            )

    reconciliation = reconcile_statement(
        statement_id=statement_id,
        transactions=transactions,
        opening_balance=opening_balance,
        closing_balance=closing_balance,
    )

    if reconciliation.warning:
        diagnostics.append(reconciliation.warning)

    composite_integrity = assess_statement_integrity(
        structural=integrity,
        coverage=coverage,
        reconciliation=reconciliation,
        transactions=transactions,
    )

    if vision_rows_added and pages_with_positioned_words > 0:
        extraction_mode = "HYBRID_NATIVE_VISION"
    elif vision_rows_added:
        extraction_mode = "VISION_FALLBACK"
    elif pages_with_positioned_words > 0:
        extraction_mode = "NATIVE_POSITIONED"
    elif any("Used OCR fallback." in item for item in diagnostics):
        extraction_mode = "OCR_TEXT_ONLY"
    elif full_text:
        extraction_mode = "TEXT_ONLY"
    else:
        extraction_mode = "NO_TEXT"

    extraction_quality = assess_extraction_quality(
        extraction_mode=extraction_mode,
        bank_id=bank_id,
        page_count=integrity.page_count,
        pages_with_positioned_words=pages_with_positioned_words,
        transaction_count=len(transactions),
        period_detected=bool(period.period_start and period.period_end),
        credit_anchor_detected=credit_anchor is not None,
        balances_detected=(
            opening_balance is not None and closing_balance is not None
        ),
        reconciliation_status=reconciliation.status.value,
    )
    diagnostics.extend(extraction_quality.warnings)

    return ParsedStatement(
        statement_id=statement_id,
        source_file=source_file,
        file_sha256=file_sha256,
        page_count=integrity.page_count,
        bank_id=bank_id,
        bank_name=bank_name,
        extraction_quality=extraction_quality,
        period_start=period.period_start,
        period_end=period.period_end,
        coverage=coverage,
        integrity=integrity,
        composite_integrity=composite_integrity,
        opening_balance=opening_balance,
        closing_balance=closing_balance,
        credit_anchor=credit_anchor,
        credit_anchor_method=credit_anchor_method,
        transactions=transactions,
        mca_debits=mca_debits,
        reconciliation_status=reconciliation.status.value,
        reconciliation_variance=reconciliation.variance,
        diagnostics=diagnostics,
    )
