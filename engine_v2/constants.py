"""Canonical underwriting classification constants.

Keep merchant/lender aliases and classification labels here so extraction,
classification, API, and UI layers use the same vocabulary.
"""

TRUE_REVENUE_POS = "True Revenue - POS / Processor"
TRUE_REVENUE_CASH = "True Revenue - Verified Cash"
TRUE_REVENUE_CUSTOMER = "True Revenue - Customer Payment / Cheque"
TRUE_REVENUE_ETRANSFER = "True Revenue - B2B E-Transfer"

NON_REVENUE_INTERNAL = "Non-Revenue - Own-Account / Internal Transfer"
NON_REVENUE_MCA = "Non-Revenue - MCA / Loan Proceeds"
NON_REVENUE_REVERSAL = "Non-Revenue - Refund / Reversal / NSF"
NON_REVENUE_GOV = "Non-Revenue - Gov / Tax / Insurance Proceeds"
NON_REVENUE_SHAREHOLDER = "Non-Revenue - Shareholder / Investment"
NON_REVENUE_WASH = "Non-Revenue - Wash / Round-Trip Transfer"
REVIEW_REQUIRED = "Review Required - Unidentified / Unusual Deposit"

ALLOWED_CATEGORIES = (
    TRUE_REVENUE_POS,
    TRUE_REVENUE_CASH,
    TRUE_REVENUE_CUSTOMER,
    TRUE_REVENUE_ETRANSFER,
    NON_REVENUE_INTERNAL,
    NON_REVENUE_MCA,
    NON_REVENUE_REVERSAL,
    NON_REVENUE_GOV,
    NON_REVENUE_SHAREHOLDER,
    NON_REVENUE_WASH,
    REVIEW_REQUIRED,
)

PREMIUM_LENDERS = {
    "MERCHANT GROWTH": ["MERCHANT GROWTH", "MERCHPAD", "MERCH PAD"],
    "GREENBOX": ["GREENBOX", "GREEN BOX", "GREENBOX CAPITAL"],
    "VAULT": ["VAULT", "VAULT FINANCIAL"],
    "DRIVEN": ["DRIVEN", "DRIVEN CAPITAL"],
    "JOURNEY": ["JOURNEY", "JOURNEY CAPITAL", "JOURNEY FUNDING", "ONDECK"],
    "ICAPITAL": ["ICAPITAL", "I CAPITAL", "IPAPITAL"],
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

LENDER_ALIASES = {}
for canonical, aliases in PREMIUM_LENDERS.items():
    for alias in aliases:
        LENDER_ALIASES[alias] = ("Premium", canonical)
for canonical, aliases in STANDARD_LENDERS.items():
    for alias in aliases:
        LENDER_ALIASES[alias] = ("Standard", canonical)

INTERNAL_TRANSFER_PATTERNS = (
    r"\bTF\s*\d{3,4}\s*#\s*\d{3,4}[\-#]\d{3,4}\b",
    r"\bONLINE\s+TRANSFER\b",
    r"\bINTERNAL\s+TRANSFER\b",
    r"\bBR\.?\s*\d{3,4}\b",
    r"\bBALANCE\s+ADJUSTMENT\b",
    r"\b\d{4}-\d{4}-\d{3,4}\s*1005\b",
)

GOV_TAX_INSURANCE_PATTERNS = (
    r"\bPROV[/\.]?\s*LOCAL\s+GVT\s+PAYMENT\b",
    r"\bPROVINCE\s+OF\b",
    r"\bCRA\b|\bCANADA\s+REVENUE\b|\bPAD\s+CCRA\b",
    r"\bGST\b|\bHST\b",
    r"\bEI\s+BENEFIT\b|\bSERVICE\s+CANADA\b",
)

NSF_REVERSAL_PATTERNS = (
    r"\bNSF\b",
    r"RETURNED\s+ITEM",
    r"\bITEM\s+RETURNED\b",
    r"\bUNPAID\b",
    r"DISHONOURED",
    r"FRAIS\s+EFFET\s+RET",
    r"\bREVERSE\b",
    r"\bRECLAIM\b",
)

POS_PROCESSOR_PATTERN = (
    r"STRIPE|SQUARE|SQ \*|MONERIS|CLOVER|FIRST DATA|FISERV|FDMS|ELAVON|"
    r"GLOBAL PAY|CHASE MERCH|PAYMENTECH|HELCIM|TD MERCH|MONETICO|"
    r"DESJARDINS PAIEMENT|LIGHTSPEED|SHOPIFY|ADYEN|BAMBORA|WORLDLINE|"
    r"TOAST|NUVEI|PIVOTAL|PAYFACTO|ZETTLE|PAYPAL|KLARNA|AMAZON|"
    r"UBER|DOORDASH|SKIPTHEDISHES|SKIP THE DISHES|MSP/DIV|MSP/ DIV|"
    r"\b(?:VI|MC|EF|AMX)\d{4}\b"
)
