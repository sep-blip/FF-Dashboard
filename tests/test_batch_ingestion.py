from engine_v2.batch_ingestion import parse_statement_batch


def test_duplicate_files_are_skipped_before_parse():
    # Bytes need not be a valid PDF for this behavior; the duplicate is detected
    # before parsing and the first item degrades gracefully.
    result = parse_statement_batch(
        [("a.pdf", b"not-a-pdf"), ("b.pdf", b"not-a-pdf")]
    )
    assert len(result.statements) == 1
    assert len(result.skipped_duplicates) == 1
    assert "duplicate of a.pdf" in result.skipped_duplicates[0]
