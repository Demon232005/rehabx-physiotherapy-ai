"""S3-compatible object storage adapter (used when STORAGE_BACKEND=s3)."""
from __future__ import annotations

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.core.config import get_settings


def _client():
    settings = get_settings()
    kwargs: dict = {"config": Config(signature_version="s3v4", retries={"max_attempts": 2})}
    if settings.s3_endpoint_url:
        kwargs["endpoint_url"] = settings.s3_endpoint_url
    if settings.s3_access_key and settings.s3_secret_key:
        kwargs["aws_access_key_id"] = settings.s3_access_key
        kwargs["aws_secret_access_key"] = settings.s3_secret_key
    return boto3.client("s3", **kwargs)


def _bucket() -> str:
    return get_settings().s3_bucket


def upload_object(key: str, data: bytes, content_type: str) -> None:
    client = _client()
    client.put_object(
        Bucket=_bucket(),
        Key=f"xray/{key}",
        Body=data,
        ContentType=content_type,
        ServerSideEncryption="AES256",
    )


def download_object(key: str) -> bytes:
    client = _client()
    try:
        response = client.get_object(Bucket=_bucket(), Key=f"xray/{key}")
        return response["Body"].read()
    except ClientError as exc:
        raise FileNotFoundError(f"Object {key} not found in storage") from exc


def delete_object(key: str) -> None:
    client = _client()
    try:
        client.delete_object(Bucket=_bucket(), Key=f"xray/{key}")
    except ClientError:
        pass
