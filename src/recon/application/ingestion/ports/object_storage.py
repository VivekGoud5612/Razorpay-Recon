from __future__ import annotations

from typing import BinaryIO, Protocol


class ObjectStorage(Protocol):

    async def put(
        self,
        object_key: str,
        content: BinaryIO,
        content_type: str,
    ) -> None:
        ...

    async def get(
        self,
        object_key: str,
    ) -> bytes:
        ...

    async def delete(
        self,
        object_key: str,
    ) -> None:
        ...