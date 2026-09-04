from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class ImportIdentity:
    import_id: str
    object_key: str


class ImportIdentityService:
    def create(
        self,
        merchant_source_id: str,
        filename: str,
    ) -> ImportIdentity:
        import_id = f"imp_{uuid4().hex}"

        object_key = (
            f"imports/"
            f"{merchant_source_id}/"
            f"{import_id}/"
            f"{filename}"
        )

        return ImportIdentity(
            import_id=import_id,
            object_key=object_key,
        )