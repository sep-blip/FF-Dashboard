CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS merchants (
    merchant_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    legal_name TEXT NOT NULL,
    dba_name TEXT,
    industry_code TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS applications (
    application_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    merchant_id UUID NOT NULL REFERENCES merchants(merchant_id),
    status TEXT NOT NULL DEFAULT 'DRAFT',
    requested_amount NUMERIC(18,2),
    requested_term_business_days INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (requested_amount IS NULL OR requested_amount >= 0)
);

CREATE TABLE IF NOT EXISTS documents (
    document_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES applications(application_id) ON DELETE CASCADE,
    document_type TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    storage_uri TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    mime_type TEXT,
    page_count INTEGER,
    ingestion_status TEXT NOT NULL DEFAULT 'UPLOADED',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (application_id, sha256)
);

CREATE TABLE IF NOT EXISTS statements (
    statement_record_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    statement_id TEXT NOT NULL,
    document_id UUID NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    account_fingerprint TEXT,
    bank_id TEXT,
    bank_name TEXT,
    extraction_quality_score INTEGER,
    extraction_quality_status TEXT,
    extraction_mode TEXT,
    period_start DATE,
    period_end DATE,
    coverage_status TEXT NOT NULL DEFAULT 'UNKNOWN',
    coverage_pct NUMERIC(6,2),
    opening_balance NUMERIC(18,2),
    closing_balance NUMERIC(18,2),
    extracted_total_credits NUMERIC(18,2),
    extracted_total_debits NUMERIC(18,2),
    reconciliation_variance NUMERIC(18,2),
    reconciliation_status TEXT,
    integrity_score INTEGER,
    integrity_status TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (document_id, statement_id),
    CHECK (coverage_pct IS NULL OR (coverage_pct >= 0 AND coverage_pct <= 100)),
    CHECK (
        extraction_quality_score IS NULL
        OR (extraction_quality_score >= 0 AND extraction_quality_score <= 100)
    ),
    CHECK (integrity_score IS NULL OR (integrity_score >= 0 AND integrity_score <= 100))
);

CREATE TABLE IF NOT EXISTS transactions (
    transaction_record_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_id TEXT NOT NULL,
    statement_record_id UUID NOT NULL REFERENCES statements(statement_record_id) ON DELETE CASCADE,
    transaction_date DATE NOT NULL,
    description TEXT NOT NULL,
    amount NUMERIC(18,2) NOT NULL,
    direction TEXT NOT NULL,
    running_balance NUMERIC(18,2),
    source_page INTEGER,
    raw_text TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (statement_record_id, transaction_id),
    CHECK (amount > 0),
    CHECK (direction IN ('credit', 'debit'))
);

CREATE TABLE IF NOT EXISTS transaction_classifications (
    classification_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_record_id UUID NOT NULL REFERENCES transactions(transaction_record_id) ON DELETE CASCADE,
    transaction_id TEXT NOT NULL,
    category TEXT NOT NULL,
    subcategory TEXT,
    confidence NUMERIC(5,4),
    source TEXT NOT NULL,
    reason TEXT,
    model_name TEXT,
    prompt_version TEXT,
    is_current BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_current_transaction_classification
    ON transaction_classifications(transaction_record_id)
    WHERE is_current = TRUE;

CREATE TABLE IF NOT EXISTS mca_positions (
    mca_position_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES applications(application_id) ON DELETE CASCADE,
    lender_name TEXT NOT NULL,
    lender_tier TEXT,
    payment_amount NUMERIC(18,2) NOT NULL,
    payment_frequency TEXT NOT NULL,
    monthly_payment NUMERIC(18,2) NOT NULL,
    first_observed_date DATE,
    last_observed_date DATE,
    observed_payments INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    source TEXT NOT NULL DEFAULT 'AUTO',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (payment_amount >= 0),
    CHECK (monthly_payment >= 0)
);

CREATE TABLE IF NOT EXISTS credit_reports (
    credit_report_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES applications(application_id) ON DELETE CASCADE,
    document_id UUID REFERENCES documents(document_id),
    owner_name TEXT,
    fico_score INTEGER,
    revolving_utilization_pct NUMERIC(7,3),
    total_high_credit NUMERIC(18,2),
    active_collections_count INTEGER,
    total_collections_amount NUMERIC(18,2),
    bankruptcies_found BOOLEAN,
    number_of_mortgages INTEGER,
    extracted_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS underwriting_metrics (
    metric_snapshot_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES applications(application_id) ON DELETE CASCADE,
    average_monthly_true_revenue NUMERIC(18,2),
    gross_monthly_deposits NUMERIC(18,2),
    revenue_trend_pct NUMERIC(9,4),
    revenue_volatility_pct NUMERIC(9,4),
    concentration_pct NUMERIC(9,4),
    negative_days INTEGER,
    nsf_count INTEGER,
    mca_position_count INTEGER,
    monthly_mca_debt_service NUMERIC(18,2),
    total_debt_ratio_pct NUMERIC(9,4),
    revenue_basis TEXT,
    calculation_version TEXT NOT NULL,
    inputs JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS offers (
    offer_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES applications(application_id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'PROPOSED',
    recommended_advance NUMERIC(18,2) NOT NULL,
    factor_rate NUMERIC(8,4),
    term_business_days INTEGER,
    daily_payment NUMERIC(18,2),
    projected_monthly_payment NUMERIC(18,2),
    projected_total_debt_ratio_pct NUMERIC(9,4),
    policy_version TEXT NOT NULL,
    calculation_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS review_items (
    review_item_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES applications(application_id) ON DELETE CASCADE,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    severity TEXT NOT NULL,
    review_code TEXT NOT NULL,
    message TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'OPEN',
    resolution TEXT,
    resolved_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS audit_events (
    audit_event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID REFERENCES applications(application_id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    actor_type TEXT NOT NULL,
    actor_id TEXT,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_documents_application ON documents(application_id);
CREATE INDEX IF NOT EXISTS idx_statements_document ON statements(document_id);
CREATE INDEX IF NOT EXISTS idx_statements_logical_id ON statements(statement_id);
CREATE INDEX IF NOT EXISTS idx_transactions_statement_date ON transactions(statement_record_id, transaction_date);
CREATE INDEX IF NOT EXISTS idx_transactions_logical_id ON transactions(transaction_id);
CREATE INDEX IF NOT EXISTS idx_mca_positions_application ON mca_positions(application_id);
CREATE INDEX IF NOT EXISTS idx_metrics_application_created ON underwriting_metrics(application_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_offers_application_created ON offers(application_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_review_items_application_status ON review_items(application_id, status);
CREATE INDEX IF NOT EXISTS idx_audit_application_created ON audit_events(application_id, created_at DESC);
