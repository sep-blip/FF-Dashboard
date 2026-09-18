from __future__ import annotations

import os
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from typing import Iterator
from uuid import UUID

import psycopg
from psycopg import Connection
from psycopg.types.json import Jsonb

from engine_v2.pipeline import UnderwritingPipelineResult
from engine_v2.models import TransactionDirection


class DatabaseConfigurationError(RuntimeError):
    pass


def database_url_from_env() -> str:
    value = os.getenv("DATABASE_URL")
    if not value:
        raise DatabaseConfigurationError(
            "DATABASE_URL is not configured."
        )
    return value


@contextmanager
def connect_database(url: str | None = None) -> Iterator[Connection]:
    connection = psycopg.connect(url or database_url_from_env())
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_schema(connection: Connection) -> None:
    schema_path = Path(__file__).with_name("schema.sql")
    connection.execute(schema_path.read_text(encoding="utf-8"))
    connection.commit()


class UnderwritingRepository:
    def __init__(self, connection: Connection):
        self.connection = connection

    def create_application(
        self,
        *,
        legal_name: str,
        dba_name: str | None = None,
        industry_code: str | None = None,
        requested_amount: float | None = None,
        requested_term_business_days: int | None = None,
    ) -> tuple[UUID, UUID]:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO merchants (legal_name, dba_name, industry_code)
                VALUES (%s, %s, %s)
                RETURNING merchant_id
                """,
                (legal_name, dba_name, industry_code),
            )
            merchant_id = cursor.fetchone()[0]

            cursor.execute(
                """
                INSERT INTO applications (
                    merchant_id,
                    requested_amount,
                    requested_term_business_days
                )
                VALUES (%s, %s, %s)
                RETURNING application_id
                """,
                (
                    merchant_id,
                    requested_amount,
                    requested_term_business_days,
                ),
            )
            application_id = cursor.fetchone()[0]

            self._audit(
                cursor,
                application_id=application_id,
                event_type="application_created",
                entity_type="application",
                entity_id=str(application_id),
                actor_type="system",
                actor_id=None,
                payload={
                    "legal_name": legal_name,
                    "requested_amount": requested_amount,
                    "requested_term_business_days": requested_term_business_days,
                },
            )

        return merchant_id, application_id

    def persist_statement_analysis(
        self,
        *,
        application_id: UUID | str,
        result: UnderwritingPipelineResult,
        storage_uri_by_sha256: dict[str, str],
        actor_id: str | None = None,
    ) -> None:
        """Persist one analysis snapshot atomically.

        Raw PDF bytes are intentionally not written into PostgreSQL. The caller
        must first place each document in durable object storage and provide its
        URI keyed by SHA-256. Missing storage URIs fail the transaction rather
        than creating an unauditable document record.
        """

        classification_by_id = {
            transaction.transaction_id: transaction
            for transaction in result.transactions
        }

        with self.connection.cursor() as cursor:
            for statement in result.statements:
                storage_uri = storage_uri_by_sha256.get(statement.file_sha256)
                if not storage_uri:
                    raise ValueError(
                        f"Missing durable storage URI for {statement.source_file} "
                        f"({statement.file_sha256})."
                    )

                cursor.execute(
                    """
                    INSERT INTO documents (
                        application_id,
                        document_type,
                        original_filename,
                        storage_uri,
                        sha256,
                        mime_type,
                        page_count,
                        ingestion_status
                    )
                    VALUES (%s, 'BANK_STATEMENT', %s, %s, %s, 'application/pdf', %s, 'PARSED')
                    ON CONFLICT (application_id, sha256)
                    DO UPDATE SET
                        original_filename = EXCLUDED.original_filename,
                        storage_uri = EXCLUDED.storage_uri,
                        page_count = EXCLUDED.page_count,
                        ingestion_status = EXCLUDED.ingestion_status
                    RETURNING document_id
                    """,
                    (
                        application_id,
                        statement.source_file,
                        storage_uri,
                        statement.file_sha256,
                        statement.page_count,
                    ),
                )
                document_id = cursor.fetchone()[0]

                total_credits = sum(
                    (
                        transaction.amount
                        for transaction in statement.transactions
                        if transaction.direction == TransactionDirection.CREDIT
                    ),
                    Decimal("0"),
                )
                total_debits = sum(
                    (
                        transaction.amount
                        for transaction in statement.transactions
                        if transaction.direction == TransactionDirection.DEBIT
                    ),
                    Decimal("0"),
                )

                cursor.execute(
                    """
                    INSERT INTO statements (
                        statement_id,
                        document_id,
                        period_start,
                        period_end,
                        coverage_status,
                        coverage_pct,
                        opening_balance,
                        closing_balance,
                        extracted_total_credits,
                        extracted_total_debits,
                        reconciliation_variance,
                        reconciliation_status,
                        integrity_score,
                        integrity_status
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (document_id, statement_id)
                    DO UPDATE SET
                        period_start = EXCLUDED.period_start,
                        period_end = EXCLUDED.period_end,
                        coverage_status = EXCLUDED.coverage_status,
                        coverage_pct = EXCLUDED.coverage_pct,
                        opening_balance = EXCLUDED.opening_balance,
                        closing_balance = EXCLUDED.closing_balance,
                        extracted_total_credits = EXCLUDED.extracted_total_credits,
                        extracted_total_debits = EXCLUDED.extracted_total_debits,
                        reconciliation_variance = EXCLUDED.reconciliation_variance,
                        reconciliation_status = EXCLUDED.reconciliation_status,
                        integrity_score = EXCLUDED.integrity_score,
                        integrity_status = EXCLUDED.integrity_status
                    RETURNING statement_record_id
                    """,
                    (
                        statement.statement_id,
                        document_id,
                        statement.period_start,
                        statement.period_end,
                        (
                            statement.coverage.status.value
                            if statement.coverage
                            else "UNKNOWN"
                        ),
                        (
                            statement.coverage.coverage_pct
                            if statement.coverage
                            else None
                        ),
                        statement.opening_balance,
                        statement.closing_balance,
                        total_credits,
                        total_debits,
                        statement.reconciliation_variance,
                        statement.reconciliation_status,
                        (
                            statement.integrity.score
                            if statement.integrity
                            else None
                        ),
                        (
                            statement.integrity.status
                            if statement.integrity
                            else None
                        ),
                    ),
                )
                statement_record_id = cursor.fetchone()[0]

                for raw_transaction in statement.transactions:
                    cursor.execute(
                        """
                        INSERT INTO transactions (
                            transaction_id,
                            statement_record_id,
                            transaction_date,
                            description,
                            amount,
                            direction,
                            running_balance,
                            source_page,
                            raw_text
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (statement_record_id, transaction_id)
                        DO UPDATE SET
                            transaction_date = EXCLUDED.transaction_date,
                            description = EXCLUDED.description,
                            amount = EXCLUDED.amount,
                            direction = EXCLUDED.direction,
                            running_balance = EXCLUDED.running_balance,
                            source_page = EXCLUDED.source_page,
                            raw_text = EXCLUDED.raw_text
                        RETURNING transaction_record_id
                        """,
                        (
                            raw_transaction.transaction_id,
                            statement_record_id,
                            raw_transaction.transaction_date,
                            raw_transaction.description,
                            raw_transaction.amount,
                            raw_transaction.direction.value,
                            raw_transaction.running_balance,
                            raw_transaction.page,
                            raw_transaction.raw_text,
                        ),
                    )
                    transaction_record_id = cursor.fetchone()[0]

                    classification = classification_by_id.get(
                        raw_transaction.transaction_id
                    )
                    if classification is None:
                        continue

                    cursor.execute(
                        """
                        UPDATE transaction_classifications
                        SET is_current = FALSE
                        WHERE transaction_record_id = %s
                          AND is_current = TRUE
                        """,
                        (transaction_record_id,),
                    )
                    cursor.execute(
                        """
                        INSERT INTO transaction_classifications (
                            transaction_record_id,
                            transaction_id,
                            category,
                            confidence,
                            source,
                            reason,
                            model_name,
                            prompt_version,
                            is_current
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, TRUE)
                        """,
                        (
                            transaction_record_id,
                            classification.transaction_id,
                            classification.category,
                            None,
                            classification.classification_source,
                            classification.classification_reason,
                            classification.classification_model,
                            "transaction-classifier-v2",
                        ),
                    )

            cursor.execute(
                """
                DELETE FROM mca_positions
                WHERE application_id = %s
                  AND source = 'AUTO'
                """,
                (application_id,),
            )
            for position in result.mca_positions:
                cursor.execute(
                    """
                    INSERT INTO mca_positions (
                        application_id,
                        lender_name,
                        lender_tier,
                        payment_amount,
                        payment_frequency,
                        monthly_payment,
                        first_observed_date,
                        last_observed_date,
                        observed_payments,
                        status,
                        source
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'ACTIVE', 'AUTO')
                    """,
                    (
                        application_id,
                        position.lender,
                        position.tier,
                        position.payment_amount,
                        position.frequency,
                        position.monthly_payment,
                        position.first_observed_date,
                        position.last_observed_date,
                        position.observed_payments,
                    ),
                )

            if result.revenue_baseline and result.debt_ratios:
                cursor.execute(
                    """
                    INSERT INTO underwriting_metrics (
                        application_id,
                        average_monthly_true_revenue,
                        mca_position_count,
                        monthly_mca_debt_service,
                        total_debt_ratio_pct,
                        revenue_basis,
                        calculation_version,
                        inputs
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        application_id,
                        result.revenue_baseline.average_monthly_true_revenue,
                        len(result.mca_positions),
                        result.debt_ratios.total_monthly_debt_service,
                        result.debt_ratios.total_debt_ratio_pct,
                        result.revenue_baseline.basis,
                        "underwriting-engine-v2",
                        Jsonb(
                            {
                                "monthly_true_revenue": result.monthly_true_revenue,
                                "months_used": list(
                                    result.revenue_baseline.months_used
                                ),
                                "partial_months_excluded": list(
                                    result.revenue_baseline.partial_months_excluded
                                ),
                                "warnings": result.warnings,
                            }
                        ),
                    ),
                )

            self._audit(
                cursor,
                application_id=application_id,
                event_type="statement_analysis_persisted",
                entity_type="application",
                entity_id=str(application_id),
                actor_type="user" if actor_id else "system",
                actor_id=actor_id,
                payload={
                    "statement_count": len(result.statements),
                    "transaction_count": len(result.transactions),
                    "mca_position_count": len(result.mca_positions),
                    "warnings": result.warnings,
                },
            )

    def _audit(
        self,
        cursor,
        *,
        application_id,
        event_type: str,
        entity_type: str,
        entity_id: str,
        actor_type: str,
        actor_id: str | None,
        payload: dict,
    ) -> None:
        cursor.execute(
            """
            INSERT INTO audit_events (
                application_id,
                event_type,
                entity_type,
                entity_id,
                actor_type,
                actor_id,
                payload
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                application_id,
                event_type,
                entity_type,
                entity_id,
                actor_type,
                actor_id,
                Jsonb(payload),
            ),
        )
