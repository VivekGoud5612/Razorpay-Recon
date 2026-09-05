from __future__ import annotations

from typing import Any

from recon.application.ingestion.ports.object_storage import ObjectStorage


class DocumentTools:
    """Retrieves the raw merchant source file (the whole uploaded CSV/JSON
    blob) backing an object_key already present in an EvidenceRef.

    This class itself is unscoped -- it will fetch any object_key that
    exists in the configured object store. Callers (LLMInvestigator) are
    responsible for only exposing it, via tool_handlers, for object_keys
    that belong to the current investigation's EvidencePackage.
    """

    def __init__(self, storage: ObjectStorage) -> None:
        self._storage = storage

    async def get_document(self, object_key: str) -> str:
        content = await self._storage.get(object_key)
        return content.decode("utf-8")

    async def search_document(
        self,
        object_key: str,
        query: str,
    ) -> str:
        content = await self.get_document(object_key)

        return "\n".join(
            line
            for line in content.splitlines()
            if query.lower() in line.lower()
        )

    def definitions(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "name": "get_document",
                "description": (
                    "Retrieve the complete contents of a merchant source "
                    "document using an object key from the supplied evidence."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "object_key": {
                            "type": "string",
                            "description": (
                                "Exact object key from an EvidenceRef."
                            ),
                        },
                    },
                    "required": ["object_key"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
            {
                "type": "function",
                "name": "search_document",
                "description": (
                    "Search a merchant source document using an exact object "
                    "key and a query. Use this for large documents."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "object_key": {
                            "type": "string",
                            "description": (
                                "Exact object key from an EvidenceRef."
                            ),
                        },
                        "query": {
                            "type": "string",
                            "description": (
                                "Value, identifier, or text to search for."
                            ),
                        },
                    },
                    "required": ["object_key", "query"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
        ]