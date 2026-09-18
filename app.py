import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import pdfplumber
import io
import json
import re
import hashlib
from openai import OpenAI

from engine_v2.ai_classifier import classify_unresolved_transactions
from engine_v2.classification import classify_by_rules as v2_classify_by_rules
from engine_v2.coverage import calculate_statement_coverage
from engine_v2.credit_extraction import extract_credit_profile
from engine_v2.identifiers import stable_statement_id, stable_transaction_id
from engine_v2.period import extract_statement_period
from engine_v2.pdf_integrity import analyze_pdf_integrity
from engine_v2.pipeline import analyze_statement_files
from engine_v2.scorecard import ScorecardInputs, calculate_scorecard


st.set_page_config(page_title="Forward Funding - Underwriting Tool", layout="wide")
st.title("📊 Forward Funding: Underwriting Tool")

#API KEY
try:
    api_key = st.secrets["OPENAI_API_KEY"]
except (FileNotFoundError, KeyError):
    api_key = st.sidebar.text_input("Enter OpenAI API Key (or configure secrets.toml)", type="password")

client = OpenAI(api_key=api_key) if api_key else None
CLASSIFIER_MODEL = "gpt-5.6-terra"
VISION_MODEL = "gpt-5.6-terra"
CREDIT_MODEL = "gpt-5.6-sol"

# INDUSTRY SCORING DICTIONARY 
INDUSTRY_SCORING = {
    "0191 - General Farms, Primarily Crop": {"points": 4, "seasonality": 1},
    "0212 - Beef Cattle, Except Feedlots": {"points": 4, "seasonality": 3},
    "1521 - General Contractors—Single-Family Houses": {"points": 4, "seasonality": 2},
    "1522 - General Contractors—Residential Buildings, Other": {"points": 4, "seasonality": 2},
    "1542 - General Contractors—Nonresidential Buildings": {"points": 5, "seasonality": 3},
    "1611 - Highway and Street Construction": {"points": 5, "seasonality": 1},
    "1711 - Plumbing, Heating & Air-Conditioning": {"points": 7, "seasonality": 3},
    "1721 - Painting and Paper Hanging": {"points": 4, "seasonality": 1},
    "1731 - Electrical Work": {"points": 7, "seasonality": 3},
    "1741 - Masonry, Stonework, Tile Setting & Plastering": {"points": 5, "seasonality": 1},
    "1751 - Carpentry Work": {"points": 5, "seasonality": 2},
    "1761 - Roofing, Siding & Sheet Metal Work": {"points": 3, "seasonality": 1},
    "1771 - Concrete Work": {"points": 4, "seasonality": 1},
    "1794 - Excavation Work": {"points": 4, "seasonality": 1},
    "1799 - Special Trade Contractors, NEC": {"points": 5, "seasonality": 3},
    "2011 - Meat Packing Plants": {"points": 5, "seasonality": 5},
    "2051 - Bread and Other Bakery Products": {"points": 6, "seasonality": 6},
    "2431 - Millwork": {"points": 5, "seasonality": 3},
    "2511 - Wood Household Furniture": {"points": 5, "seasonality": 3},
    "2752 - Commercial Printing, Lithographic": {"points": 5, "seasonality": 5},
    "3441 - Fabricated Structural Metal": {"points": 5, "seasonality": 3},
    "4212 - Local Trucking Without Storage": {"points": 4, "seasonality": 3},
    "4213 - Trucking, Except Local": {"points": 4, "seasonality": 3},
    "4215 - Courier Services, Except by Air": {"points": 5, "seasonality": 5},
    "5013 - Motor Vehicle Supplies & New Parts—Wholesale": {"points": 6, "seasonality": 6},
    "5031 - Lumber, Plywood, Millwork & Wood Panels—Wholesale": {"points": 5, "seasonality": 3},
    "5045 - Computers & Peripheral Equipment and Software—Wholesale": {"points": 6, "seasonality": 6},
    "5211 - Lumber & Other Building Materials Dealers": {"points": 6, "seasonality": 3},
    "5251 - Hardware Stores": {"points": 7, "seasonality": 5},
    "5411 - Grocery Stores": {"points": 7, "seasonality": 6},
    "5461 - Retail Bakeries": {"points": 6, "seasonality": 5},
    "5511 - Motor Vehicle Dealers (New and Used)": {"points": 4, "seasonality": 3},
    "5521 - Motor Vehicle Dealers (Used Only)": {"points": 3, "seasonality": 3},
    "5531 - Auto and Home Supply Stores": {"points": 6, "seasonality": 6},
    "5541 - Gasoline Service Stations": {"points": 6, "seasonality": 6},
    "5611 - Men's and Boys' Clothing Stores": {"points": 5, "seasonality": 2},
    "5621 - Women's Clothing Stores": {"points": 5, "seasonality": 2},
    "5661 - Shoe Stores": {"points": 5, "seasonality": 3},
    "5712 - Furniture Stores": {"points": 4, "seasonality": 3},
    "5731 - Radio, Television & Consumer Electronics Stores": {"points": 4, "seasonality": 3},
    "5812 - Eating Places / Restaurants": {"points": 4, "seasonality": 2},
    "5813 - Drinking Places / Bars": {"points": 2, "seasonality": 1},
    "5912 - Drug Stores & Proprietary Stores": {"points": 7, "seasonality": 6},
    "5921 - Liquor Stores": {"points": 5, "seasonality": 3},
    "5999 - Miscellaneous Retail Stores, NEC": {"points": 4, "seasonality": 3},
    "6512 - Operators of Nonresidential Buildings": {"points": 6, "seasonality": 6},
    "6513 - Operators of Apartment Buildings": {"points": 7, "seasonality": 6},
    "7011 - Hotels & Motels": {"points": 4, "seasonality": 1},
    "7215 - Coin-Operated Laundries & Drycleaning": {"points": 7, "seasonality": 6},
    "7231 - Beauty Shops": {"points": 6, "seasonality": 3},
    "7241 - Barber Shops": {"points": 6, "seasonality": 5},
    "7311 - Advertising Agencies": {"points": 6, "seasonality": 5},
    "7349 - Building Cleaning & Maintenance Services, NEC": {"points": 7, "seasonality": 6},
    "7371 - Computer Programming Services": {"points": 7, "seasonality": 6},
    "7372 - Prepackaged Software": {"points": 7, "seasonality": 6},
    "7373 - Computer Integrated Systems Design": {"points": 7, "seasonality": 6},
    "7538 - General Automotive Repair Shops": {"points": 7, "seasonality": 5},
    "7542 - Carwashes": {"points": 6, "seasonality": 2},
    "7997 - Membership Sports & Recreation Clubs": {"points": 4, "seasonality": 2},
    "7999 - Amusement & Recreation Services, NEC": {"points": 3, "seasonality": 1},
    "8011 - Offices & Clinics of Doctors of Medicine": {"points": 8, "seasonality": 6},
    "8021 - Offices & Clinics of Dentists": {"points": 8, "seasonality": 6},
    "8041 - Offices & Clinics of Chiropractors": {"points": 7, "seasonality": 5},
    "8042 - Offices & Clinics of Optometrists": {"points": 7, "seasonality": 5},
    "8049 - Offices & Clinics of Health Practitioners, NEC": {"points": 7, "seasonality": 5},
    "8082 - Home Health Care Services": {"points": 7, "seasonality": 6},
    "8111 - Legal Services": {"points": 8, "seasonality": 6},
    "8721 - Accounting, Auditing & Bookkeeping Services": {"points": 8, "seasonality": 3},
    "8742 - Management Consulting Services": {"points": 7, "seasonality": 5},
    "8999 - Services, NEC": {"points": 4, "seasonality": 3}
}

