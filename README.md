## Forward Funding: Underwriting Engine

An automated, production-grade underwriting engine built for Merchant Cash Advance (MCA) risk assessment. This system utilizes a hybrid deterministic-probabilistic architecture to ingest raw bank statements, dynamically map columns, reconcile ledger math, classify revenue streams, and generate a comprehensive credit scorecard.

---

## System Architecture & Layout

The engine operates on a multi-layered pipeline, moving from raw document ingestion through dynamic spatial extraction, and finally into semantic AI classification and risk scoring.

```text
[ Document Input ] (Bank Statements & Credit Reports)
        │
        ▼
[ Ingestion & Profiling Layer ]
   ├─ FICO & Bureau Extractor (OpenAI GPT-4o-mini)
   ├─ Multi-Entity Detector (Regex Account/Name Isolation)
   └─ Hash-Based Deduplication (SHA-256 Byte-Level Dedup)
        │
        ▼
[ Universal Dynamic Spatial Engine ] (pdfplumber)
   ├─ Dynamic Header Hunting (Locates X-coordinates for Withdrawn/Deposited)
   ├─ Strict Balance Cordoning (Prevents running balances from being extracted)
   ├─ Line-by-Line Math Extraction (Row reconstruction)
   └─ Date/Chronology Normalization
        │
        ▼
[ Semantic Classification & Filtering Layer ]
   ├─ Deterministic Pass 1: Wash/Round-Trip Detection
   ├─ Deterministic Pass 2: POS Processors (Stripe, Klarna, PayPal, etc.)
   ├─ Deterministic Pass 3: Gov/Tax/Insurance & NSF Reversals
   └─ Probabilistic AI Pass: OpenAI GPT-4o-mini (Strict JSON Schema)
        │
        ▼
[ Mathematical Reconciliation & Review ]
   ├─ Automated Bank Summary Anchor Mapping
   ├─ Interactive Underwriter Review Queue
   └─ Bulk Toggle Category Overrides
        │
        ▼
[ Scorecard & Offer Engine ]
   ├─ Cash Flow Metrics (Avg True Revenue, Volatility, MCA Burden)
   ├─ Risk Grading (A+ to E)
   └─ Deal Structuring (Max Advance & Daily Payment Limits)

- Core Features
Universal Dynamic Spatial Parser: Bypasses the need for hardcoded pixel ranges. The engine actively hunts for table headers ("Deposited", "Withdrawn", "Balance") on a per-page basis to construct temporary spatial grids, allowing it to easily read non-standard or wide-format printouts (like TD EasyWeb).

Running Balance Cordoning: Drops a rigid vertical wall immediately before the running balance column, preventing the engine from confusing active balances with massive customer deposits.

Canadian POS & BNPL Recognition: Includes an extensive regex net that instantly categorizes Moneris, Stripe, Square, Klarna, Amazon, and PayPal deposits, as well as VI/MC card settlements, directly into "True Revenue" without expending LLM tokens.

Automated Fraud & Wash Detection: Identifies recurring transfer signatures (e.g., TF 3978#1967-174) in both the credit and debit columns to catch account-kiting and artificial revenue inflation.

Underwriter Triage UI: Features a review queue that isolates unidentified transactions, allowing underwriters to quickly flip unmapped deposits to True Revenue with a single checkbox.

- Tech Stack
Frontend & Routing: Streamlit

Data Processing: Pandas

Document Ingestion: pdfplumber

Semantic Engine: OpenAI API (gpt-4o-mini)

Hashing & Logic: Python standard libraries (hashlib, re, difflib)

-Installation & Setup
Clone the repository:

Bash
git clone [https://github.com/yourusername/forward-funding-engine.git](https://github.com/yourusername/forward-funding-engine.git)
cd forward-funding-engine
Install the required dependencies:
Ensure you have Python 3.9+ installed, then run:

Bash
pip install -r requirements.txt
Configure your OpenAI API Key:
The engine requires an active OpenAI API key to process ambiguous transactions and extract FICO scores. Create a hidden .streamlit/secrets.toml file in the root directory:

Ini, TOML
OPENAI_API_KEY = "sk-your-openai-api-key-here"
Run the application:

Bash
streamlit run app.py

-Usage Guide
Upload Documents: Start by dropping up to 12 months of PDF bank statements and 1 PDF Credit Report into the primary ingestion blocks.

Extract Bureau Data: Click Extract Credit Profile to automatically pull FICO scores, utilization percentages, and active collection counts.

Run the Spatial Engine: Click Process Ledger to trigger the spatial extraction, classification, and reconciliation pipeline.

Reconcile: Verify the mathematical variance between the extracted ledger and the bank's summary anchors. If the variance is $0.00, proceed to review.

Classify: Navigate to the Interactive True Revenue Reconciliation table. Review the unclassified transactions and use the checkboxes to manually authorize them as revenue.

Structure the Deal: Open the Scorecard & Offer Engine tab, input the remaining manual fields (Time in Business, Verification status), and review the final algorithmic grade, suggested max advance, and affordable daily payment limit.