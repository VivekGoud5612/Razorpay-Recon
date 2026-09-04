from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class DocumentContent:
    object_key: str
    content: str


class DocumentProvider(Protocol):

    async def get_document(self, object_key: str) -> DocumentContent:
        ...

    async def search_document(
        self,
        object_key: str,
        query: str,
    ) -> DocumentContent:
        ...