# --- CUSTOM MCA LENDER DICTIONARY (TIERED) ---
PREMIUM_LENDERS = {
    "MERCHANT GROWTH": ["MERCHANT GROWTH", "MERCHPAD", "MERCH PAD"],
    "GREENBOX": ["GREENBOX", "GREEN BOX", "GREENBOX CAPITAL"],
    "VAULT": ["VAULT", "VAULT FINANCIAL"],
    "DRIVEN": ["DRIVEN", "DRIVEN CAPITAL"],
    "JOURNEY": ["JOURNEY", "JOURNEY CAPITAL", "JOURNEY FUNDING", "ONDECK"],
    "ICAPITAL": ["ICAPITAL", "I CAPITAL", "IPAPITAL"]
}

STANDARD_LENDERS = {
    "CANACAP": ["CANACAP", "CANA CAP", "CANA CAPITAL", "CANACAPITAL"],
    "2M7": ["2M7", "2M7 FINANCIAL", "URAL", "URAL CAPITAL"],
    "BIZFUND": ["BIZFUND", "BIZ FUND", "BIZ-FUND"],
    "XUPER": ["XUPER", "XUPER FUNDING", "XUPER CAPITAL"],
    "NEWCO": ["NEWCO", "NEWCO CAPITAL"],
    "SHEAVES": ["SHEAVES", "SHEAVES CAPITAL"],
    "CMCA": ["CMCA", "C.M.C.A.", "CANADIAN MERCHANT"],
    "B2B": ["B2B", "B2B CAPITAL", "B2B FUNDING"],
    "FORWARD FUNDING": ["FORWARD FUNDING", "FORWARDFUNDING"],
    "KM CAPITAL": ["2313833 ONTARIO", "2313833 ONTARIO INC", "KM CAPITAL"],
    "EFSA": ["EFSA", "EFSA CAPITAL"],
    "ROOK BRISTOL": ["ROOK BRISTOL"],
    "ELECT CAPITAL": ["ELECT CAPITAL"],
    "SHARP SHOOTER": ["SHARP SHOOTER FUNDING", "SSF"],
    "MFUND": ["MFUND"],
    "9341-8812 QUEBEC": ["9341-8812 QUE", "9341-8812 QUEBEC INC"],
    "NORTH FUNDING": ["NORTH FUNDING"],
    "BUSINESS CREDIT CAPITAL": ["BUSINESS CR", "BCC", "BUSINESS CREDIT CAPITAL"],
    "FLEX CAPITAL": ["FLEXCAPITALGROUP", "FLEX CAPITAL"],
    "ONTAP": ["ONTAP CAPITAL"],
    "CLARA": ["CLARA CAPITAL"],
    "FUNDFI": ["FUNDFI"],
    "ADVENTEX": ["ADVANTEX", "ADVANTEX MARKETING", "ADVANTEX DINING"],
    "CAPITAL ADVANCE": ["CAPITAL ADVANCE"],
    "SIMPLY": ["SIMPLY"],
    "CLARIO": ["CLARIO"],
    "BIZCAP": ["BIZCAP"],
    "KEEP BUS": ["KEEP BUS", "KEEP BUS/ENT"],
    "1048279 ONT": ["1048279 ONT", "1048279 ONT RLS/LOY"],
    "TOTAL CREDIT": ["TOTAL CREDIT"],
    "PEOPLES TRUST": ["PEOPLES TRUST"],
    "ACURA FINANCE": ["ACURA FINANCE"],
}

ALL_KNOWN_LENDERS = {}
for l, vars in PREMIUM_LENDERS.items():
    for v in vars: ALL_KNOWN_LENDERS[v] = ("Premium", l)
for l, vars in STANDARD_LENDERS.items():
    for v in vars: ALL_KNOWN_LENDERS[v] = ("Standard", l)

# --- OWN-ACCOUNT / INTERNAL TRANSFER SIGNATURE PATTERNS ---
INTERNAL_TRANSFER_PATTERNS = [
    r'\bTF\s*\d{3,4}\s*#\s*\d{3,4}[\-#]\d{3,4}\b',      
    r'\bONLINE\s+TRANSFER\b',
    r'\bINTERNAL\s+TRANSFER\b',
    r'\bBR\.?\s*\d{3,4}\b',                              
    r'\bBALANCE\s+ADJUSTMENT\b',
    r'\b\d{4}-\d{4}-\d{3,4}\s*1005\b',                   
]

GOV_TAX_INSURANCE_PATTERNS = [
    r'\bPROV[/\.]?\s*LOCAL\s+GVT\s+PAYMENT\b',
    r'\bPROVINCE\s+OF\b',
    r'\bCRA\b|\bCANADA\s+REVENUE\b|\bPAD\s+CCRA\b',
    r'\bGST\b|\bHST\b',
    r'\bEI\s+BENEFIT\b|\bSERVICE\s+CANADA\b',
]

NSF_REVERSAL_PATTERNS = [
    r'\bNSF\b', r'RETURNED\s+ITEM', r'\bITEM\s+RETURNED\b', r'\bUNPAID\b',
    r'DISHONOURED', r'FRAIS\s+EFFET\s+RET', r'\bREVERSE\b', r'\bRECLAIM\b',
]

# --- STRICT 3-TIER CATEGORIZATION SCHEMA ---
CATEGORIZATION_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "statement_categorization",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "mappings": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "description": {"type": "string"},
                            "category": {
                                "type": "string",
                                "enum": [
                                    "True Revenue - POS / Processor",
                                    "True Revenue - Verified Cash",
                                    "True Revenue - Customer Payment / Cheque",
                                    "True Revenue - B2B E-Transfer",
                                    "Non-Revenue - Own-Account / Internal Transfer",
                                    "Non-Revenue - MCA / Loan Proceeds",
                                    "Non-Revenue - Refund / Reversal / NSF",
                                    "Non-Revenue - Gov / Tax / Insurance Proceeds",
                                    "Non-Revenue - Shareholder / Investment",
                                    "Non-Revenue - Wash / Round-Trip Transfer",
                                    "Review Required - Unidentified / Unusual Deposit"
                                ]
                            }
                        },
                        "required": ["description", "category"],
                        "additionalProperties": False
                    }
                }
            },
            "required": ["mappings"],
            "additionalProperties": False
        }
    }
}

# --- STRICT CREDIT REPORT SCHEMA ---
CREDIT_REPORT_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "credit_report_extraction",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "owner_name": {"type": "string"},
                "fico_score": {"type": "integer", "description": "The 3-digit FICO or Beacon score"},
                "total_high_credit": {"type": "number", "description": "Extract the exact explicit number listed under 'High Credit' or 'HighCred'. DO NOT calculate, sum, or add credit limits together."},
                "revolving_credit_utilization_pct": {"type": "number", "description": "The revolving credit utilization percentage (e.g., 100 for 100%)"},
                "active_collections_count": {"type": "integer", "description": "Number of unpaid or active collections"},
                "total_collections_amount": {"type": "number", "description": "Total dollar amount of active collections"},
                "bankruptcies_found": {"type": "boolean", "description": "True if any bankruptcies or consumer proposals are found"},
                "number_of_mortgages": {"type": "integer", "description": "Total number of mortgage trades found in the portfolio"},
                "mortgage_ltv_details": {"type": "string", "description": "LTV ratio if property value is reported, otherwise state 'Property values not reported'"}
            },
            "required": [
                "owner_name", "fico_score", "total_high_credit", "revolving_credit_utilization_pct",
                "active_collections_count", "total_collections_amount", "bankruptcies_found",
                "number_of_mortgages", "mortgage_ltv_details"
            ],
            "additionalProperties": False
        }
    }
}

# --- SESSION STATE INITIALIZATION ---
if 'transactions' not in st.session_state:
    st.session_state.transactions = None
if 'mca_positions' not in st.session_state:
    st.session_state.mca_positions = []
if 'expected_credits' not in st.session_state:
    st.session_state.expected_credits = 0.0
if 'credit_profile' not in st.session_state:
    st.session_state.credit_profile = {
        "owner_name": None,
        "fico_score": None,
        "total_high_credit": None,
        "revolving_credit_utilization_pct": None,
        "active_collections_count": None,
        "total_collections_amount": None,
        "bankruptcies_found": None,
        "number_of_mortgages": None,
        "mortgage_ltv_details": None,
        "evidence": {},
        "warnings": [],
        "model_name": None,
        "is_loaded": False
    }
