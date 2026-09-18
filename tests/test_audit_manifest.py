from engine_v2.audit_manifest import ENGINE_VERSION, build_audit_manifest


def test_audit_manifest_handles_empty_run():
    manifest = build_audit_manifest(
        statements=[],
        classifier_model="classifier-model",
        vision_model="vision-model",
        enable_ocr=False,
        enable_vision_fallback=True,
    )
    assert manifest.engine_version == ENGINE_VERSION
    assert manifest.run_id
    assert manifest.source_documents == []
