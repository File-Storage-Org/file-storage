import io
from app.config import (
    MINIO_HOSTNAME,
    MINIO_ACCESS_KEY,
    MINIO_SECRET_KEY,
    MINIO_BUCKET,
)
from app.schemas import File
from minio import Minio

client = Minio(
    MINIO_HOSTNAME,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=False,
)
bucket_name = MINIO_BUCKET


async def upload_file(file: bytes, filename: str) -> str:
    found = client.bucket_exists(bucket_name)

    if not found:
        client.make_bucket(bucket_name)

    client.put_object(
        bucket_name,
        filename,
        io.BytesIO(file),
        length=len(file),
    )

    return f"http://{MINIO_HOSTNAME}/{bucket_name}/{filename}"


def delete_file(file: File) -> None:
    client.remove_object(bucket_name, f"{file.name}{file.format}")