if 'diagnostic_log' not in st.session_state:
    st.session_state.diagnostic_log = []
if 'file_signatures' not in st.session_state:
    st.session_state.file_signatures = {}
if 'statement_coverage' not in st.session_state:
    st.session_state.statement_coverage = []
if 'pdf_integrity_reports' not in st.session_state:
    st.session_state.pdf_integrity_reports = []
if 'full_ledger' not in st.session_state:
    st.session_state.full_ledger = None
if 'revenue_baseline' not in st.session_state:
    st.session_state.revenue_baseline = None
if 'decision_readiness' not in st.session_state:
    st.session_state.decision_readiness = None


# ==============================================================================
# HELPERS - ROBUST PDF EXTRACTION / PARSING
# ==============================================================================

def safe_pdf_text(pdf_bytes):
    """Extract text without allowing one bad PDF/page to crash the application."""
    errors = []
    text_pages = []

    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as doc:
            for page_no, page in enumerate(doc.pages, 1):
                try:
                    page_text = page.extract_text(x_tolerance=2, y_tolerance=3) or ""
                except Exception as exc:
                    errors.append(f"Page {page_no}: text extraction failed ({exc})")
                    page_text = ""
                text_pages.append(page_text)
    except Exception as exc:
        errors.append(f"pdfplumber open failed ({exc})")

    text = "\n".join(text_pages).strip()
    if text:
        return text, errors

    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(pdf_bytes))
        fallback_pages = []
        for page_no, page in enumerate(reader.pages, 1):
            try:
                fallback_pages.append(page.extract_text() or "")
            except Exception as exc:
                errors.append(f"pypdf page {page_no}: {exc}")
        text = "\n".join(fallback_pages).strip()
        if text:
            errors.append("Used pypdf text fallback.")
            return text, errors
    except Exception as exc:
        errors.append(f"pypdf fallback unavailable/failed ({exc})")

    try:
        import fitz
        pdf = fitz.open(stream=pdf_bytes, filetype="pdf")
        fallback_pages = []
        for page_no, page in enumerate(pdf, 1):
            try:
                fallback_pages.append(page.get_text("text") or "")
            except Exception as exc:
                errors.append(f"PyMuPDF page {page_no}: {exc}")
        pdf.close()
        text = "\n".join(fallback_pages).strip()
        if text:
            errors.append("Used PyMuPDF text fallback.")
            return text, errors
    except Exception as exc:
        errors.append(f"PyMuPDF fallback unavailable/failed ({exc})")

    # Optional OCR fallback for scanned/image-only PDFs.
    try:
        import fitz
        import pytesseract
        from PIL import Image
        pdf = fitz.open(stream=pdf_bytes, filetype="pdf")
        ocr_pages = []
        for page_no, page in enumerate(pdf, 1):
            try:
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                ocr_pages.append(
                    pytesseract.image_to_string(img, config="--psm 6") or ""
                )
            except Exception as exc:
                errors.append(f"OCR page {page_no}: {exc}")
        pdf.close()
        text = "\n".join(ocr_pages).strip()
        if text:
            errors.append("Used OCR fallback for image/scanned PDF.")
            return text, errors
    except Exception as exc:
        errors.append(f"OCR fallback unavailable/failed ({exc})")

    return "", errors


def open_pdf_safely(pdf_bytes):
    try:
        return pdfplumber.open(io.BytesIO(pdf_bytes)), None
    except Exception as exc:
        return None, exc


def extract_words_safely(page, page_no, diagnostic_log):
    try:
        words = page.extract_words(
            x_tolerance=2,
            y_tolerance=3,
            keep_blank_chars=False,
            use_text_flow=False
        )
        if words:
            return words
        diagnostic_log.append(f"⚠️ Page {page_no}: no positioned words extracted.")
    except Exception as exc:
        diagnostic_log.append(f"⚠️ Page {page_no}: positioned extraction failed: {exc}")
    return []


def group_words_into_lines(raw_words):
    line_dict = {}
    seen = set()

    for w in raw_words:
        word = str(w.get("text", "")).strip()
        if not word:
            continue
        x0 = float(w.get("x0", 0))
        y0 = float(w.get("top", 0))
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


def parse_money_token(value):
    if value is None:
        return None

    s = str(value).strip().replace("$", "").replace(" ", "")
    if not s:
        return None

    negative = s.startswith("(") and s.endswith(")")
    s = s.strip("()")

    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        tail = s.rsplit(",", 1)[-1]
        if len(tail) == 2:
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")

    try:
        number = float(s)
        return -number if negative else number
    except (TypeError, ValueError):
        return None


def money_from_words(words):
    if not words:
        return None

    joined = "".join(str(w) for w in words).replace("$", "").replace(" ", "")
    matches = re.findall(r'-?\(?\d[\d,]*\.\d{2}\)?', joined)
    if matches:
        value = parse_money_token(matches[-1])
        return abs(value) if value is not None else None

    matches = re.findall(r'-?\(?\d[\d,]{2,}\)?', joined)
    if matches:
        value = parse_money_token(matches[-1])
        return abs(value) if value is not None else None

    return None


def detect_statement_columns(sorted_words, balance_x_min):
    withdrawn_x = None
    deposited_x = None

    for x0, word in sorted_words:
        w = word.lower().strip()
        if any(k in w for k in ("withdrawn", "debited", "debit", "outflow", "payments")):
            withdrawn_x = x0
        elif any(k in w for k in ("deposited", "credited", "credit", "inflow", "deposits")):
            deposited_x = x0

    if withdrawn_x is not None and deposited_x is not None:
        debit_min = min(withdrawn_x, deposited_x) - 20
        debit_max = max(withdrawn_x, deposited_x) - 5
        credit_min = max(withdrawn_x, deposited_x) - 20
        credit_max = balance_x_min - 5
        return withdrawn_x - 10, debit_min, debit_max, credit_min, credit_max

    return None


def parse_date_from_line(line, default_year):
    patterns = [
        r'^(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{2,4})\b',
        r'^(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b',
        r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2})\b',
    ]
    month_numbers = {
        "JAN":"01","FEB":"02","MAR":"03","APR":"04","MAY":"05","JUN":"06",
        "JUL":"07","AUG":"08","SEP":"09","OCT":"10","NOV":"11","DEC":"12"
    }

    for idx, pattern in enumerate(patterns):
        m = re.search(pattern, line, re.IGNORECASE)
        if not m:
            continue

        if idx == 0:
            day, month, year = m.group(1), m.group(2).upper(), m.group(3)
            year = year if len(year) == 4 else "20" + year
        elif idx == 1:
            day, month, year = m.group(1), m.group(2).upper(), str(default_year)
        else:
            month, day, year = m.group(1).upper(), m.group(2), str(default_year)

        month_num = month_numbers.get(month)
        if month_num:
            return f"{year}-{month_num}-{str(day).zfill(2)}", f"{year}-{month_num}"

    return None, None


def extract_opening_closing_balance(full_pdf_text):
    opening, closing = None, None

    m = re.search(
        r'(?:Opening\s+balance|BALANCE\s+FORWARD)\s*(?:on[^\d\n]*)?'
        r'[:\s]*\$?\s*([\-\d,]+\.\d{2})',
        full_pdf_text, re.IGNORECASE
    )
    if m:
        opening = parse_money_token(m.group(1))

    m = re.search(
        r'Closing\s+balance\s*(?:on[^\d\n]*)?[:\s]*=?\s*\$?\s*'
        r'([\-\d,]+\.\d{2})',
        full_pdf_text, re.IGNORECASE
    )
    if m:
        closing = parse_money_token(m.group(1))

    if closing is None:
        m = re.search(
            r'Current\s+Balance:?\s*(?:CA)?\$?\s*([\-\d,]+\.\d{2})',
            full_pdf_text, re.IGNORECASE
        )
        if m:
            closing = parse_money_token(m.group(1))

    return opening, closing


