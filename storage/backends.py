from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class StoredObject:
    uri: str
    sha256: str
    size_bytes: int


class ObjectStorage(Protocol):
    def put_bytes(
        self,
        *,
        key: str,
        payload: bytes,
        content_type: str,
    ) -> StoredObject:
        ...


class LocalObjectStorage:
    """Development-only filesystem storage.

    Production deployments should use S3ObjectStorage or another durable remote
    implementation. The interface keeps persistence logic independent from the
    storage provider.
    """

    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def put_bytes(
        self,
        *,
        key: str,
        payload: bytes,
        content_type: str,
    ) -> StoredObject:
        destination = (self.root / key).resolve()
        if self.root not in destination.parents and destination != self.root:
            raise ValueError("Object key escapes configured storage root.")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)
        sha = hashlib.sha256(payload).hexdigest()
        return StoredObject(
            uri=f"file://{destination}",
            sha256=sha,
            size_bytes=len(payload),
        )


class S3ObjectStorage:
    def __init__(
        self,
        *,
        bucket: str,
        region: str | None = None,
        endpoint_url: str | None = None,
        prefix: str = "",
        server_side_encryption: str | None = "AES256",
    ):
        import boto3

        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self.server_side_encryption = server_side_encryption
        self.client = boto3.client(
            "s3",
            region_name=region,
            endpoint_url=endpoint_url,
        )

    def _full_key(self, key: str) -> str:
        clean = key.lstrip("/")
        return f"{self.prefix}/{clean}" if self.prefix else clean

    def put_bytes(
        self,
        *,
        key: str,
        payload: bytes,
        content_type: str,
    ) -> StoredObject:
        full_key = self._full_key(key)
        kwargs = {
            "Bucket": self.bucket,
            "Key": full_key,
            "Body": payload,
            "ContentType": content_type,
        }
        if self.server_side_encryption:
            kwargs["ServerSideEncryption"] = self.server_side_encryption

        self.client.put_object(**kwargs)
        sha = hashlib.sha256(payload).hexdigest()
        return StoredObject(
            uri=f"s3://{self.bucket}/{full_key}",
            sha256=sha,
            size_bytes=len(payload),
        )


def storage_from_env() -> ObjectStorage:
    backend = os.getenv("OBJECT_STORAGE_BACKEND", "local").strip().lower()

    if backend == "local":
        return LocalObjectStorage(
            os.getenv("LOCAL_OBJECT_STORAGE_ROOT", "./var/uploads")
        )

    if backend == "s3":
        bucket = os.getenv("S3_BUCKET")
        if not bucket:
            raise RuntimeError(
                "S3_BUCKET is required when OBJECT_STORAGE_BACKEND=s3."
            )
        return S3ObjectStorage(
            bucket=bucket,
            region=os.getenv("AWS_REGION"),
            endpoint_url=os.getenv("S3_ENDPOINT_URL"),
            prefix=os.getenv("S3_PREFIX", ""),
            server_side_encryption=os.getenv(
                "S3_SERVER_SIDE_ENCRYPTION",
                "AES256",
            ) or None,
        )

    raise RuntimeError(
        f"Unsupported OBJECT_STORAGE_BACKEND: {backend}"
    )
