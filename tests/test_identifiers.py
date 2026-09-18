from datetime import date

from engine_v2.identifiers import stable_transaction_id


def test_transaction_id_is_repeatable_and_occurrence_sensitive():
    kwargs = dict(
        statement_id="stmt_abc",
        transaction_date=date(2026, 9, 17),
        description="Stripe Payout",
        amount="1234.56",
        direction="credit",
    )
    a = stable_transaction_id(**kwargs, occurrence=0)
    b = stable_transaction_id(**kwargs, occurrence=0)
    c = stable_transaction_id(**kwargs, occurrence=1)
    assert a == b
    assert a != c