def matches_any(patterns, text_upper):
    return any(re.search(p, text_upper) for p in patterns)


def rule_based_category(desc_upper, max_amount=None):
    if matches_any(INTERNAL_TRANSFER_PATTERNS, desc_upper):
        return "Non-Revenue - Own-Account / Internal Transfer"
    if matches_any(GOV_TAX_INSURANCE_PATTERNS, desc_upper):
        return "Non-Revenue - Gov / Tax / Insurance Proceeds"
    if matches_any(NSF_REVERSAL_PATTERNS, desc_upper):
        return "Non-Revenue - Refund / Reversal / NSF"
    for var_str, (tier, lender_name) in ALL_KNOWN_LENDERS.items():
        if re.search(r'\b' + re.escape(var_str) + r'\b', desc_upper):
            return "Non-Revenue - MCA / Loan Proceeds"
    return None


def detect_wash_pattern(df):
    if df.empty:
        return False, 0

    credit_refs = df[df['tx_type'] == 'credit']['description'].apply(
        lambda d: re.sub(r'[^A-Z0-9#\-]', '', str(d).upper())
    )
    debit_refs = df[df['tx_type'] == 'debit']['description'].apply(
        lambda d: re.sub(r'[^A-Z0-9#\-]', '', str(d).upper())
    )
    ref_pattern = re.compile(r'TF\d{3,4}#?\d{3,4}[\-#]\d{3,4}')
    c_refs = set(
        m.group(0)
        for d in credit_refs
        for m in [ref_pattern.search(d)]
        if m
    )
    d_refs = set(
        m.group(0)
        for d in debit_refs
        for m in [ref_pattern.search(d)]
        if m
    )

    overlap = c_refs & d_refs
    round_trip_count = 0
    for ref in overlap:
        round_trip_count += min(
            credit_refs.str.contains(re.escape(ref)).sum(),
            debit_refs.str.contains(re.escape(ref)).sum()
        )

    return round_trip_count >= 6, round_trip_count

tab1, tab2, tab3 = st.tabs(["Document Analyzer", "Bank Summary", "Underwriting Model"])

