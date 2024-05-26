import uuid
import io
import os

from app.config import (
    MINIO_HOSTNAME,
    MINIO_ACCESS_KEY,
    MINIO_SECRET_KEY,
    MINIO_BUCKET,
)
from minio import Minio

client = Minio(
    MINIO_HOSTNAME,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=False,
)
bucket_name = MINIO_BUCKET


async def upload_file(file, extension):
    found = client.bucket_exists(bucket_name)

    if not found:
        client.make_bucket(bucket_name)
    else:
        print(f"Bucket {bucket_name} already exists")

    # Generate a UUID for the file name
    file_uuid = str(uuid.uuid4())
    file_name = f"{file_uuid}.{extension}"

    file_content = await file.read()

    client.put_object(
        bucket_name,
        file_name,
        io.BytesIO(file_content),
        length=len(file_content),
    )

    # Warning! MinIO share the link of object only for 7 days!
    url = client.presigned_get_object(bucket_name, file_name)

    return url, file_uuid


def delete_file(file):
    client.remove_object(bucket_name, f"{file.file_uuid}.{file.format}")

    return None


def remove_extension(filename):
    # Split the filename into base and extension
    base, ext = os.path.splitext(filename)
    # Return the base part of the filename
    return base
