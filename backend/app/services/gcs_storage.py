import asyncio
import hashlib
import os
from typing import Optional
import uuid

from dotenv import load_dotenv
from google.cloud import storage

load_dotenv()

GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")

_storage_client: Optional[storage.Client] = None


def _get_storage_client() -> storage.Client:
    """Lazy-initialize and reuse the GCS client across requests."""
    global _storage_client
    if _storage_client is None:
        _storage_client = storage.Client()
    return _storage_client


def _require_bucket_name() -> str:
    if not GCS_BUCKET_NAME:
        raise RuntimeError("GCS_BUCKET_NAME environment variable is not set.")
    return GCS_BUCKET_NAME


def compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


async def upload_bytes_to_gcs(
    data: bytes,
    original_filename: str,
    content_type: str = "text/plain",
    sha256_hash: Optional[str] = None,
) -> str:
    """Upload raw DSC bytes to GCS in a worker thread and return the gs:// URI."""
    bucket_name = _require_bucket_name()
    ext = (
        original_filename.rsplit(".", 1)[-1].lower()
        if "." in original_filename
        else "dat"
    )
    blob_name = f"raw/{uuid.uuid4()}.{ext}"

    def _sync_upload() -> str:
        client = _get_storage_client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        blob.metadata = {
            "original_filename": original_filename,
            "sha256": sha256_hash or compute_sha256(data),
        }
        blob.upload_from_string(data, content_type=content_type)
        return f"gs://{bucket_name}/{blob_name}"

    return await asyncio.to_thread(_sync_upload)


async def download_bytes_from_gcs(storage_uri: str) -> bytes:
    """Download raw DSC bytes from a gs://bucket/path URI for analysis tools."""
    if not storage_uri.startswith("gs://"):
        raise ValueError(f"Invalid GCS URI: {storage_uri}")

    without_scheme = storage_uri[5:]
    bucket_name, _, blob_name = without_scheme.partition("/")
    if not bucket_name or not blob_name:
        raise ValueError(f"Malformed GCS URI: {storage_uri}")

    def _sync_download() -> bytes:
        client = _get_storage_client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        return blob.download_as_bytes()

    return await asyncio.to_thread(_sync_download)