# ==============================================================================
# TAB 1: UNIVERSAL DYNAMIC RECON ENGINE & CREDIT EXTRACTOR
# ==============================================================================
with tab1:
    st.header("1. Document Analyzer")

    col_u1, col_u2 = st.columns(2)
    with col_u1:
        uploaded_files = st.file_uploader(
            "Upload Bank Statements (PDF)",
            type="pdf",
            accept_multiple_files=True
        )
    with col_u2:
        credit_file = st.file_uploader(
            "Upload Credit Report (PDF)",
            type="pdf",
            accept_multiple_files=False
        )

    opt_col1, opt_col2 = st.columns(2)
    with opt_col1:
        enable_ocr_option = st.checkbox(
            "Enable OCR text fallback",
            value=False,
            help="Uses bilingual English/French OCR when native PDF text is unavailable."
        )
    with opt_col2:
        enable_vision_option = st.checkbox(
            "Enable vision fallback for unreadable pages",
            value=bool(client),
            disabled=not bool(client),
            help=(
                "Uses the vision model only for pages that cannot be reliably "
                "read by native positioned extraction. Vision-derived rows "
                "still require reconciliation/review."
            ),
        )

    if credit_file and client:
        if st.button("🔍 Extract Credit", type="secondary"):
            with st.spinner("Extracting Credit..."):
                pdf_bytes = credit_file.getvalue()
                credit_text, pdf_errors = safe_pdf_text(pdf_bytes)

                for err in pdf_errors:
                    st.session_state.diagnostic_log.append(f"Credit PDF: {err}")

                if not credit_text:
                    st.error(
                        "Could not extract text from the credit-report PDF. "
                        "If it is a scanned/image PDF, install the optional OCR dependencies."
                    )
                else:
                    try:
                        profile = extract_credit_profile(
                            client=client,
                            credit_text=credit_text,
                            model=CREDIT_MODEL,
                        )
                        raw_credit = profile.model_dump()
                        raw_credit["is_loaded"] = True
                        st.session_state.credit_profile = raw_credit

                        fico_label = (
                            str(profile.fico_score)
                            if profile.fico_score is not None
                            else "not found"
                        )
                        st.success(
                            f"✅ Credit Profile Loaded for: "
                            f"{profile.owner_name or 'Unknown owner'} "
                            f"(FICO: {fico_label})"
                        )
                        if profile.warnings:
                            for warning in profile.warnings:
                                st.warning(f"Credit extraction: {warning}")
                    except Exception as exc:
                        st.error(f"Error extracting credit report: {exc}")

    if st.button("🚀 Process Statements", type="primary") and uploaded_files:
        status_text = st.empty()
        progress_bar = st.progress(0)
        st.session_state.diagnostic_log = []

        status_text.info("Step 1/3: Parsing and validating statements...")

        upload_payload = []
        for idx, uploaded in enumerate(uploaded_files):
            upload_payload.append((uploaded.name, uploaded.getvalue()))
            progress_bar.progress((idx + 1) / max(len(uploaded_files), 1))

        pipeline_result = analyze_statement_files(
            files=upload_payload,
            ai_client=client,
            vision_client=client,
            classifier_model=CLASSIFIER_MODEL,
            enable_ocr=enable_ocr_option,
            enable_vision_fallback=enable_vision_option,
            vision_model=VISION_MODEL,
        )

        coverage_records = []
        integrity_records = []
        expected_credits = 0.0
        anchor_count = 0

        for statement in pipeline_result.statements:
            statement_month = None
            if (
                statement.period_start
                and statement.period_end
                and statement.period_start.year == statement.period_end.year
                and statement.period_start.month == statement.period_end.month
            ):
                statement_month = statement.period_start.strftime("%Y-%m")

            coverage_records.append({
                "source_file": statement.source_file,
                "statement_id": statement.statement_id,
                "month": statement_month,
                "period_start": (
                    statement.period_start.isoformat()
                    if statement.period_start else None
                ),
                "period_end": (
                    statement.period_end.isoformat()
                    if statement.period_end else None
                ),
                "expected_days": (
                    statement.coverage.expected_days
                    if statement.coverage else None
                ),
                "observed_days": (
                    statement.coverage.observed_days
                    if statement.coverage else None
                ),
                "coverage_pct": (
                    statement.coverage.coverage_pct
                    if statement.coverage else None
                ),
                "status": (
                    statement.coverage.status.value
                    if statement.coverage else "UNKNOWN"
                ),
                "warning": (
                    statement.coverage.warning
                    if statement.coverage else
                    "Statement period could not be verified."
                ),
            })

            effective_integrity = (
                statement.composite_integrity or statement.integrity
            )
            integrity_records.append({
                "source_file": statement.source_file,
                "statement_id": statement.statement_id,
                "bank": statement.bank_name or statement.bank_id,
                "extraction_quality": (
                    statement.extraction_quality.status
                    if statement.extraction_quality else "UNKNOWN"
                ),
                "extraction_quality_score": (
                    statement.extraction_quality.score
                    if statement.extraction_quality else None
                ),
                "extraction_mode": (
                    statement.extraction_quality.extraction_mode
                    if statement.extraction_quality else None
                ),
                "score": (
                    effective_integrity.score
                    if effective_integrity else None
                ),
                "status": (
                    effective_integrity.status
                    if effective_integrity else "UNKNOWN"
                ),
                "page_count": statement.page_count,
                "findings": (
                    [
                        {
                            "code": finding.code,
                            "severity": finding.severity.value,
                            "message": finding.message,
                            "evidence": finding.evidence,
                        }
                        for finding in effective_integrity.findings
                    ]
                    if effective_integrity else []
                ),
            })

            if statement.credit_anchor is not None:
                expected_credits += float(statement.credit_anchor)
                anchor_count += 1

            for diagnostic in statement.diagnostics:
                st.session_state.diagnostic_log.append(
                    f"{statement.source_file}: {diagnostic}"
                )
            if statement.integrity:
                for finding in statement.integrity.findings:
                    st.session_state.diagnostic_log.append(
                        f"PDF integrity [{finding.severity.value}] "
                        f"{statement.source_file} {finding.code}: "
                        f"{finding.message}"
                    )

        for warning in pipeline_result.warnings:
            st.session_state.diagnostic_log.append(f"Pipeline: {warning}")

        st.session_state.expected_credits = expected_credits
        st.session_state.statement_coverage = coverage_records
        st.session_state.pdf_integrity_reports = integrity_records
        st.session_state.decision_readiness = (
            {
                "status": pipeline_result.decision_readiness.status.value,
                "automated_offer_allowed": (
                    pipeline_result.decision_readiness.automated_offer_allowed
                ),
                "blocking_reasons": list(
                    pipeline_result.decision_readiness.blocking_reasons
                ),
                "review_reasons": list(
                    pipeline_result.decision_readiness.review_reasons
                ),
                "checks": pipeline_result.decision_readiness.checks,
            }
            if pipeline_result.decision_readiness else None
        )
        st.session_state.revenue_baseline = (
            {
                "average_monthly_true_revenue": (
                    pipeline_result.revenue_baseline.average_monthly_true_revenue
                ),
                "months_used": list(pipeline_result.revenue_baseline.months_used),
                "partial_months_excluded": list(
                    pipeline_result.revenue_baseline.partial_months_excluded
                ),
                "basis": pipeline_result.revenue_baseline.basis,
                "warning": pipeline_result.revenue_baseline.warning,
            }
            if pipeline_result.revenue_baseline else None
        )
        st.session_state.mca_positions = [
            {
                "lender": position.lender,
                "tier": position.tier,
                "payment_amount": position.payment_amount,
                "frequency": position.frequency,
                "monthly_payment": position.monthly_payment,
            }
            for position in pipeline_result.mca_positions
        ]

        ledger_rows = []
        for transaction in pipeline_result.transactions:
            ledger_rows.append({
                "transaction_id": transaction.transaction_id,
                "statement_id": transaction.statement_id,
                "source_file": transaction.source_file,
                "source_page": transaction.source_page,
                "date": transaction.date,
                "month": transaction.date[:7],
                "description": transaction.description,
                "payer_or_source": transaction.description,
                "amount": transaction.amount,
                "tx_type": transaction.direction,
                "category": transaction.category,
                "classification_source": transaction.classification_source,
                "classification_reason": transaction.classification_reason,
                "classification_model": transaction.classification_model,
                "needs_review": transaction.needs_review,
                "is_revenue": transaction.is_true_revenue,
            })

        full_ledger_df = pd.DataFrame(ledger_rows)
        st.session_state.full_ledger = full_ledger_df

        if full_ledger_df.empty:
            st.session_state.transactions = None
            st.error(
                "No transactions were extracted. Review Extraction Diagnostics. "
                "For scanned/image-only statements, enable OCR in the production API."
            )
        else:
            credit_df = full_ledger_df[
                full_ledger_df["tx_type"] == "credit"
            ].copy().reset_index(drop=True)

            wash_detected, wash_ref_count = detect_wash_pattern(full_ledger_df)
            st.session_state["wash_detected_auto"] = wash_detected
            st.session_state["wash_ref_count"] = wash_ref_count
            if wash_detected:
                st.session_state.diagnostic_log.append(
                    f"🚨 Wash/round-trip pattern detected: {wash_ref_count} "
                    "matched debit/credit pairs sharing the same transfer reference."
                )

            st.session_state.transactions = credit_df

            partial_count = sum(
                1 for row in coverage_records
                if row.get("status") == "PARTIAL"
            )
            unknown_count = sum(
                1 for row in coverage_records
                if row.get("status") == "UNKNOWN"
            )
            integrity_review_count = sum(
                1 for row in integrity_records
                if row.get("status") not in ("LOW_CONCERN", None)
            )

            if partial_count:
                st.warning(
                    f"⚠️ {partial_count} partial statement(s) detected. Their "
                    "transactions remain visible, while verified complete months "
                    "are preferred for the underwriting revenue baseline."
                )
            if unknown_count:
                st.info(
                    f"ℹ️ Statement coverage could not be verified for "
                    f"{unknown_count} file(s)."
                )
            if integrity_review_count:
                st.warning(
                    f"🛡️ {integrity_review_count} statement file(s) contain "
                    "structural integrity signals requiring review. These signals "
                    "are not proof of fraud."
                )
            if pipeline_result.skipped_duplicates:
                st.warning(
                    "⚠️ Duplicate uploads skipped: "
                    + ", ".join(pipeline_result.skipped_duplicates)
                )

            if anchor_count < len(pipeline_result.statements):
                st.warning(
                    "⚠️ Extraction completed, but one or more statements did not "
                    "have a verifiable deposit-total anchor."
                )
            else:
                st.success("✅ Extraction and validation complete.")

        status_text.empty()
        progress_bar.empty()

    elif not uploaded_files:
        st.info("Upload one or more bank statement PDFs to begin.")

    with st.expander("🔍 Extraction Diagnostics"):
        if st.session_state.diagnostic_log:
            st.write(
                "Per-file parsing, calibration, fallback and classification log:"
            )
            for log in st.session_state.diagnostic_log:
                st.code(log)
        else:
            st.write("Awaiting document processing...")

    if (
        st.session_state.transactions is not None
        and not st.session_state.transactions.empty
    ):
        st.markdown("---")
        st.subheader("⚖️ Reconciliation")

        recon_df = st.session_state.transactions[
            st.session_state.transactions["tx_type"] == "credit"
        ]
        total_gross = recon_df["amount"].sum()
        expected_credits = st.session_state.expected_credits
        variance = abs(total_gross - expected_credits)

        r_col1, r_col2, r_col3 = st.columns(3)
        r_col1.metric(
            "Bank Summary / Fallback Anchor Total",
            f"${expected_credits:,.2f}"
        )
        r_col2.metric("Extracted Ledger Total", f"${total_gross:,.2f}")

        if expected_credits == 0.0:
            r_col3.metric(
                "Reconciliation Variance",
                "N/A",
                "Anchor Missing",
                delta_color="off"
            )
            st.warning(
                "⚠️ Anchor Warning: No reliable summary total could be found."
            )
        elif variance > 2.00:
            r_col3.metric(
                "Reconciliation Variance",
                f"${variance:,.2f}",
                "Mismatch Detected",
                delta_color="inverse"
            )
            st.error(
                f"🚨 Variance Detected: stated/derived anchor is "
                f"${expected_credits:,.2f}, extracted total is "
                f"${total_gross:,.2f}. Review Extraction Diagnostics."
            )
        else:
            r_col3.metric(
                "Reconciliation Variance",
                f"${variance:,.2f}",
                "Matched",
                delta_color="normal"
            )
            st.success(
                "✅ Reconciliation Passed: extracted deposits match the resolved total(s)."
            )

        st.markdown("---")
        st.subheader("True Revenue Reconciliation")
        st.caption(
            "Use the filters below to isolate transaction types. Toggle the "
            "checkboxes to reclassify items between True Revenue, Non-Revenue, and Review."
        )

        months_available = ["All"] + sorted(
            st.session_state.transactions["month"].dropna().unique().tolist()
        )
        categories_available = ["All"] + sorted(
            st.session_state.transactions["category"].dropna().unique().tolist()
        )

        col_f1, col_f2 = st.columns(2)
        with col_f1:
            selected_month = st.selectbox(
                "Filter by Month", options=months_available
            )
        with col_f2:
            selected_category = st.selectbox(
                "Filter by Category", options=categories_available
            )

        mask = pd.Series(True, index=st.session_state.transactions.index)
        if selected_month != "All":
            mask &= st.session_state.transactions["month"] == selected_month
        if selected_category != "All":
            mask &= st.session_state.transactions["category"] == selected_category

        filtered_df = st.session_state.transactions[mask]

        display_cols = [
            "date", "month", "description", "amount", "payer_or_source",
            "tx_type", "category", "classification_source",
            "classification_reason", "is_revenue", "needs_review"
        ]
        display_cols = [
            c for c in display_cols if c in filtered_df.columns
        ]

        edited_filtered_df = st.data_editor(
            filtered_df[display_cols],
            column_config={
                "is_revenue": st.column_config.CheckboxColumn("True Revenue?"),
                "needs_review": st.column_config.CheckboxColumn(
                    "Review Req?", disabled=True
                ),
                "amount": st.column_config.NumberColumn(
                    "Amount ($)", format="$%.2f"
                ),
                "date": st.column_config.TextColumn("Date"),
                "month": st.column_config.TextColumn("Month"),
                "category": st.column_config.TextColumn("Category"),
                "classification_source": st.column_config.TextColumn(
                    "Classified By", disabled=True
                ),
                "classification_reason": st.column_config.TextColumn(
                    "Classification Reason", disabled=True
                ),
                "payer_or_source": st.column_config.TextColumn("Payer / Source"),
                "description": st.column_config.TextColumn("Description"),
                "tx_type": st.column_config.TextColumn("Type", disabled=True),
            },
            disabled=[
                "date", "month", "amount", "description",
                "payer_or_source", "category", "tx_type",
                "classification_source", "classification_reason"
            ],
            width="stretch",
            num_rows="dynamic",
            key="main_editor"
        )
        st.session_state.transactions.update(edited_filtered_df)

        st.markdown("<br>", unsafe_allow_html=True)
        revenue_df = st.session_state.transactions[
            st.session_state.transactions["is_revenue"] == True
        ]
        review_df = st.session_state.transactions[
            st.session_state.transactions["needs_review"] == True
        ]

        total_true = revenue_df["amount"].sum()
        total_review = review_df["amount"].sum()

        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        kpi1.metric("Confirmed True Revenue", f"${total_true:,.2f}")
        kpi2.metric(
            "Revenue Under Review",
            f"${total_review:,.2f}",
            "Requires Manual Approval",
            delta_color="off"
        )

        baseline = st.session_state.get("revenue_baseline") or {}
        baseline_avg = baseline.get("average_monthly_true_revenue")
        if baseline_avg is None:
            num_active_months = (
                st.session_state.transactions["month"].nunique()
                if not st.session_state.transactions.empty else 1
            )
            baseline_avg = (
                total_true / num_active_months
                if num_active_months > 0 else 0.0
            )
        kpi3.metric(
            "Avg Monthly True Revenue",
            f"${baseline_avg:,.2f}"
        )
        if baseline.get("basis"):
            st.caption(
                f"Revenue baseline: {baseline['basis']} | "
                f"Months used: {', '.join(baseline.get('months_used', [])) or 'N/A'}"
            )
        kpi4.metric(
            "Non-Revenue Proportion",
            f"{((total_gross - total_true) / total_gross * 100 if total_gross > 0 else 0):.1f}%"
        )

        st.markdown("---")
        col_cat, col_mca = st.columns(2)

        with col_cat:
            st.markdown("#### Deposit Breakdown by Payer & Category")
            cat_summary = (
                st.session_state.transactions
                .groupby(["category", "payer_or_source"])
                .agg(Total=("amount", "sum"), Count=("amount", "count"))
                .reset_index()
            )
            cat_rev_status = (
                st.session_state.transactions
                .groupby(["category", "payer_or_source"])["is_revenue"]
                .agg(lambda x: bool(x.mode()[0]) if not x.empty else False)
                .reset_index()
            )
            cat_summary = pd.merge(
                cat_summary, cat_rev_status,
                on=["category", "payer_or_source"]
            )
            cat_summary = cat_summary.sort_values(
                by="Total", ascending=False
            ).reset_index(drop=True)

            cat_editor = st.data_editor(
                cat_summary,
                column_config={
                    "category": st.column_config.TextColumn(
                        "Category", disabled=True
                    ),
                    "payer_or_source": st.column_config.TextColumn(
                        "Payer / Source", disabled=True
                    ),
                    "is_revenue": st.column_config.CheckboxColumn(
                        "True Revenue?"
                    ),
                    "Count": st.column_config.NumberColumn(
                        "Count", disabled=True
                    ),
                    "Total": st.column_config.NumberColumn(
                        "Total ($)", format="$%.2f", disabled=True
                    )
                },
                key="bulk_cat_editor",
                width="stretch"
            )

            bulk_changed = False
            for _, r in cat_editor.iterrows():
                c_name = r["category"]
                p_name = r["payer_or_source"]
                c_status = r["is_revenue"]
                mask2 = (
                    (st.session_state.transactions["category"] == c_name)
                    &
                    (st.session_state.transactions["payer_or_source"] == p_name)
                )
                if not (
                    st.session_state.transactions.loc[mask2, "is_revenue"]
                    == c_status
                ).all():
                    st.session_state.transactions.loc[
                        mask2, "is_revenue"
                    ] = c_status
                    if c_status:
                        st.session_state.transactions.loc[
                            mask2, "needs_review"
                        ] = False
                    bulk_changed = True

            if bulk_changed:
                st.rerun()

        with col_mca:
            st.markdown("#### Active MCA Positions")
            mca_df = pd.DataFrame(st.session_state.mca_positions)
            if mca_df.empty:
                mca_df = pd.DataFrame(
                    columns=[
                        "lender", "tier", "frequency",
                        "payment_amount", "monthly_payment"
                    ]
                )

            edited_mca_df = st.data_editor(
                mca_df,
                column_config={
                    "lender": st.column_config.TextColumn(
                        "Lender Name", required=True
                    ),
                    "tier": st.column_config.SelectboxColumn(
                        "Tier",
                        options=["Premium", "Standard"],
                        required=True
                    ),
                    "frequency": st.column_config.SelectboxColumn(
                        "Frequency",
                        options=[
                            "Daily", "2-3x Weekly", "Weekly",
                            "Bi-Weekly", "Monthly"
                        ],
                        required=True
                    ),
                    "payment_amount": st.column_config.NumberColumn(
                        "Payment ($)", min_value=0.0,
                        format="$%.2f", required=True
                    ),
                    "monthly_payment": st.column_config.NumberColumn(
                        "Monthly Equiv ($)", disabled=True,
                        format="$%.2f"
                    )
                },
                num_rows="dynamic",
                width="stretch",
                key="mca_editor"
            )

            def calculate_monthly_equiv(row):
                freq = str(row.get("frequency", "Monthly"))
                amt = pd.to_numeric(
                    row.get("payment_amount"), errors="coerce"
                )
                amt = 0.0 if pd.isna(amt) else amt
                return (
                    amt * 21 if freq == "Daily"
                    else amt * 9 if freq == "2-3x Weekly"
                    else amt * 4.33 if freq == "Weekly"
                    else amt * 2.16 if freq == "Bi-Weekly"
                    else amt
                )

            if not edited_mca_df.empty:
                edited_mca_df["monthly_payment"] = edited_mca_df.apply(
                    calculate_monthly_equiv, axis=1
                )
                st.session_state.mca_positions = edited_mca_df.to_dict("records")
            else:
                st.session_state.mca_positions = []

