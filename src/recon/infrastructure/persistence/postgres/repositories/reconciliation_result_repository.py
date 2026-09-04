from __future__ import annotations

import asyncpg

from recon.application.reconciliation.dto.response import ReconcileSettlementResponse
from recon.application.reconciliation.dto.run import ReconciliationRunResponse
from recon.application.reconciliation.ports.result_repository import ReconciliationResultRepository
from recon.domain.graph.entity import EntityReference
from recon.domain.reconciliation.evidence import EvidenceRef
from recon.domain.reconciliation.finding import ReconciliationFinding


class ReconciliationPostgresResultRepository(ReconciliationResultRepository):

    def __init__(self, db) -> None:
        self._db = db

    async def save(
        self,
        settlement_id: str,
        findings: list[ReconciliationFinding],
        evidence: list[EvidenceRef],
    ) -> None:
        async with self._db.acquire() as conn:
            async with conn.transaction():
                # A re-run must *replace* the settlement's findings/evidence,
                # not accumulate alongside whatever a previous run produced --
                # otherwise a finding that no longer applies (e.g. the
                # underlying data was fixed) lingers forever. Join rows first
                # to respect the FKs into both parent tables.
                await conn.execute(
                    "DELETE FROM reconciliation_finding_evidence WHERE settlement_id = $1",
                    settlement_id,
                )
                await conn.execute(
                    "DELETE FROM reconciliation_findings WHERE settlement_id = $1",
                    settlement_id,
                )
                await conn.execute(
                    "DELETE FROM reconciliation_evidence WHERE settlement_id = $1",
                    settlement_id,
                )

                await self._save_findings(conn, settlement_id, findings)
                await self._save_evidence(conn, settlement_id, evidence)
                await self._save_finding_evidence(conn, settlement_id, findings)

    async def _save_findings(
        self,
        conn: asyncpg.Connection,
        settlement_id: str,
        findings: list[ReconciliationFinding],
    ) -> None:
        if not findings:
            return

        await conn.executemany(
            """
            INSERT INTO reconciliation_findings (
                settlement_id,
                finding_id,
                code,
                severity,
                source,
                entity_type,
                entity_id,
                message
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (settlement_id, finding_id)
            DO UPDATE SET
                code = EXCLUDED.code,
                severity = EXCLUDED.severity,
                source = EXCLUDED.source,
                entity_type = EXCLUDED.entity_type,
                entity_id = EXCLUDED.entity_id,
                message = EXCLUDED.message
            """,
            [
                (
                    settlement_id,
                    finding.finding_id,
                    finding.code,
                    finding.severity,
                    finding.affected_entity.source,
                    finding.affected_entity.entity_type,
                    finding.affected_entity.entity_id,
                    finding.message,
                )
                for finding in findings
            ],
        )

    async def _save_evidence(
        self,
        conn: asyncpg.Connection,
        settlement_id: str,
        evidence: list[EvidenceRef],
    ) -> None:
        if not evidence:
            return

        await conn.executemany(
            """
            INSERT INTO reconciliation_evidence (
                settlement_id,
                evidence_id,
                source,
                entity_type,
                entity_id,
                reason,
                object_key
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (settlement_id, evidence_id)
            DO UPDATE SET
                source = EXCLUDED.source,
                entity_type = EXCLUDED.entity_type,
                entity_id = EXCLUDED.entity_id,
                reason = EXCLUDED.reason,
                object_key = EXCLUDED.object_key
            """,
            [
                (
                    settlement_id,
                    item.evidence_id,
                    item.source,
                    item.entity_type,
                    item.entity_id,
                    item.reason,
                    item.object_key,
                )
                for item in evidence
            ],
        )

    async def _save_finding_evidence(
        self,
        conn: asyncpg.Connection,
        settlement_id: str,
        findings: list[ReconciliationFinding],
    ) -> None:
        rows = [
            (settlement_id, finding.finding_id, item.evidence_id)
            for finding in findings
            for item in finding.evidence
        ]

        if not rows:
            return

        await conn.executemany(
            """
            INSERT INTO reconciliation_finding_evidence (
                settlement_id,
                finding_id,
                evidence_id
            )
            VALUES ($1, $2, $3)
            ON CONFLICT DO NOTHING
            """,
            rows,
        )

    async def save_run(
        self,
        response: ReconcileSettlementResponse,
        import_ids: list[str],
    ) -> None:
        async with self._db.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO reconciliation_runs (
                    settlement_id,
                    status,
                    reason_code,
                    merchant_expected,
                    razorpay_net,
                    bank_observed,
                    merchant_vs_razorpay_difference,
                    razorpay_vs_bank_difference,
                    import_ids,
                    updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, now())
                ON CONFLICT (settlement_id)
                DO UPDATE SET
                    status = EXCLUDED.status,
                    reason_code = EXCLUDED.reason_code,
                    merchant_expected = EXCLUDED.merchant_expected,
                    razorpay_net = EXCLUDED.razorpay_net,
                    bank_observed = EXCLUDED.bank_observed,
                    merchant_vs_razorpay_difference = EXCLUDED.merchant_vs_razorpay_difference,
                    razorpay_vs_bank_difference = EXCLUDED.razorpay_vs_bank_difference,
                    import_ids = EXCLUDED.import_ids,
                    updated_at = now()
                """,
                response.settlement_id,
                response.status,
                response.reason_code,
                response.merchant_expected,
                response.razorpay_net,
                response.bank_observed,
                response.merchant_vs_razorpay_difference,
                response.razorpay_vs_bank_difference,
                import_ids,
            )

    async def get_run(
        self,
        settlement_id: str,
    ) -> ReconciliationRunResponse | None:
        async with self._db.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    settlement_id,
                    status,
                    reason_code,
                    merchant_expected,
                    razorpay_net,
                    bank_observed,
                    merchant_vs_razorpay_difference,
                    razorpay_vs_bank_difference,
                    import_ids,
                    created_at,
                    updated_at
                FROM reconciliation_runs
                WHERE settlement_id = $1
                """,
                settlement_id,
            )

        if row is None:
            return None

        return self._map_run(row)

    async def list_runs(self) -> list[ReconciliationRunResponse]:
        async with self._db.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    settlement_id,
                    status,
                    reason_code,
                    merchant_expected,
                    razorpay_net,
                    bank_observed,
                    merchant_vs_razorpay_difference,
                    razorpay_vs_bank_difference,
                    import_ids,
                    created_at,
                    updated_at
                FROM reconciliation_runs
                ORDER BY updated_at DESC
                """,
            )

        return [self._map_run(row) for row in rows]

    async def list_findings(
        self,
        settlement_id: str,
    ) -> list[ReconciliationFinding]:
        async with self._db.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    f.finding_id,
                    f.code,
                    f.severity,
                    f.source,
                    f.entity_type,
                    f.entity_id,
                    f.message,
                    e.evidence_id,
                    e.source AS evidence_source,
                    e.entity_type AS evidence_entity_type,
                    e.entity_id AS evidence_entity_id,
                    e.reason,
                    e.object_key
                FROM reconciliation_findings f
                LEFT JOIN reconciliation_finding_evidence fe
                    ON fe.settlement_id = f.settlement_id
                   AND fe.finding_id = f.finding_id
                LEFT JOIN reconciliation_evidence e
                    ON e.settlement_id = fe.settlement_id
                   AND e.evidence_id = fe.evidence_id
                WHERE f.settlement_id = $1
                ORDER BY f.finding_id, e.evidence_id
                """,
                settlement_id,
            )

        return self._group_findings(rows)

    async def get_finding(
        self,
        settlement_id: str,
        finding_id: str,
    ) -> ReconciliationFinding | None:
        findings = await self.list_findings(settlement_id)

        return next(
            (finding for finding in findings if finding.finding_id == finding_id),
            None,
        )

    async def list_evidence(
        self,
        settlement_id: str,
    ) -> list[EvidenceRef]:
        async with self._db.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    evidence_id,
                    source,
                    entity_type,
                    entity_id,
                    reason,
                    object_key
                FROM reconciliation_evidence
                WHERE settlement_id = $1
                ORDER BY evidence_id
                """,
                settlement_id,
            )

        return [
            EvidenceRef(
                evidence_id=row["evidence_id"],
                source=row["source"],
                entity_type=row["entity_type"],
                entity_id=row["entity_id"],
                reason=row["reason"],
                object_key=row["object_key"],
            )
            for row in rows
        ]

    @staticmethod
    def _map_run(row: asyncpg.Record) -> ReconciliationRunResponse:
        return ReconciliationRunResponse(
            settlement_id=row["settlement_id"],
            status=row["status"],
            reason_code=row["reason_code"],
            merchant_expected=row["merchant_expected"],
            razorpay_net=row["razorpay_net"],
            bank_observed=row["bank_observed"],
            merchant_vs_razorpay_difference=row["merchant_vs_razorpay_difference"],
            razorpay_vs_bank_difference=row["razorpay_vs_bank_difference"],
            import_ids=list(row["import_ids"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _group_findings(
        rows: list[asyncpg.Record],
    ) -> list[ReconciliationFinding]:
        grouped: dict[str, list[asyncpg.Record]] = {}
        order: list[str] = []

        for row in rows:
            finding_id = row["finding_id"]

            if finding_id not in grouped:
                grouped[finding_id] = []
                order.append(finding_id)

            grouped[finding_id].append(row)

        findings: list[ReconciliationFinding] = []

        for finding_id in order:
            finding_rows = grouped[finding_id]
            row = finding_rows[0]

            evidence = [
                EvidenceRef(
                    evidence_id=evidence_row["evidence_id"],
                    source=evidence_row["evidence_source"],
                    entity_type=evidence_row["evidence_entity_type"],
                    entity_id=evidence_row["evidence_entity_id"],
                    reason=evidence_row["reason"],
                    object_key=evidence_row["object_key"],
                )
                for evidence_row in finding_rows
                if evidence_row["evidence_id"] is not None
            ]

            findings.append(
                ReconciliationFinding(
                    finding_id=row["finding_id"],
                    code=row["code"],
                    severity=row["severity"],
                    affected_entity=EntityReference(
                        source=row["source"],
                        entity_type=row["entity_type"],
                        entity_id=row["entity_id"],
                    ),
                    message=row["message"],
                    evidence=evidence,
                )
            )

        return findings
