from __future__ import annotations

import argparse
import json
from pathlib import Path

from engine_v2.regression import compare_statement_to_manifest
from engine_v2.statement_parser import parse_statement_pdf


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run bank-statement extraction regression cases."
    )
    parser.add_argument(
        "cases_dir",
        type=Path,
        help=(
            "Directory containing *.expected.json manifests and the PDF named "
            "by each manifest's source_file field."
        ),
    )
    parser.add_argument(
        "--ocr",
        action="store_true",
        help="Enable OCR fallback during regression parsing.",
    )
    args = parser.parse_args()

    manifests = sorted(args.cases_dir.glob("*.expected.json"))
    if not manifests:
        raise SystemExit(
            f"No *.expected.json regression manifests found in {args.cases_dir}"
        )

    failed = 0
    summaries = []

    for manifest_path in manifests:
        manifest = json.loads(
            manifest_path.read_text(encoding="utf-8")
        )
        source_file = manifest.get("source_file")
        if not source_file:
            raise SystemExit(
                f"{manifest_path}: source_file is required."
            )

        pdf_path = args.cases_dir / source_file
        if not pdf_path.exists():
            raise SystemExit(
                f"{manifest_path}: source PDF does not exist: {pdf_path}"
            )

        statement = parse_statement_pdf(
            pdf_path.read_bytes(),
            source_file=pdf_path.name,
            enable_ocr=args.ocr,
        )
        result = compare_statement_to_manifest(
            case_name=manifest_path.stem,
            statement=statement,
            manifest=manifest,
        )

        if not result.passed:
            failed += 1

        summaries.append(
            {
                "case": result.case_name,
                "passed": result.passed,
                "transaction_recall": round(
                    result.transaction_recall,
                    4,
                ),
                "actual_transaction_count": (
                    result.actual_transaction_count
                ),
                "mismatches": [
                    {
                        "code": mismatch.code,
                        "message": mismatch.message,
                    }
                    for mismatch in result.mismatches
                ],
            }
        )

    print(json.dumps(summaries, indent=2))

    if failed:
        raise SystemExit(
            f"{failed}/{len(summaries)} regression cases failed."
        )


if __name__ == "__main__":
    main()
