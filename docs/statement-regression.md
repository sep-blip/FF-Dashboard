# Bank-statement regression testing

Production reliability should be measured against a private golden corpus of
real, redacted bank statements rather than by visual inspection of the UI.

Do not commit real merchant statements to this repository.

Create a local directory such as regression_cases/ and place a redacted PDF
plus a matching *.expected.json manifest for each test case.

Example manifest:

    {
      "source_file": "rbc_business_aug_2026.pdf",
      "bank_id": "RBC",
      "period_start": "2026-08-01",
      "period_end": "2026-08-31",
      "transaction_count": 42,
      "credit_total": 185432.10,
      "debit_total": 171004.33,
      "reconciliation_status": "PASS",
      "minimum_transaction_recall": 1.0,
      "transactions": [
        {
          "date": "2026-08-05",
          "direction": "credit",
          "amount": 8421.32,
          "description_contains": "STRIPE"
        }
      ]
    }

Run:

    python tools/run_statement_regression.py regression_cases

For scanned statements:

    python tools/run_statement_regression.py regression_cases --ocr

The regression suite checks bank detection, statement dates, transaction
counts, credit/debit totals, explicit expected transactions and reconciliation.
The intended production target is exact amount/date extraction with no silent
ledger variance. Classification accuracy should be measured separately against
human-labeled categories.
