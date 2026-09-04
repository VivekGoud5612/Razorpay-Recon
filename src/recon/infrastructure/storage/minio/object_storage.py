from __future__ import annotations

from io import BytesIO

from minio import Minio

from recon.application.ingestion.ports.object_storage import ObjectStorage


class MinioObjectStorage:
    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket_name: str,
        secure: bool = False,
    ) -> None:
        self._client = Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
        )
        self._bucket = bucket_name

    def ensure_bucket(self) -> None:
        if not self._client.bucket_exists(self._bucket):
            self._client.make_bucket(self._bucket)

    async def put(
        self,
        object_key: str,
        content:bytes,
        content_type: str,
    ) -> None:

        self._client.put_object(
            self._bucket,
            object_key,
            BytesIO(content),
            length=len(content),
            content_type=content_type,
        )

    async def get(
        self,
        object_key: str,
    ) -> bytes:
        response = self._client.get_object(
            self._bucket,
            object_key,
        )

        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    async def delete(
        self,
        object_key: str,
    ) -> None:
        self._client.remove_object(
            self._bucket,
            object_key,
        )