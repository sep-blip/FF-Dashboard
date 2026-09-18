from storage.backends import LocalObjectStorage


def test_local_storage_writes_and_hashes(tmp_path):
    storage = LocalObjectStorage(tmp_path)
    stored = storage.put_bytes(
        key="application-1/statements/a.pdf",
        payload=b"pdf-bytes",
        content_type="application/pdf",
    )
    assert stored.uri.startswith("file://")
    assert stored.size_bytes == len(b"pdf-bytes")
    assert (tmp_path / "application-1/statements/a.pdf").read_bytes() == b"pdf-bytes"


def test_local_storage_rejects_path_escape(tmp_path):
    storage = LocalObjectStorage(tmp_path)
    try:
        storage.put_bytes(
            key="../../escape.pdf",
            payload=b"x",
            content_type="application/pdf",
        )
    except ValueError:
        pass
    else:
        raise AssertionError("Expected path traversal protection.")