# ============================================================================
# TAB 2 & 3: SUMMARY & SCORECARD
# ============================================================================
# TAB 2 & 3: SUMMARY & SCORECARD
# ==============================================================================
with tab2:
    if st.session_state.transactions is not None and not st.session_state.transactions.empty:
        st.header("🏦 Bank Statement Summary")

        if st.session_state.get("statement_coverage"):
            st.markdown("#### Statement Coverage")
            coverage_df = pd.DataFrame(st.session_state.statement_coverage)
            coverage_cols = [
                "source_file", "period_start", "period_end",
                "coverage_pct", "status", "warning"
            ]
            coverage_cols = [
                col for col in coverage_cols if col in coverage_df.columns
            ]
            st.dataframe(
                coverage_df[coverage_cols],
                width="stretch",
                hide_index=True,
            )

        if st.session_state.get("pdf_integrity_reports"):
            st.markdown("#### PDF Integrity Triage")
            integrity_df = pd.DataFrame(st.session_state.pdf_integrity_reports)
            integrity_cols = [
                "source_file", "score", "status", "page_count"
            ]
            st.dataframe(
                integrity_df[integrity_cols],
                width="stretch",
                hide_index=True,
            )
            st.caption(
                "Integrity scores are review signals only. They do not establish "
                "that a statement is fraudulent or altered."
            )

        df = st.session_state.transactions
        mca_df_raw = pd.DataFrame(st.session_state.mca_positions)

        summary_rows = []
        for month, group in df.groupby("month"):
            dep_group = group[group['tx_type'] == 'credit']
            rev_group = group[group["is_revenue"] == True]
            non_rev_group = dep_group[dep_group["is_revenue"] == False]
            loan_debits = sum([p.get("monthly_payment", 0.0) for p in st.session_state.mca_positions]) if not mca_df_raw.empty else 0.0

            summary_rows.append({
                "Month": month,
                "# Deposits": len(dep_group),
                "Total Deposits ($)": dep_group["amount"].sum(),
                "# Revenue": len(rev_group),
                "Total Revenue ($)": rev_group["amount"].sum(),
                "# Non Revenue": len(non_rev_group),
                "Total Non Revenue ($)": non_rev_group["amount"].sum(),
                "# Loan Debits": len(st.session_state.mca_positions) * 4 if not mca_df_raw.empty else 0,
                "Total Loan Debits ($)": loan_debits
            })

        summary_df = pd.DataFrame(summary_rows).sort_values("Month", ascending=False).reset_index(drop=True)
        st.dataframe(summary_df, width="stretch", hide_index=True)

    else:
        st.info("Upload and analyze bank statements in Tab 1 to generate the Bank Summary Dashboard.")

