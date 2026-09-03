import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import pdfplumber
import io
import json
import re
import hashlib
from openai import OpenAI

# --- CONFIGURATION ---
st.set_page_config(page_title="Forward Funding - Underwriting ", layout="wide")
st.title("📊 Forward Funding: Financial & Underwriting Engine")

# --- API KEY MANAGEMENT ---
try:
    api_key = st.secrets["OPENAI_API_KEY"]
except (FileNotFoundError, KeyError):
    api_key = st.sidebar.text_input("Enter OpenAI API Key (or configure secrets.toml)", type="password")

client = OpenAI(api_key=api_key) if api_key else None

# --- INDUSTRY SCORING DICTIONARY (FROM MATRIX) ---
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
        "owner_name": "Unknown",
        "fico_score": 650,
        "total_high_credit": 0.0,
        "revolving_credit_utilization_pct": 0.0,
        "active_collections_count": 0,
        "total_collections_amount": 0.0,
        "bankruptcies_found": False,
        "number_of_mortgages": 0,
        "mortgage_ltv_details": "N/A",
        "is_loaded": False
    }
if 'diagnostic_log' not in st.session_state:
    st.session_state.diagnostic_log = []
if 'entity_warning' not in st.session_state:
    st.session_state.entity_warning = None
if 'file_signatures' not in st.session_state:
    st.session_state.file_signatures = {}

tab1, tab2, tab3 = st.tabs(["📋 Document & Recon Engine", "🏦 Transaction Classifier", "🧮 Scorecard & Offer Engine"])

# ==============================================================================
# HELPERS
# ==============================================================================

def normalize_name(name):
    if not name:
        return ""
    return re.sub(r'[^A-Z0-9]', '', name.upper())


def extract_account_identity(full_pdf_text):
    """
    Pulls account holder name / business name and account number out of a
    statement so we can detect when a batch mixes more than one entity.
    Works across the 'Account Holder:', 'Business name:', and bare
    letterhead-name layouts seen across BMO / RBC / TD / aggregator exports.
    """
    holder = None
    acct_num = None

    m = re.search(r'Account Holder:\s*([^\n]+)', full_pdf_text, re.IGNORECASE)
    if m:
        holder = m.group(1).strip()

    if not holder:
        m = re.search(r'Business name:\s*\n?\s*([^\n]+)', full_pdf_text, re.IGNORECASE)
        if m:
            holder = m.group(1).strip()

    if not holder:
        # Fallback: RBC / TD style letterhead - first ALL-CAPS-ish line near
        # the top that isn't a bank name / boilerplate header.
        lines = [l.strip() for l in full_pdf_text.split("\n") if l.strip()][:30]
        skip_words = ["ROYAL BANK", "BANK OF MONTREAL", "TD", "BUSINESS BANKING",
                      "ACCOUNT STATEMENT", "BANQUE NATIONALE", "SCOTIABANK", "CIBC",
                      "STATEMENT", "PAGE", "ACCOUNT SUMMARY", "BRANCH"]
        for l in lines:
            if "_" in l: continue # Bypass alphanumeric routing codes (e.g. TDCDA71400_5164975_004)
            if re.match(r'^\d', l) or " ST " in l.upper() or " AVE " in l.upper() or " ON " in l.upper() or " BC " in l.upper(): continue # Bypass street addresses
            if len(l) > 3 and l.upper() == l and not any(sw in l.upper() for sw in skip_words) \
               and not re.match(r'^[\d\s\-\.\$,]+$', l):
                holder = l
                break

    m = re.search(r'Account\s*#\s*:?\s*(\d{4,})', full_pdf_text)
    if m:
        acct_num = m.group(1)
    if not acct_num:
        m = re.search(r'Account\s+number:?\s*([\d\s\-]{6,})', full_pdf_text, re.IGNORECASE)
        if m:
            acct_num = re.sub(r'\D', '', m.group(1))

    return holder, acct_num


def extract_opening_closing_balance(full_pdf_text):
    """
    Universal fallback anchor: every Canadian bank statement prints an
    opening and closing (or 'current') balance somewhere, even when the
    "Total amounts credited" style summary line isn't present (e.g. the
    aggregator/open-banking export format that has no summary line at all).
    """
    opening, closing = None, None

    m = re.search(r'Opening\s+balance\s*(?:on[^\d\n]*)?[:\s]*\$?\s*([\-\d,]+\.\d{2})', full_pdf_text, re.IGNORECASE)
    if m:
        opening = float(m.group(1).replace(',', ''))

    m = re.search(r'Closing\s+balance\s*(?:on[^\d\n]*)?[:\s]*=?\s*\$?\s*([\-\d,]+\.\d{2})', full_pdf_text, re.IGNORECASE)
    if m:
        closing = float(m.group(1).replace(',', ''))

    if closing is None:
        m = re.search(r'Current\s+Balance:?\s*(?:CA)?\$?\s*([\-\d,]+\.\d{2})', full_pdf_text, re.IGNORECASE)
        if m:
            closing = float(m.group(1).replace(',', ''))

    return opening, closing


def matches_any(patterns, text_upper):
    return any(re.search(p, text_upper) for p in patterns)


def rule_based_category(desc_upper, max_amount=None):
    """
    Deterministic pre-classification pass, applied BEFORE the LLM call.
    Catches the high-confidence, structurally-obvious cases so the model
    only has to adjudicate genuinely ambiguous descriptions. Returns None
    if no rule matches (falls through to the AI classifier).
    """
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
    """
    Rule-based wash/kiting detector: flags accounts where the SAME transfer
    reference (e.g. 'TF 3978#1967-174') appears as both a large debit and a
    large credit within the same statement, repeatedly, in a way consistent
    with round-tripping funds to inflate apparent deposit activity or to
    mask a negative running balance. This does not depend on the LLM
    assigning a 'Wash' category (which the schema does define but the model
    may not reliably choose), so the hard-stop can actually fire.
    """
    if df.empty:
        return False, 0
    credit_refs = df[df['tx_type'] == 'credit']['description'].apply(
        lambda d: re.sub(r'[^A-Z0-9#\-]', '', str(d).upper())
    )
    debit_refs = df[df['tx_type'] == 'debit']['description'].apply(
        lambda d: re.sub(r'[^A-Z0-9#\-]', '', str(d).upper())
    )
    ref_pattern = re.compile(r'TF\d{3,4}#?\d{3,4}[\-#]\d{3,4}')
    c_refs = set(m.group(0) for d in credit_refs for m in [ref_pattern.search(d)] if m)
    d_refs = set(m.group(0) for d in debit_refs for m in [ref_pattern.search(d)] if m)
    overlap = c_refs & d_refs
    round_trip_count = 0
    for ref in overlap:
        c_count = credit_refs.str.contains(re.escape(ref)).sum()
        d_count = debit_refs.str.contains(re.escape(ref)).sum()
        round_trip_count += min(c_count, d_count)
    return round_trip_count >= 6, round_trip_count


