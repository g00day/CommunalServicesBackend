import asyncio
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import boto3
from botocore.client import Config
from fastapi import HTTPException, UploadFile

from app.core.config import settings


def _ensure_storage_config() -> tuple[str, str, str, str]:
    required_values = {
        "S3_BUCKET": settings.S3_BUCKET,
        "S3_ACCESS_KEY_ID": settings.S3_ACCESS_KEY_ID,
        "S3_SECRET_ACCESS_KEY": settings.S3_SECRET_ACCESS_KEY,
        "S3_ENDPOINT_URL": settings.S3_ENDPOINT_URL,
    }
    missing = [name for name, value in required_values.items() if not value]
    if missing:
        raise HTTPException(
            status_code=500,
            detail=f"S3-хранилище не настроено: отсутствуют параметры {', '.join(missing)}",
        )

    return (
        settings.S3_BUCKET,
        settings.S3_ACCESS_KEY_ID,
        settings.S3_SECRET_ACCESS_KEY,
        settings.S3_ENDPOINT_URL,
    )


def _build_object_key(scope: str, owner_id: int, original_name: str) -> str:
    safe_name = Path(original_name).name or "file"
    return f"{scope}/{owner_id}/{uuid4().hex}_{safe_name}"


def _build_file_url(bucket: str, object_key: str) -> str:
    if settings.S3_PUBLIC_BASE_URL:
        base = settings.S3_PUBLIC_BASE_URL.rstrip("/")
        return f"{base}/{object_key}"
    endpoint = settings.S3_ENDPOINT_URL.rstrip("/")
    return f"{endpoint}/{bucket}/{object_key}"


def _extract_object_key(file_url: str | None = None, file_path: str | None = None) -> str:
    if file_path:
        return file_path.lstrip("/")
    if not file_url:
        raise HTTPException(status_code=400, detail="Не указано расположение файла")

    parsed = urlparse(file_url)
    path = parsed.path.lstrip("/")
    bucket = settings.S3_BUCKET
    if bucket and path.startswith(f"{bucket}/"):
        return path[len(bucket) + 1 :]
    return path


def _get_s3_client():
    bucket, access_key_id, secret_access_key, endpoint_url = _ensure_storage_config()
    client = boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        region_name=settings.S3_REGION,
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
        config=Config(signature_version="s3v4"),
    )
    return client, bucket


async def upload_file_to_storage(upload_file: UploadFile, scope: str, owner_id: int) -> tuple[str, str]:
    if not upload_file.filename:
        raise HTTPException(status_code=400, detail="Не указано имя файла")

    file_bytes = await upload_file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Пустые файлы не допускаются")

    object_key = _build_object_key(scope, owner_id, upload_file.filename)
    content_type = upload_file.content_type or "application/octet-stream"

    def _upload() -> tuple[str, str]:
        client, bucket = _get_s3_client()
        client.put_object(
            Bucket=bucket,
            Key=object_key,
            Body=file_bytes,
            ContentType=content_type,
        )
        return object_key, _build_file_url(bucket, object_key)

    try:
        return await asyncio.to_thread(_upload)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Не удалось загрузить файл в хранилище: {exc}") from exc


async def generate_download_url(file_url: str | None = None, file_path: str | None = None, expires_in: int = 3600) -> str:
    object_key = _extract_object_key(file_url=file_url, file_path=file_path)

    def _generate() -> str:
        client, bucket = _get_s3_client()
        return client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": bucket,
                "Key": object_key,
            },
            ExpiresIn=expires_in,
        )

    try:
        return await asyncio.to_thread(_generate)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Не удалось сформировать ссылку на скачивание: {exc}") from exc