with tab3:
    st.header("Forward Funding Underwriting Model")

    cp = st.session_state.credit_profile
    default_public_records = "Clean"
    if cp.get("bankruptcies_found") is True:
        default_public_records = "Severe"
    elif (cp.get("active_collections_count") or 0) > 0:
        default_public_records = "Moderate"

    st.markdown("---")
    st.subheader("👤 Owner Credit Profile (Bureau Data)")

    fico_display = cp.get("fico_score")
    fico_display = fico_display if fico_display is not None else "Not found"
    util_display = (
        f"{cp.get('revolving_credit_utilization_pct')}%"
        if cp.get("revolving_credit_utilization_pct") is not None
        else "Not found"
    )
    high_credit_display = (
        f"${cp.get('total_high_credit'):,.2f}"
        if cp.get("total_high_credit") is not None
        else "Not found"
    )
    collections_count_display = (
        cp.get("active_collections_count")
        if cp.get("active_collections_count") is not None
        else "Not found"
    )
    collections_amount_display = (
        f"${cp.get('total_collections_amount'):,.2f}"
        if cp.get("total_collections_amount") is not None
        else "Not found"
    )
    mortgage_count_display = (
        cp.get("number_of_mortgages")
        if cp.get("number_of_mortgages") is not None
        else "Not found"
    )

    c_col1, c_col2, c_col3, c_col4 = st.columns(4)
    with c_col1:
        st.metric("Owner Name", cp.get("owner_name") or "Not found")
        st.metric("FICO Score", fico_display)
    with c_col2:
        st.metric("Revolving Utilization", util_display)
        st.metric("Reported High Credit", high_credit_display)
    with c_col3:
        active_collections = cp.get("active_collections_count")
        col_color = (
            "normal"
            if active_collections in (None, 0)
            else "inverse"
        )
        st.metric(
            "Active Collections",
            collections_count_display,
            delta=(
                "Review Required"
                if (active_collections or 0) > 0
                else ("Not extracted" if active_collections is None else "Clean")
            ),
            delta_color=col_color,
        )
        st.metric("Collections Amount", collections_amount_display)
    with c_col4:
        st.metric("Active Mortgages", mortgage_count_display)
        st.caption(
            f"**LTV Details:** {cp.get('mortgage_ltv_details') or 'Not found'}"
        )

    if cp.get("is_loaded") and cp.get("fico_score") is None:
        st.warning(
            "The credit report was processed, but no explicit FICO/Beacon score "
            "was found. The underwriting input below remains a manual field."
        )

    st.markdown("---")
    st.warning("###  MANUAL INPUT REQUIRED\n**These critical fields require human verification or external API integrations.**")
    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    with m_col1:
        time_in_biz = st.number_input("Time in Business (months)", min_value=0, max_value=1000, value=24)
        avg_daily_balance = st.number_input("Average Daily Balance (ADB) $", value=0.0)
    with m_col2:
        extracted_credit_score = cp.get("fico_score")
        credit_score = st.number_input(
            "Owner Credit Score (300-900)",
            min_value=300,
            max_value=900,
            value=int(extracted_credit_score) if extracted_credit_score is not None else 650,
            help=(
                "Uses the explicitly extracted bureau score when available. "
                "If no score was extracted, 650 is only an editable UI starting "
                "value and is not treated as verified bureau data."
            ),
        )
        negative_days = st.number_input("Actual Negative Days (Statement Count)", value=0)
    with m_col3:
        public_records = st.selectbox(
            "Public Records / Commercial Credit",
            options=["Clean", "Minor", "Moderate", "Severe"],
            index=["Clean", "Minor", "Moderate", "Severe"].index(default_public_records)
        )
        borrowing_velocity = st.selectbox("Recent Funding Velocity", ["0 in 90 Days", "1 in 90 Days", "2+ in 90 Days"])
    with m_col4:
        bank_verification = st.selectbox("Bank Data Verification", ["Bank Connect", "Original PDF", "Minor inconsistency", "Suspected manipulation"])

    st.markdown("---")
    st.markdown("### 🏢 INDUSTRY & BUSINESS PROFILE")
    selected_industry = st.selectbox("Select Business Industry (SIC)", options=list(INDUSTRY_SCORING.keys()))
    industry_score = INDUSTRY_SCORING[selected_industry]["points"]
    seasonality_score = INDUSTRY_SCORING[selected_industry]["seasonality"]

    st.markdown("---")

    # SAFE VARIABLE INITIALIZATION
    auto_avg_true_rev = 0.0
    auto_trend_pct = 0.0
    auto_deposit_count = 0
    auto_rev_volatility = 0.0
    auto_concentration_pct = 0.0
    auto_mca_positions = 0
    auto_mca_burden_pct = 0.0
    auto_payment_perf = 0
    partial_months_excluded = 0
    gross_deposits = 0.0
    median_deposit = 0.0
    largest_deposit = 0.0
    wash_transactions_detected = st.session_state.get('wash_detected_auto', False)

    if st.session_state.transactions is not None and not st.session_state.transactions.empty:
        df = st.session_state.transactions
        rev_tx = df[df["is_revenue"] == True]
        all_deposits_df = df[df['tx_type'] == 'credit']

        gross_deposits = all_deposits_df['amount'].sum()
        median_deposit = all_deposits_df['amount'].median() if not all_deposits_df.empty else 0.0
        largest_deposit = all_deposits_df['amount'].max() if not all_deposits_df.empty else 0.0

        monthly_rev_series = rev_tx.groupby("month")["amount"].sum().sort_index()
        monthly_count_series = rev_tx.groupby("month")["amount"].count().sort_index()

        coverage_by_month = {
            row.get("month"): row
            for row in st.session_state.get("statement_coverage", [])
            if row.get("month")
        }
        complete_months = {
            month
            for month, row in coverage_by_month.items()
            if row.get("status") == "COMPLETE"
        }
        partial_months = {
            month
            for month, row in coverage_by_month.items()
            if row.get("status") == "PARTIAL"
        }

        underwriting_rev_series = monthly_rev_series
        underwriting_count_series = monthly_count_series
        if complete_months:
            underwriting_rev_series = monthly_rev_series[
                monthly_rev_series.index.isin(complete_months)
            ]
            underwriting_count_series = monthly_count_series[
                monthly_count_series.index.isin(complete_months)
            ]
            partial_months_excluded = len(
                set(monthly_rev_series.index).intersection(partial_months)
            )

        num_months = len(underwriting_rev_series) if len(underwriting_rev_series) > 0 else 1

        auto_avg_true_rev = (
            float(underwriting_rev_series.mean())
            if not underwriting_rev_series.empty else 0.0
        )
        auto_deposit_count = (
            int(round(underwriting_count_series.mean()))
            if not underwriting_count_series.empty else 0
        )

        if num_months > 1 and auto_avg_true_rev > 0:
            auto_rev_volatility = float(
                (underwriting_rev_series.std() / auto_avg_true_rev) * 100
            )
        if len(underwriting_rev_series) >= 2:
            m_start = underwriting_rev_series.iloc[0]
            m_end = underwriting_rev_series.iloc[-1]
            auto_trend_pct = (
                float(((m_end - m_start) / m_start) * 100)
                if m_start > 0 else 0.0
            )

        total_rev = rev_tx["amount"].sum()
        if total_rev > 0:
            top_payer_sum = rev_tx.groupby("payer_or_source")["amount"].sum().max()
            auto_concentration_pct = float((top_payer_sum / total_rev) * 100)

        auto_mca_positions = len(st.session_state.mca_positions)
        total_mca_monthly = sum([p.get("monthly_payment", 0.0) for p in st.session_state.mca_positions])
        auto_mca_burden_pct = float((total_mca_monthly / auto_avg_true_rev) * 100) if auto_avg_true_rev > 0 else 0.0
        revenue_coverage_ratio = float(auto_avg_true_rev / total_mca_monthly) if total_mca_monthly > 0 else 99.9

        wash_df = df[df["category"].str.contains("Wash", case=False, na=False)]
        if len(wash_df) >= 3:
            wash_transactions_detected = True

        full_ledger = st.session_state.get("full_ledger")
        if full_ledger is not None and not full_ledger.empty:
            nsf_mask = full_ledger["description"].str.contains(
                r"\bNSF\b|RETURNED\s+ITEM|ITEM\s+RETURNED|"
                r"\bUNPAID\b|DISHONOURED|FRAIS\s+EFFET\s+RET",
                case=False,
                regex=True,
                na=False,
            )
            auto_payment_perf = int(nsf_mask.sum())
        else:
            auto_payment_perf = 0

    st.success("### 🤖 AUTOMATED FINANCIAL metrics \n**These fields are dynamically calculated by the transaction ledger.**")
    if partial_months_excluded:
        st.warning(
            f"⚠️ {partial_months_excluded} partial month(s) were excluded from "
            "Avg Monthly True Revenue, trend, volatility, and average deposit count. "
            "Their observed transactions remain visible in the ledger and Bank Summary."
        )
    a_col1, a_col2, a_col3, a_col4 = st.columns(4)

    with a_col1:
        st.number_input("Gross Extracted Deposits ($)", value=round(gross_deposits, 2), disabled=True)
        st.number_input("Avg Monthly True Revenue ($)", value=round(auto_avg_true_rev, 2), disabled=True)
        st.number_input("Revenue Trend %", value=round(auto_trend_pct, 1), disabled=True)

    with a_col2:
        st.number_input("Avg Deposit Count / Month", value=int(auto_deposit_count), disabled=True)
        st.number_input("Median Deposit Size ($)", value=round(median_deposit, 2), disabled=True)
        st.number_input("Largest Single Deposit ($)", value=round(largest_deposit, 2), disabled=True)

    with a_col3:
        st.number_input("Revenue Concentration %", value=round(auto_concentration_pct, 1), disabled=True)
        st.number_input("Revenue Volatility (CV) %", value=round(auto_rev_volatility, 1), disabled=True)
        st.number_input("Returned ACH / Missed Payments", value=int(auto_payment_perf), disabled=True)

    with a_col4:
        st.number_input("Existing MCA Positions", value=int(auto_mca_positions), disabled=True)
        st.number_input("Existing MCA Payment Burden %", value=round(auto_mca_burden_pct, 1), disabled=True)
        st.number_input("Revenue Coverage Ratio (X)", value=round(revenue_coverage_ratio, 2) if 'revenue_coverage_ratio' in locals() else 0.0, disabled=True)

    st.markdown("---")
    st.subheader("🛡️ Hard-Stop & Override")
    h_col1, h_col2 = st.columns(2)
    with h_col1:
        fraud_suspected = st.checkbox("Suspected altered statements / fraud?")
        wash_flag = st.checkbox("Severe Wash Transactions detected?", value=wash_transactions_detected)
    with h_col2:
        active_default = st.checkbox("Active lender default / collections?")

    scorecard_result = calculate_scorecard(
        ScorecardInputs(
            average_monthly_true_revenue=auto_avg_true_rev,
            revenue_trend_pct=auto_trend_pct,
            average_deposit_count=int(auto_deposit_count),
            revenue_volatility_pct=auto_rev_volatility,
            average_daily_balance=float(avg_daily_balance),
            mca_position_count=int(auto_mca_positions),
            mca_burden_pct=auto_mca_burden_pct,
            borrowing_velocity=borrowing_velocity,
            returned_ach_or_missed_payments=int(auto_payment_perf),
            negative_days=int(negative_days),
            time_in_business_months=int(time_in_biz),
            industry_score=int(industry_score),
            seasonality_score=int(seasonality_score),
            credit_score=int(credit_score),
            public_records=public_records,
            bank_verification=bank_verification,
            revenue_concentration_pct=auto_concentration_pct,
            suspected_fraud=fraud_suspected,
            severe_wash_transactions=wash_flag,
            active_lender_default=active_default,
        )
    )

    if scorecard_result.hard_stop:
        st.error(
            "🚨 **POLICY HARD STOP / AUTO DECLINE**: "
            + ", ".join(scorecard_result.hard_stop_reasons)
        )
    else:
        score = scorecard_result.score
        grade = scorecard_result.grade
        risk = scorecard_result.risk_tier
        advance = scorecard_result.revenue_advance_multiple
        max_burden = scorecard_result.max_total_debt_burden_pct / 100.0

        max_advance_dollars = auto_avg_true_rev * advance
        remaining_monthly_capacity = max(
            0.0,
            (auto_avg_true_rev * max_burden)
            - (auto_avg_true_rev * (auto_mca_burden_pct / 100)),
        )
        affordable_daily_payment = remaining_monthly_capacity / 21

        st.markdown("### 🏆 Underwriting Score & Offer Structuring")
        r1, r2, r3, r4 = st.columns(4)
        r1.metric(
            "Overall Score",
            f"{score} / {scorecard_result.max_score}"
        )
        r2.metric("Score Grade", grade)
        r3.metric("Risk Tier", risk)
        r4.metric("Suggested Max Advance %", f"{advance * 100:.0f}%")

        s1, s2, s3 = st.columns(3)
        s1.metric("Suggested Max Advance ($)", f"${max_advance_dollars:,.2f}")
        s2.metric(
            "Remaining Monthly Debt Capacity ($)",
            f"${remaining_monthly_capacity:,.2f}",
        )
        s3.metric(
            "Affordable Daily Payment (21 days)",
            f"${affordable_daily_payment:,.2f}",
        )

        with st.expander("Scorecard breakdown"):
            breakdown_df = pd.DataFrame(
                [
                    {"Component": key.replace("_", " ").title(), "Points": value}
                    for key, value in scorecard_result.breakdown.items()
                ]
            )
            st.dataframe(breakdown_df, hide_index=True, width="stretch")
            st.caption(
                f"Policy version: {scorecard_result.policy_version}. "
                f"Current configured maximum score: "
                f"{scorecard_result.max_score}."
            )