# ==============================================================================
# TAB 1: UNIVERSAL DYNAMIC RECON ENGINE & CREDIT EXTRACTOR
# ==============================================================================
with tab1:
    st.header("1. Document Ingestion & Universal Dynamic Recon Engine")

    col_u1, col_u2 = st.columns(2)
    with col_u1:
        uploaded_files = st.file_uploader("Upload Bank Statements (PDF)", type="pdf", accept_multiple_files=True)
    with col_u2:
        credit_file = st.file_uploader("Upload Credit Report (Equifax/TransUnion PDF)", type="pdf", accept_multiple_files=False)

    if credit_file and client:
        if st.button("🔍 Extract Credit Profile", type="secondary"):
            with st.spinner("Extracting FICO & Bureau Data..."):
                pdf_bytes = credit_file.read()
                with pdfplumber.open(io.BytesIO(pdf_bytes)) as doc:
                    credit_text = "\n".join([page.extract_text() or "" for page in doc.pages])

                try:
                    credit_response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": "You extract key underwriting metrics from raw credit bureau PDFs. Check the Credit Portfolio Insights table for utilization and mortgage counts. Do not hallucinate property values for LTV if missing. For total_high_credit, extract ONLY the exact value shown for 'High Credit' or 'HighCred'. DO NOT sum limits together."},
                            {"role": "user", "content": credit_text}
                        ],
                        temperature=0.0,
                        response_format=CREDIT_REPORT_SCHEMA,
                        timeout=30.0
                    )
                    raw_credit = json.loads(credit_response.choices[0].message.content)
                    raw_credit["is_loaded"] = True
                    st.session_state.credit_profile = raw_credit
                    st.success(f"✅ Credit Profile Loaded for: {raw_credit['owner_name']} (FICO: {raw_credit['fico_score']})")
                except Exception as e:
                    st.error(f"Error extracting credit report: {str(e)}")

    if st.button("🚀 Process Ledger (Dynamic Engine)", type="primary") and uploaded_files:
        status_text = st.empty()
        progress_bar = st.progress(0)

        all_deposits = []
        all_mca_debits = []
        total_anchor_credits = 0.0
        anchor_source_count = 0
        fallback_anchor_used = 0
        st.session_state.diagnostic_log = []
        st.session_state.entity_warning = None

        entities_seen = {}   # normalized_name -> {"display": ..., "files": [...]}
        file_hashes_seen = {}  # sha256 -> filename (for dedup)
        skipped_duplicate_files = []

        month_map = {
            "JAN": "01", "FEB": "02", "MAR": "03", "APR": "04", "MAY": "05", "JUN": "06",
            "JUL": "07", "AUG": "08", "SEP": "09", "OCT": "10", "NOV": "11", "DEC": "12"
        }

        status_text.info("Step 1/3: Parsing layouts and building mathematical ledger...")

        for f_idx, f in enumerate(uploaded_files):
            pdf_bytes = f.read()

            # --- FILE-LEVEL DEDUP (catches the same statement re-uploaded under a
            # different auto-incremented filename, e.g. "bank_stmt (2).pdf") ---
            file_hash = hashlib.sha256(pdf_bytes).hexdigest()
            if file_hash in file_hashes_seen:
                skipped_duplicate_files.append(f.name)
                st.session_state.diagnostic_log.append(
                    f"⚠️ {f.name}: SKIPPED - byte-identical duplicate of {file_hashes_seen[file_hash]}"
                )
                progress_bar.progress((f_idx + 1) / len(uploaded_files))
                continue
            file_hashes_seen[file_hash] = f.name

            with pdfplumber.open(io.BytesIO(pdf_bytes)) as doc:
                full_pdf_text = "\n".join([page.extract_text() or "" for page in doc.pages])

                # --- MULTI-ENTITY DETECTION ---
                holder_name, acct_num = extract_account_identity(full_pdf_text)
                entity_key = normalize_name(holder_name) if holder_name else f"UNKNOWN_{f.name}"
                if entity_key not in entities_seen:
                    entities_seen[entity_key] = {"display": holder_name or "Unknown", "files": []}
                entities_seen[entity_key]["files"].append(f.name)

                is_nbc = "BANQUE NATIONALE" in full_pdf_text.upper()

                # --- ACCURATE SUMMARY ANCHOR EXTRACTION (bank-specific first) ---
                bmo_credited_matches = re.findall(r'Total\s+amounts\s+credited\s*\(\$\)[^\d\n]*\+?\s*([\d,]+\.\d{2})', full_pdf_text, re.IGNORECASE)
                bmo_closing_matches = re.findall(r'Closing\s+totals[\s\S]*?[\d,]+\.\d{2}\s+([\d,]+\.\d{2})', full_pdf_text, re.IGNORECASE)
                rbc_matches = re.findall(r'Total\s+deposits\s*&\s*credits\s*\(\d+\)[^\d]*\+?\s*([\d,]+\.\d{2})', full_pdf_text, re.IGNORECASE)
                td_matches = re.findall(r'Total[^\d\n]*[\d,]+\.\d{2}[^\d\n]*([\d,]+\.\d{2})', full_pdf_text, re.IGNORECASE)

                file_anchor = 0.0
                anchor_method = None

                if bmo_credited_matches:
                    file_anchor = sum(float(m.replace(',', '')) for m in bmo_credited_matches)
                    anchor_method = "BMO: Total amounts credited"
                elif bmo_closing_matches:
                    file_anchor = sum(float(m.replace(',', '')) for m in bmo_closing_matches)
                    anchor_method = "BMO: Closing totals"
                elif rbc_matches:
                    file_anchor = sum(float(m.replace(',', '')) for m in rbc_matches)
                    anchor_method = "RBC: Total deposits & credits"
                elif td_matches and "Amounts deposited" not in full_pdf_text:
                    file_anchor = sum(float(m.replace(',', '')) for m in td_matches)
                    anchor_method = "TD/generic: Total line"

                # --- UNIVERSAL FALLBACK ANCHOR ---
                # If no bank-specific summary phrase was found (e.g. aggregator /
                # open-banking exports with no printed "Total" line at all), derive
                # the expected net credit total from Opening/Closing balance plus
                # the debits we extract, so reconciliation still has something
                # meaningful to check against instead of silently contributing $0.
                opening_bal, closing_bal = extract_opening_closing_balance(full_pdf_text)
                needs_fallback = (anchor_method is None) and (opening_bal is not None) and (closing_bal is not None)

                if anchor_method:
                    total_anchor_credits += file_anchor
                    anchor_source_count += 1
                    st.session_state.diagnostic_log.append(
                        f"✅ {f.name}: Anchor found via [{anchor_method}] = ${file_anchor:,.2f}"
                    )
                elif needs_fallback:
                    fallback_anchor_used += 1
                    st.session_state.diagnostic_log.append(
                        f"↪️ {f.name}: No printed summary total detected. Using Opening/Closing "
                        f"balance fallback (resolved after debits are tallied below)."
                    )
                else:
                    st.session_state.diagnostic_log.append(
                        f"🚨 {f.name}: NO anchor total found (no summary line, no opening/closing "
                        f"balance detected). Reconciliation for this file will be unverifiable."
                    )

                # --- STRICT YEAR BOUNDARY FIX ---
                year_match = re.search(r'\b(201[5-9]|202[0-9])\b', full_pdf_text)
                year = year_match.group(0) if year_match else "2026"

                active_date = None
                active_month = None

                # --- PERSISTENT CALIBRATION ACROSS ALL PAGES OF A DOCUMENT ---
                debit_x_min, debit_x_max = 200, 370
                credit_x_min, credit_x_max = 370, 460
                desc_x_limit = 200
                balance_x_min = 460

                file_debit_total = 0.0  # tracked for the opening/closing fallback anchor

                for page_num, page in enumerate(doc.pages):
                    raw_words = page.extract_words(x_tolerance=2, y_tolerance=3)
                    seen_coords = set()
                    lines = []

                    for w in raw_words:
                        if w['text'].lower() in ["balance", "balance($)", "balance(s)"]:
                            balance_x_min = w['x0'] - 10
                            credit_x_max = balance_x_min - 5
                            break

                    for w in raw_words:
                        x0, y0, word = w['x0'], w['top'], w['text']
                        coord_key = (round(x0, 1), round(y0, 1), word)
                        if coord_key not in seen_coords:
                            seen_coords.add(coord_key)
                            lines.append((x0, y0, word))

                    line_dict = {}
                    for w in lines:
                        x0, y0, word = w
                        y_key = round(y0 / 3.5) * 3.5
                        if y_key not in line_dict: line_dict[y_key] = []
                        line_dict[y_key].append((x0, word))

                    # Build a merged-header lookahead so wrapped headers
                    # ("Amounts" on one line, "withdrawn ($)" on the next) still
                    # trigger recalibration.
                    sorted_y_keys = sorted(line_dict.keys())
                    for yk_idx, y_key in enumerate(sorted_y_keys):
                        sorted_words = sorted(line_dict[y_key], key=lambda item: item[0])
                        full_line = " ".join([w[1] for w in sorted_words])
                        lookahead_line = ""
                        if yk_idx + 1 < len(sorted_y_keys):
                            nxt = sorted(line_dict[sorted_y_keys[yk_idx + 1]], key=lambda item: item[0])
                            lookahead_line = " ".join([w[1] for w in nxt])
                        combined_line = f"{full_line} {lookahead_line}"
                        full_line_lower = full_line.lower()
                        combined_lower = combined_line.lower()

                        # --- 1. DYNAMIC HEADER HUNTING (tolerant of wrapped headers) ---
                        header_hit = (
                            any(k in combined_lower for k in ["withdrawn", "debited", "debit", "payments", "out"]) and
                            any(k in combined_lower for k in ["deposited", "credited", "credit", "deposits", "in"])
                        )
                        if header_hit:
                            withdrawn_x, deposited_x = None, None
                            scan_words = sorted_words
                            if yk_idx + 1 < len(sorted_y_keys) and not any(
                                h in full_line_lower for h in ["withdrawn", "debited", "debit", "deposited", "credited", "credit"]
                            ):
                                scan_words = sorted_words + sorted(line_dict[sorted_y_keys[yk_idx + 1]], key=lambda item: item[0])

                            for x0, word in scan_words:
                                w_low = word.lower()
                                if any(h in w_low for h in ["withdrawn", "debited", "debit", "out"]):
                                    withdrawn_x = x0
                                elif any(h in w_low for h in ["deposited", "credited", "credit", "in"]):
                                    deposited_x = x0

                            if withdrawn_x and deposited_x:
                                desc_x_limit = withdrawn_x - 10
                                debit_x_min = withdrawn_x - 20
                                debit_x_max = deposited_x - 5
                                credit_x_min = deposited_x - 20
                                credit_x_max = balance_x_min - 5

                                st.session_state.diagnostic_log.append(
                                    f"{f.name} (p.{page_num+1}): Calibrated -> Desc: <{round(desc_x_limit,1)} | "
                                    f"Debit: {round(debit_x_min,1)}-{round(debit_x_max,1)} | "
                                    f"Credit: {round(credit_x_min,1)}-{round(credit_x_max,1)} | "
                                    f"Balance Cordon: >{round(balance_x_min,1)}"
                                )

                        # --- TD FOOTER KILL-SWITCH ---
                        if any(k in full_line.upper() for k in ["ACCOUNT/TRANSACTION TYPE", "FEES PAID"]):
                            break

                        is_date_row = False

                        # --- ROBUST DATE ROUTING NODE ---
                        if is_nbc:
                            match = re.match(r'^[\s|]*(0[1-9]|1[0-2])[\s|]+(0[1-9]|[12]\d|3[01])\b', full_line)
                            if match:
                                m_str, d_str = match.group(1), match.group(2)
                                active_date, active_month = f"{year}-{m_str}-{d_str}", f"{year}-{m_str}"
                                is_date_row = True
                        else:
                            match1 = re.match(r'^(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{2,4})\b', full_line, re.IGNORECASE)
                            match2 = re.match(r'^(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b', full_line, re.IGNORECASE)
                            match3 = re.search(r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2})\b', full_line, re.IGNORECASE)

                            if match1:
                                d_str, m_str = match1.group(1).zfill(2), match1.group(2).upper()
                                y_val = match1.group(3) if len(match1.group(3)) == 4 else "20" + match1.group(3)
                                if m_str in month_map:
                                    active_date, active_month = f"{y_val}-{month_map[m_str]}-{d_str}", f"{y_val}-{month_map[m_str]}"
                                    is_date_row = True
                            elif match2:
                                d_str, m_str = match2.group(1).zfill(2), match2.group(2).upper()
                                if m_str in month_map:
                                    active_date, active_month = f"{year}-{month_map[m_str]}-{d_str}", f"{year}-{month_map[m_str]}"
                                    is_date_row = True
                            elif match3:
                                m_str, d_str = match3.group(1).upper(), match3.group(2).zfill(2)
                                if m_str in month_map:
                                    active_date, active_month = f"{year}-{month_map[m_str]}-{d_str}", f"{year}-{month_map[m_str]}"
                                    is_date_row = True

                        # --- NBC DIFFERENTIAL PARSER OVERRIDE ---
                        if is_nbc and is_date_row and active_date:
                            debit_parts, credit_parts = [], []
                            desc_words = []
                            for x0, word in sorted_words:
                                if x0 < 90: continue  
                                elif x0 < 270: 
                                    if word != '|': desc_words.append(word)
                                elif 270 <= x0 < 375:
                                    if re.search(r'[\d,]', word): debit_parts.append(word)
                                elif 375 <= x0 < 465:
                                    if re.search(r'[\d,]', word): credit_parts.append(word)

                            debit_val, credit_val = None, None
                            if debit_parts:
                                clean_d = "".join(debit_parts).replace(' ', '').replace('$', '').replace(',', '.')
                                match = re.search(r'\d+\.\d{2}', clean_d)
                                if match: debit_val = float(match.group(0))
                            if credit_parts:
                                clean_c = "".join(credit_parts).replace(' ', '').replace('$', '').replace(',', '.')
                                match = re.search(r'\d+\.\d{2}', clean_c)
                                if match: credit_val = float(match.group(0))

                            desc_str = " ".join(desc_words).strip()
                            desc_upper = desc_str.upper()

                            if any(k in desc_upper for k in ["CLOSING", "OPENING", "ITEMS PROCESSED", "BALANCE FORWARD", "TOTALS", "SOLDE PRECEDENT", "FACTURATION", "TRANSACTIONS"]):
                                continue

                            if credit_val and credit_val > 0:
                                all_deposits.append({"date": active_date, "month": active_month, "description": desc_str if desc_str else "Deposit", "amount": credit_val, "payer_or_source": desc_str if desc_str else "Deposit", "tx_type": "credit", "source_file": f.name, "entity": entity_key})

                            if debit_val and debit_val > 0:
                                is_mca = False
                                for var_str, (tier, lender_name) in ALL_KNOWN_LENDERS.items():
                                    if re.search(r'\b' + re.escape(var_str) + r'\b', desc_upper) and lender_name not in ["TD", "EASYHOME"]:
                                        all_mca_debits.append({"date": active_date, "lender": lender_name, "tier": tier, "payment_amount": debit_val, "month": active_month})
                                        is_mca = True
                                        break

                                if not is_mca and re.search(r'\bLOAN PAYMENT\b|\bLOAN CREDIT\b', desc_upper):
                                    all_mca_debits.append({"date": active_date, "lender": "Generic Loan/MCA", "tier": "Standard", "payment_amount": debit_val, "month": active_month})

                                if re.search(r'\bNSF\b|RETURNED ITEM|UNPAID|DISHONOURED|FRAIS EFFET RET', desc_upper):
                                    if not re.search(r'OVERDRAWN|HANDLING CHGS', desc_upper) and debit_val > 30.00:
                                        all_deposits.append({"date": active_date, "month": active_month, "description": desc_str, "amount": debit_val, "payer_or_source": "Bank Fee", "tx_type": "debit", "source_file": f.name, "entity": entity_key})

                        # --- 2. UNIVERSAL DYNAMIC SPATIAL EXTRACTION ---
                        else:
                            has_currency = bool(re.search(r'\d+\.\d{2}', full_line))

                            if (is_date_row or (active_date and has_currency)):
                                debit_val, credit_val = None, None
                                desc_words = []
                                debit_parts, credit_parts = [], []

                                for x0, word in sorted_words: 
                                    if x0 >= balance_x_min:
                                        pass  # STRICT CORDON OF RUNNING BALANCES
                                    elif x0 < desc_x_limit and not re.search(r'^(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)', word, re.IGNORECASE):
                                        if len(desc_words) == 0 and re.match(r'^\d{1,2}$', word): continue
                                        desc_words.append(word)
                                    elif debit_x_min <= x0 < debit_x_max:
                                        if re.search(r'[\d,.\-]', word): debit_parts.append(word)
                                    elif credit_x_min <= x0 < credit_x_max:
                                        if re.search(r'[\d,.\-]', word): credit_parts.append(word)

                                if debit_parts:
                                    clean_d = "".join(debit_parts).replace(' ', '').replace('$', '').replace(',', '')
                                    match = re.search(r'-?\d+\.\d{2}-?', clean_d)
                                    if match: debit_val = abs(float(match.group(0).replace('-', '')))
                                if credit_parts:
                                    clean_c = "".join(credit_parts).replace(' ', '').replace('$', '').replace(',', '')
                                    match = re.search(r'-?\d+\.\d{2}-?', clean_c)
                                    if match: credit_val = abs(float(match.group(0).replace('-', '')))

                                desc_str = " ".join(desc_words).strip()
                                desc_upper = desc_str.upper()

                                if any(k in desc_upper for k in ["CLOSING", "OPENING", "ITEMS PROCESSED", "BALANCE FORWARD", "TOTALS", "SOLDE PRECEDENT", "FACTURATION", "NEW BALANCE", "TOTAL FUNDS", "TRANSACTION"]):
                                    continue

                                if "TOTAL" in desc_upper and len(desc_words) < 3:
                                    continue

                                if credit_val and credit_val > 0:
                                    all_deposits.append({
                                        "date": active_date, "month": active_month, "description": desc_str if desc_str else "Deposit",
                                        "amount": credit_val, "payer_or_source": desc_str if desc_str else "Deposit", "tx_type": "credit",
                                        "source_file": f.name, "entity": entity_key
                                    })

                                if debit_val and debit_val > 0:
                                    file_debit_total += debit_val
                                    is_mca = False
                                    for var_str, (tier, lender_name) in ALL_KNOWN_LENDERS.items():
                                        if re.search(r'\b' + re.escape(var_str) + r'\b', desc_upper) and lender_name not in ["TD", "EASYHOME"]:
                                            all_mca_debits.append({"date": active_date, "lender": lender_name, "tier": tier, "payment_amount": debit_val, "month": active_month})
                                            is_mca = True
                                            break

                                    if not is_mca and re.search(r'\bLOAN PAYMENT\b|\bLOAN CREDIT\b', desc_upper):
                                        all_mca_debits.append({"date": active_date, "lender": "Generic Loan/MCA", "tier": "Standard", "payment_amount": debit_val, "month": active_month})

                                    if matches_any(NSF_REVERSAL_PATTERNS, desc_upper):
                                        if not re.search(r'OVERDRAWN|HANDLING CHGS', desc_upper) and debit_val > 30.00:
                                            all_deposits.append({"date": active_date, "month": active_month, "description": desc_str, "amount": debit_val, "payer_or_source": "Bank Fee", "tx_type": "debit", "source_file": f.name, "entity": entity_key})

                # Resolve the opening/closing balance fallback anchor now that we
                # have the full debit total for this file.
                if needs_fallback:
                    implied_credits = (closing_bal - opening_bal) + file_debit_total
                    total_anchor_credits += implied_credits
                    st.session_state.diagnostic_log.append(
                        f"↪️ {f.name}: Fallback anchor resolved = ${implied_credits:,.2f} "
                        f"(Closing ${closing_bal:,.2f} - Opening ${opening_bal:,.2f} + Debits ${file_debit_total:,.2f})"
                    )
                    anchor_source_count += 1

            progress_bar.progress((f_idx + 1) / len(uploaded_files))

        st.session_state.expected_credits = total_anchor_credits

        # --- MULTI-ENTITY WARNING ---
        if len(entities_seen) > 1:
            entity_summary = "; ".join(
                f"{v['display']} ({len(v['files'])} file(s))" for v in entities_seen.values()
            )
            st.session_state.entity_warning = (
                f"This batch appears to contain statements from {len(entities_seen)} different "
                f"account holders: {entity_summary}. Mixing entities will corrupt revenue totals, "
                f"concentration %, and the reconciliation check below."
            )

        if skipped_duplicate_files:
            st.warning(f"⚠️ Skipped {len(skipped_duplicate_files)} duplicate file(s) (byte-identical to an earlier upload): {', '.join(skipped_duplicate_files)}")

        if not all_deposits:
            st.error("❌ No deposits found. Please verify PDF formatting.")
        else:
            status_text.info("Step 2/3: Applying Strict 3-Tier Classification (rules-first, AI for the remainder)...")
            df = pd.DataFrame(all_deposits).reset_index(drop=True)

            # --- Row-level dedup across files (same date+amount+description+entity) ---
            before_dedup = len(df)
            df = df.drop_duplicates(subset=["entity", "date", "amount", "description", "tx_type"]).reset_index(drop=True)
            if before_dedup != len(df):
                st.session_state.diagnostic_log.append(
                    f"🧹 Removed {before_dedup - len(df)} duplicate transaction row(s) across files."
                )

            # --- INTERVAL-BASED MCA FREQUENCY LOGIC ---
            mca_positions = []
            if all_mca_debits:
                mca_df = pd.DataFrame(all_mca_debits).drop_duplicates(subset=["date", "payment_amount"]).reset_index(drop=True)
                mca_df['date'] = pd.to_datetime(mca_df['date'])

                for lender, group in mca_df.groupby("lender"):
                    group = group.sort_values('date')
                    tier = group["tier"].iloc[0]
                    amt = group["payment_amount"].mode()[0] if not group.empty else 0

                    if len(group) >= 2:
                        median_days = group['date'].diff().dt.days.median()
                        if median_days <= 2: freq = "Daily"
                        elif median_days <= 5: freq = "2-3x Weekly"
                        elif median_days <= 8: freq = "Weekly"
                        elif median_days <= 15: freq = "Bi-Weekly"
                        else: freq = "Monthly"
                    else:
                        freq = "Monthly"

                    monthly_equiv = amt * 21 if freq == "Daily" else amt * 9 if freq == "2-3x Weekly" else amt * 4.33 if freq == "Weekly" else amt * 2.16 if freq == "Bi-Weekly" else amt
                    mca_positions.append({"lender": lender, "tier": tier, "payment_amount": amt, "frequency": freq, "monthly_payment": monthly_equiv})
            st.session_state.mca_positions = mca_positions

            # --- RULE-BASED PRE-CLASSIFICATION PASS ---
            df['description_upper'] = df['description'].astype(str).str.upper()
            df['category'] = df['description_upper'].apply(lambda d: rule_based_category(d))
            unresolved_mask = df['category'].isna()

            # --- CONTEXTUAL AI PAYLOAD (only for rows the rules pass couldn't resolve) ---
            if unresolved_mask.any() and client:
                unresolved_df = df[unresolved_mask]
                context_dict = unresolved_df.groupby('description')['amount'].max().to_dict()
                context_payload = [{"description": desc, "max_amount": amt} for desc, amt in context_dict.items()]

                try:
                    ai_response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {
                                "role": "system",
                                "content": "You map bank transaction descriptions to strict categories. Use the provided max_amount to add context. Philosophy: Unknown ≠ Revenue. Unknown = Review Required. A $50,000 unexplained transfer should NEVER be true revenue. Map ONLY to the exact allowed enum categories."
                            },
                            {"role": "user", "content": json.dumps(context_payload)}
                        ],
                        temperature=0.0,
                        response_format=CATEGORIZATION_SCHEMA,
                        timeout=30.0
                    )
                    raw_json = json.loads(ai_response.choices[0].message.content)
                    category_map = {str(i['description']).strip().upper(): i['category'] for i in raw_json.get('mappings', [])}
                    df.loc[unresolved_mask, 'category'] = df.loc[unresolved_mask, 'description'].apply(
                        lambda x: category_map.get(str(x).strip().upper(), "Review Required - Unidentified / Unusual Deposit")
                    )
                except Exception:
                    df.loc[unresolved_mask, 'category'] = "Review Required - Unidentified / Unusual Deposit"
            elif unresolved_mask.any():
                df.loc[unresolved_mask, 'category'] = "Review Required - Unidentified / Unusual Deposit"

            df.drop(columns=['description_upper'], inplace=True)

            # --- THE REVENUE HIERARCHY MAPPER ---
            df['is_revenue'] = False
            df['needs_review'] = False

            df.loc[df['category'].str.startswith('True Revenue', na=False), 'is_revenue'] = True
            df.loc[df['category'].str.startswith('Review Required', na=False), 'needs_review'] = True

            # --- CANADIAN POS PROCESSOR & CARD SETTLEMENT OVERRIDE ---
            pos_pattern = (
                r'STRIPE|SQUARE|SQ \*|MONERIS|CLOVER|FIRST DATA|FISERV|FDMS|ELAVON|GLOBAL PAY|'
                r'CHASE MERCH|PAYMENTECH|HELCIM|TD MERCH|MONETICO|DESJARDINS PAIEMENT|LIGHTSPEED|'
                r'SHOPIFY|ADYEN|BAMBORA|WORLDLINE|TOAST|NUVEI|PIVOTAL|PAYFACTO|ZETTLE|PAYPAL|'
                r'KLARNA|AMAZON|UBER|DOORDASH|SKIPTHEDISHES|SKIP THE DISHES|MSP/DIV|MSP/ DIV|'
                r'\b(?:VI|MC|EF|AMX)\d{4}\b'
            )
            pos_mask = df['description'].str.contains(pos_pattern, case=False, na=False)

            df.loc[pos_mask, 'category'] = "True Revenue - POS / Processor"
            df.loc[pos_mask, 'is_revenue'] = True
            df.loc[pos_mask, 'needs_review'] = False

            # --- RULE-BASED WASH / ROUND-TRIP DETECTION ---
            wash_detected, wash_ref_count = detect_wash_pattern(df)
            st.session_state['wash_detected_auto'] = wash_detected
            st.session_state['wash_ref_count'] = wash_ref_count
            if wash_detected:
                st.session_state.diagnostic_log.append(
                    f"🚨 Wash/round-trip pattern detected: {wash_ref_count} matched debit/credit pairs "
                    f"sharing the same internal transfer reference."
                )

            st.session_state.transactions = df

            status_text.empty()
            progress_bar.empty()
            if anchor_source_count < len(uploaded_files) - len(skipped_duplicate_files):
                st.warning("⚠️ Extraction complete, but one or more files had no verifiable anchor total. Check Diagnostics below.")
            else:
                st.success("✅ Extraction complete with anchors resolved for all files (native or fallback).")

    # --- ENTITY MISMATCH WARNING (persists after processing) ---
    if st.session_state.entity_warning:
        st.error(f"🚨 **MULTIPLE ENTITIES DETECTED**: {st.session_state.entity_warning}")

    # --- UI DISPLAY & RECONCILIATION ---
    with st.expander("🔍 Extraction Diagnostics & Confidence Matrix"):
        if st.session_state.diagnostic_log:
            st.write("Per-file processing log (anchor method, calibration, warnings):")
            for log in st.session_state.diagnostic_log:
                st.code(log)
        else:
            st.write("Awaiting document processing...")

    if st.session_state.transactions is not None and not st.session_state.transactions.empty:
        st.markdown("---")
        st.subheader("⚖️ Mathematical Reconciliation (Two-Pass Verification)")

        recon_df = st.session_state.transactions[st.session_state.transactions['tx_type'] == 'credit']
        total_gross = recon_df['amount'].sum()
        expected_credits = st.session_state.expected_credits
        variance = abs(total_gross - expected_credits)

        r_col1, r_col2, r_col3 = st.columns(3)
        r_col1.metric("Bank Summary / Fallback Anchor Total", f"${expected_credits:,.2f}")
        r_col2.metric("Extracted Ledger Total", f"${total_gross:,.2f}")

        if expected_credits == 0.0:
            r_col3.metric("Reconciliation Variance", "N/A", "Anchor Missing", delta_color="off")
            st.warning("⚠️ Anchor Warning: No summary or fallback anchor total could be resolved for any file.")
        elif variance > 2.00:
            r_col3.metric("Reconciliation Variance", f"-${variance:,.2f}", "Mismatch Detected", delta_color="inverse")
            st.error(f"🚨 Variance Detected: Stated/derived anchor is ${expected_credits:,.2f}, extracted total is ${total_gross:,.2f}. Check Diagnostics for which file(s) drove this.")
        else:
            r_col3.metric("Reconciliation Variance", f"${variance:,.2f}", "Matched (100%)", delta_color="normal")
            st.success("✅ Reconciliation Passed: extracted deposits match the resolved anchor total(s).")

        st.markdown("---")
        st.subheader("Interactive True Revenue Reconciliation")

        st.caption("Use the filters below to isolate specific transaction types. Toggle the checkboxes to reclassify items between True Revenue, Non-Revenue, and Review.")

        months_available = ["All"] + sorted(st.session_state.transactions["month"].dropna().unique().tolist())
        categories_available = ["All"] + sorted(st.session_state.transactions["category"].dropna().unique().tolist())
        entities_available = ["All"] + sorted(st.session_state.transactions["entity"].dropna().unique().tolist()) if "entity" in st.session_state.transactions.columns else ["All"]

        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1: selected_month = st.selectbox("Filter by Month", options=months_available)
        with col_f2: selected_category = st.selectbox("Filter by Category", options=categories_available)
        with col_f3: selected_entity = st.selectbox("Filter by Entity", options=entities_available)

        mask = pd.Series(True, index=st.session_state.transactions.index)
        if selected_month != "All": mask &= (st.session_state.transactions["month"] == selected_month)
        if selected_category != "All": mask &= (st.session_state.transactions["category"] == selected_category)
        if selected_entity != "All" and "entity" in st.session_state.transactions.columns:
            mask &= (st.session_state.transactions["entity"] == selected_entity)

        filtered_df = st.session_state.transactions[mask]

        display_cols = ["date", "month", "description", "amount", "payer_or_source", "tx_type", "category", "is_revenue", "needs_review"]
        display_cols = [c for c in display_cols if c in filtered_df.columns]

        edited_filtered_df = st.data_editor(
            filtered_df[display_cols],
            column_config={
                "is_revenue": st.column_config.CheckboxColumn("True Revenue?"),
                "needs_review": st.column_config.CheckboxColumn("Review Req?", disabled=True),
                "amount": st.column_config.NumberColumn("Amount ($)", format="$%.2f"),
                "date": st.column_config.TextColumn("Date"),
                "month": st.column_config.TextColumn("Month"),
                "category": st.column_config.TextColumn("Category"),
                "payer_or_source": st.column_config.TextColumn("Payer / Source"),
                "description": st.column_config.TextColumn("Description"),
                "tx_type": st.column_config.TextColumn("Type", disabled=True),
            },
            disabled=["date", "month", "amount", "description", "payer_or_source", "category", "tx_type"],
            width="stretch",
            num_rows="dynamic",
            key="main_editor"
        )
        st.session_state.transactions.update(edited_filtered_df)

        st.markdown("<br>", unsafe_allow_html=True)
        revenue_df = st.session_state.transactions[st.session_state.transactions["is_revenue"] == True]
        review_df = st.session_state.transactions[st.session_state.transactions["needs_review"] == True]

        total_true = revenue_df["amount"].sum()
        total_review = review_df["amount"].sum()

        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        kpi1.metric("Confirmed True Revenue", f"${total_true:,.2f}")
        kpi2.metric("Revenue Under Review", f"${total_review:,.2f}", "Requires Manual Approval", delta_color="off")

        num_active_months = st.session_state.transactions["month"].nunique() if not st.session_state.transactions.empty else 1
        kpi3.metric("Avg Monthly True Revenue", f"${(total_true / num_active_months if num_active_months > 0 else 0.0):,.2f}")
        kpi4.metric("Non-Revenue Proportion", f"{((total_gross - total_true)/total_gross*100 if total_gross > 0 else 0):.1f}%")

        st.markdown("---")
        col_cat, col_mca = st.columns(2)
        with col_cat:
            st.markdown("#### 📂 Deposit Breakdown by Payer & Category (Bulk Toggle)")
            cat_summary = st.session_state.transactions.groupby(["category", "payer_or_source"]).agg(Total=("amount", "sum"), Count=("amount", "count")).reset_index()
            cat_rev_status = st.session_state.transactions.groupby(["category", "payer_or_source"])["is_revenue"].agg(lambda x: bool(x.mode()[0]) if not x.empty else False).reset_index()
            cat_summary = pd.merge(cat_summary, cat_rev_status, on=["category", "payer_or_source"])
            cat_summary = cat_summary.sort_values(by="Total", ascending=False).reset_index(drop=True)

            cat_editor = st.data_editor(
                cat_summary,
                column_config={
                    "category": st.column_config.TextColumn("Category", disabled=True),
                    "payer_or_source": st.column_config.TextColumn("Payer / Source", disabled=True),
                    "is_revenue": st.column_config.CheckboxColumn("True Revenue?"),
                    "Count": st.column_config.NumberColumn("Count", disabled=True),
                    "Total": st.column_config.NumberColumn("Total ($)", format="$%.2f", disabled=True)
                },
                key="bulk_cat_editor",
                width="stretch"
            )

            bulk_changed = False
            for _, r in cat_editor.iterrows():
                c_name = r["category"]
                p_name = r["payer_or_source"]
                c_status = r["is_revenue"]
                mask2 = (st.session_state.transactions["category"] == c_name) & (st.session_state.transactions["payer_or_source"] == p_name)
                if not (st.session_state.transactions.loc[mask2, "is_revenue"] == c_status).all():
                    st.session_state.transactions.loc[mask2, "is_revenue"] = c_status
                    if c_status:
                        st.session_state.transactions.loc[mask2, "needs_review"] = False
                    bulk_changed = True

            if bulk_changed: st.rerun()

        with col_mca:
            st.markdown("#### 🏦 Identified Active MCA Positions (Editable)")
            mca_df = pd.DataFrame(st.session_state.mca_positions)
            if mca_df.empty: mca_df = pd.DataFrame(columns=["lender", "tier", "frequency", "payment_amount", "monthly_payment"])

            edited_mca_df = st.data_editor(
                mca_df,
                column_config={
                    "lender": st.column_config.TextColumn("Lender Name", required=True),
                    "tier": st.column_config.SelectboxColumn("Tier", options=["Premium", "Standard"], required=True),
                    "frequency": st.column_config.SelectboxColumn("Frequency", options=["Daily", "Weekly", "Bi-Weekly", "Monthly"], required=True),
                    "payment_amount": st.column_config.NumberColumn("Payment ($)", min_value=0.0, format="$%.2f", required=True),
                    "monthly_payment": st.column_config.NumberColumn("Monthly Equiv ($)", disabled=True, format="$%.2f")
                },
                num_rows="dynamic",
                width="stretch",
                key="mca_editor"
            )

            def calculate_monthly_equiv(row):
                freq = str(row.get("frequency", "Monthly"))
                amt = pd.to_numeric(row.get("payment_amount"), errors='coerce')
                amt = 0.0 if pd.isna(amt) else amt
                return amt * 21 if freq == "Daily" else amt * 9 if freq == "2-3x Weekly" else amt * 4.33 if freq == "Weekly" else amt * 2.16 if freq == "Bi-Weekly" else amt * 1.0

            if not edited_mca_df.empty:
                edited_mca_df["monthly_payment"] = edited_mca_df.apply(calculate_monthly_equiv, axis=1)
                st.session_state.mca_positions = edited_mca_df.to_dict('records')
            else:
                st.session_state.mca_positions = []

# ==============================================================================
# TAB 2 & 3: SUMMARY & SCORECARD
# ==============================================================================
with tab2:
    if st.session_state.transactions is not None and not st.session_state.transactions.empty:
        st.header("🏦 Master Bank Statement Summary")
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
    st.header("Forward Funding Underwriting Scoring Model v1.0")

    cp = st.session_state.credit_profile
    default_public_records = "Clean"
    if cp["bankruptcies_found"]:
        default_public_records = "Severe"
    elif cp["active_collections_count"] > 0:
        default_public_records = "Moderate"

    st.markdown("---")
    st.subheader("👤 Owner Credit Profile (Bureau Data)")
    c_col1, c_col2, c_col3, c_col4 = st.columns(4)
    with c_col1:
        st.metric("Owner Name", cp["owner_name"])
        st.metric("FICO Score", cp["fico_score"])
    with c_col2:
        st.metric("Revolving Utilization", f"{cp['revolving_credit_utilization_pct']}%")
        st.metric("Reported High Credit", f"${cp['total_high_credit']:,.2f}")
    with c_col3:
        col_color = "normal" if cp["active_collections_count"] == 0 else "inverse"
        st.metric("Active Collections", cp["active_collections_count"], delta="Review Required" if cp["active_collections_count"] > 0 else "Clean", delta_color=col_color)
        st.metric("Collections Amount", f"${cp['total_collections_amount']:,.2f}")
    with c_col4:
        st.metric("Active Mortgages", cp["number_of_mortgages"])
        st.caption(f"**LTV Details:** {cp['mortgage_ltv_details']}")

    st.markdown("---")
    st.warning("### ⚠️ MANUAL INPUT REQUIRED\n**These critical fields require human verification or external API integrations.**")
    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    with m_col1:
        time_in_biz = st.number_input("Time in Business (months)", min_value=0, max_value=1000, value=24)
        avg_daily_balance = st.number_input("Average Daily Balance (ADB) $", value=0.0)
    with m_col2:
        credit_score = st.number_input("Owner Credit Score (300-900)", min_value=300, max_value=900, value=int(cp["fico_score"]))
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

        monthly_rev_series = rev_tx.groupby("month")["amount"].sum()
        monthly_count_series = rev_tx.groupby("month")["amount"].count()
        num_months = len(df["month"].unique()) if len(df["month"].unique()) > 0 else 1

        auto_avg_true_rev = float(monthly_rev_series.mean()) if not monthly_rev_series.empty else 0.0
        auto_deposit_count = int(round(monthly_count_series.mean())) if not monthly_count_series.empty else 0

        if num_months > 1 and auto_avg_true_rev > 0:
            auto_rev_volatility = float((monthly_rev_series.std() / auto_avg_true_rev) * 100)
        if len(monthly_rev_series) >= 2:
            m_start = monthly_rev_series.iloc[0]
            m_end = monthly_rev_series.iloc[-1]
            auto_trend_pct = float(((m_end - m_start) / m_start) * 100) if m_start > 0 else 0.0

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

        nsf_df = df[df['category'].str.contains('NSF', case=False, na=False)]
        auto_payment_perf = len(nsf_df[nsf_df['tx_type'] == 'debit']) + len(nsf_df[nsf_df['tx_type'] == 'credit'])

    st.success("### 🤖 AUTOMATED FINANCIAL FINGERPRINT\n**These fields are dynamically calculated by the transaction ledger.**")
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
    st.subheader("🛡️ Hard-Stop & Override Logic")
    h_col1, h_col2 = st.columns(2)
    with h_col1:
        fraud_suspected = st.checkbox("Suspected altered statements / fraud?")
        wash_flag = st.checkbox("Severe Wash Transactions detected?", value=wash_transactions_detected)
    with h_col2:
        active_default = st.checkbox("Active lender default / collections?")
        multi_entity_flag = st.checkbox("Multiple unrelated entities detected in upload batch?", value=bool(st.session_state.entity_warning))

    score = 0
    hard_stop_reasons = []

    if fraud_suspected: hard_stop_reasons.append("Suspected altered statements / fraud")
    if active_default: hard_stop_reasons.append("Active lender default or collections")
    if wash_flag: hard_stop_reasons.append("Evidence of structural wash transactions to cover debt")
    if multi_entity_flag: hard_stop_reasons.append("Statement batch contains multiple unrelated entities - re-upload verified single-entity file set")
    if auto_avg_true_rev < 10000: hard_stop_reasons.append("Avg True Revenue is under $10,000 policy minimum")

    if hard_stop_reasons:
        st.error(f"🚨 **POLICY HARD STOP / AUTO DECLINE**: {', '.join(hard_stop_reasons)}")
    else:
        score += 6 if auto_avg_true_rev >= 150000 else 5 if auto_avg_true_rev >= 75000 else 4 if auto_avg_true_rev >= 40000 else 3 if auto_avg_true_rev >= 20000 else 2 if auto_avg_true_rev >= 10000 else 0
        score += 6 if auto_trend_pct > 15 else 5 if auto_trend_pct >= 5 else 4 if auto_trend_pct >= -5 else 2 if auto_trend_pct >= -10 else 1 if auto_trend_pct >= -20 else 0
        score += 5 if auto_deposit_count >= 40 else 4 if auto_deposit_count >= 20 else 3 if auto_deposit_count >= 10 else 2 if auto_deposit_count >= 5 else 0
        score += 5 if auto_rev_volatility <= 10 else 4 if auto_rev_volatility <= 20 else 3 if auto_rev_volatility <= 30 else 2 if auto_rev_volatility <= 40 else 1 if auto_rev_volatility <= 50 else 0

        adb_pct = (avg_daily_balance / auto_avg_true_rev * 100) if auto_avg_true_rev > 0 else 0
        score += 5 if adb_pct >= 10 else 4 if adb_pct >= 7 else 3 if adb_pct >= 4 else 2 if adb_pct >= 2 else 1 if adb_pct >= 1 else 0

        score += 6 if auto_mca_positions == 0 else 5 if auto_mca_positions == 1 else 3 if auto_mca_positions == 2 else 1 if auto_mca_positions == 3 else 0
        score += 10 if auto_mca_burden_pct <= 8 else 8 if auto_mca_burden_pct <= 12 else 6 if auto_mca_burden_pct <= 16 else 4 if auto_mca_burden_pct <= 20 else 2 if auto_mca_burden_pct <= 25 else 0

        score += 5 if borrowing_velocity == "0 in 90 Days" else 3 if borrowing_velocity == "1 in 90 Days" else 1
        score += 4 if auto_payment_perf == 0 else 3 if auto_payment_perf == 1 else 2 if auto_payment_perf == 2 else 1 if auto_payment_perf <= 4 else 0
        score += 6 if negative_days == 0 else 5 if negative_days <= 3 else 3 if negative_days <= 6 else 2 if negative_days <= 10 else 1 if negative_days <= 15 else 0

        score += 6 if time_in_biz >= 84 else 5 if time_in_biz >= 48 else 4 if time_in_biz >= 24 else 3 if time_in_biz >= 12 else 1 if time_in_biz >= 6 else 0
        score += industry_score
        score += seasonality_score

        score += 6 if credit_score >= 750 else 5 if credit_score >= 700 else 4 if credit_score >= 650 else 3 if credit_score >= 600 else 2 if credit_score >= 550 else 1 if credit_score >= 500 else 0
        score += 4 if public_records == "Clean" else 3 if public_records == "Minor" else 1 if public_records == "Moderate" else 0
        score += 3 if bank_verification == "Bank Connect" else 2 if bank_verification == "Original PDF" else 1 if bank_verification == "Minor inconsistency" else 0
        score += 2 if auto_concentration_pct <= 20 else 1 if auto_concentration_pct <= 35 else 0

        if score >= 90: grade, risk, advance, max_burden = "A+", "Prime MCA", 1.00, 0.18
        elif score >= 82: grade, risk, advance, max_burden = "A", "Strong", 0.85, 0.17
        elif score >= 74: grade, risk, advance, max_burden = "B", "Acceptable", 0.70, 0.15
        elif score >= 66: grade, risk, advance, max_burden = "C", "Elevated", 0.55, 0.13
        elif score >= 58: grade, risk, advance, max_burden = "D", "High", 0.35, 0.10
        else: grade, risk, advance, max_burden = "E", "High / Unacceptable", 0.00, 0.00

        max_advance_dollars = auto_avg_true_rev * advance
        remaining_monthly_capacity = max(0.0, (auto_avg_true_rev * max_burden) - (auto_avg_true_rev * (auto_mca_burden_pct / 100)))
        affordable_daily_payment = remaining_monthly_capacity / 21

        st.markdown("### 🏆 Final Underwriting Score & Offer Structuring")
        r1, r2, r3, r4 = st.columns(4)
        r1.metric("Overall Score", f"{score} / 100")
        r2.metric("Score Grade", grade)
        r3.metric("Risk Tier", risk)
        r4.metric("Suggested Max Advance %", f"{advance * 100:.0f}%")

        s1, s2, s3 = st.columns(3)
        s1.metric("Suggested Max Advance ($)", f"${max_advance_dollars:,.2f}")
        s2.metric("Remaining Monthly Debt Capacity ($)", f"${remaining_monthly_capacity:,.2f}")
        s3.metric("Affordable Daily Payment (21 days)", f"${affordable_daily_payment:,.2f}")
