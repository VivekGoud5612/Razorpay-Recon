from __future__ import annotations

import json
from typing import Any

from recon.application.investigation.dto.evidence import EvidencePackage
from recon.application.investigation.dto.response import (
    Hypothesis,
    InvestigationEvidence,
    InvestigationResponse,
    RootCause,
)
from recon.application.investigation.ports.llm import LLMClient
from recon.infrastructure.ai.schemas import INVESTIGATION_RESPONSE_SCHEMA
from recon.infrastructure.investigation.mcp.document_tools import DocumentTools


SYSTEM_PROMPT = """
You are a financial reconciliation investigator.

You investigate reconciliation exceptions using only the supplied findings,
evidence, graph context, and documents retrieved through the available tools.

CORE RULES

1. Treat deterministic reconciliation findings as established facts.
2. Never invent entities, amounts, dates, relationships, or documents.
3. Clearly distinguish factual observations from hypotheses.
4. Every hypothesis must cite evidence IDs from the supplied evidence package.
5. Do not cite evidence that was not supplied or retrieved.
6. Seeing an object_key does NOT mean that the document has been read.
7. Never claim to have read a source document unless its contents were supplied
   directly or returned by a document tool.
8. Never override deterministic reconciliation facts.
9. If the available evidence is insufficient to support a reliable conclusion,
   abstain.
10. Confidence must reflect evidence strength, not certainty.
11. A discrepancy does not by itself establish which source is incorrect.
12. Never assign fault to a source merely because its value differs from another source.
13. Treat a finding as an observed violation of an invariant, not as proof of the root cause.
14. A root cause may identify a source as incorrect only when additional evidence
    establishes that source as the cause.
15. If the evidence proves only that two sources disagree, report the disagreement
    and abstain from assigning a root cause.

DOCUMENT TOOLS

You have access to these document tools:

get_document(object_key)
    Retrieves the contents of a specific merchant source document referenced
    by an EvidenceRef.object_key.

search_document(object_key, query)
    Searches a referenced merchant source document and returns relevant
    matching records or lines.

TOOL RULES

- Only call tools with object_keys present in the supplied EvidenceRefs.
- Never invent an object_key.
- Use get_document when the relevant document is small or complete contents
  are necessary.
- Use search_document when only specific records or terms are necessary.
- Prefer the smallest amount of document content needed for the investigation.
- A tool response is the only basis on which you may claim to have read
  a document.
- If a required document or record cannot be retrieved, report it as
  missing evidence and consider abstaining.

EVIDENCE PROVENANCE

For every hypothesis, cite the exact evidence IDs supporting it.

Evidence can come from:
- deterministic reconciliation evidence,
- graph nodes,
- graph edges,
- retrieved merchant source documents.

Do not cite a node, edge, or document that was not actually supplied
or retrieved.

INVESTIGATION PROCESS

1. Identify the deterministic finding or findings.
2. Separate established facts from unresolved causality.
3. Examine the supplied domain records and their values.
4. Examine the graph relationships.
5. Determine whether the evidence establishes which source is authoritative
   or which source contains the error.
6. If additional source-document information is necessary, retrieve it.
7. Generate hypotheses only when they are supported by evidence.
8. Do not convert a mismatch into a causal claim without supporting evidence.
9. If multiple sources disagree and no evidence establishes the responsible
   source, abstain from assigning a root cause.

OUTPUT REQUIREMENTS

Return only the requested structured InvestigationResponse.

The response must contain:
- factual_observations
- hypotheses
- root_cause
- missing_evidence
- should_abstain
- abstain_reason

Never use prose outside the structured response.
"""


class LLMInvestigator:

    def __init__(
        self,
        client: LLMClient,
        document_tools: DocumentTools,
    ) -> None:
        self._client = client
        self._document_tools = document_tools

    async def investigate(
        self,
        evidence: EvidencePackage,
    ) -> InvestigationResponse:
        result = await self._client.complete(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=self._build_prompt(evidence),
            response_schema=INVESTIGATION_RESPONSE_SCHEMA,
            tools=self._document_tools.definitions(),
            tool_handlers=self._scoped_tool_handlers(evidence),
        )

        return self._to_response(result, evidence)

    def _scoped_tool_handlers(
        self,
        evidence: EvidencePackage,
    ) -> dict[str, Any]:
        """Binds the document tools to exactly the object_keys present in
        this EvidencePackage. The model is never given raw storage access:
        every call is checked against this allowlist before it reaches
        DocumentTools/ObjectStorage, so it can only retrieve documents that
        are already part of the current investigation's evidence.
        """
        allowed_object_keys = {
            item.object_key
            for item in evidence.evidence
            if item.object_key
        }

        async def get_document(arguments: dict[str, Any]) -> str:
            object_key = arguments.get("object_key")

            if object_key not in allowed_object_keys:
                return json.dumps(
                    {
                        "error": (
                            "object_key not present in the supplied "
                            "evidence package"
                        ),
                    }
                )

            return await self._document_tools.get_document(object_key)

        async def search_document(arguments: dict[str, Any]) -> str:
            object_key = arguments.get("object_key")

            if object_key not in allowed_object_keys:
                return json.dumps(
                    {
                        "error": (
                            "object_key not present in the supplied "
                            "evidence package"
                        ),
                    }
                )

            return await self._document_tools.search_document(
                object_key,
                arguments.get("query", ""),
            )

        return {
            "get_document": get_document,
            "search_document": search_document,
        }

    @staticmethod
    def _build_prompt(
        evidence: EvidencePackage,
    ) -> str:
        return json.dumps(
            {
                "findings": [
                    {
                        "finding_id": finding.finding_id,
                        "code": finding.code,
                        "severity": finding.severity,
                        "affected_entity": {
                            "source": finding.affected_entity.source,
                            "entity_type": finding.affected_entity.entity_type,
                            "entity_id": finding.affected_entity.entity_id,
                        },
                        "message": finding.message,
                    }
                    for finding in evidence.findings
                ],
                "evidence": [
                    {
                        "evidence_id": item.evidence_id,
                        "source": item.source,
                        "entity_type": item.entity_type,
                        "entity_id": item.entity_id,
                        "reason": item.reason,
                        "object_key": item.object_key,
                    }
                    for item in evidence.evidence
                ],
                "records": [
                    {
                        "source": record.source,
                        "entity_type": record.entity_type,
                        "entity_id": record.entity_id,
                        "data": record.data,
                    }
                    for record in evidence.records
                ],
                "nodes": [
                    {
                        "node_id": node.node_id,
                        "source": node.source,
                        "entity_type": node.entity_type,
                        "entity_id": node.entity_id,
                    }
                    for node in evidence.nodes
                ],
                "edges": [
                    {
                        "edge_id": edge.edge_id,
                        "source_node_id": edge.source_node_id,
                        "target_node_id": edge.target_node_id,
                        "edge_type": edge.edge_type,
                        "confidence": edge.confidence,
                    }
                    for edge in evidence.edges
                ],
            },
            indent=2,
            default=str,
        )

    @staticmethod
    def _to_response(
        result: dict,
        evidence: EvidencePackage,
    ) -> InvestigationResponse:
        evidence_by_id = {
            item.evidence_id: item
            for item in evidence.evidence
        }

        investigation_evidence = [
            InvestigationEvidence(
                evidence_id=item.evidence_id,
                source=item.source,
                entity_type=item.entity_type,
                entity_id=item.entity_id,
                reason=item.reason,
                data=(
                    next(
                        (
                            record.data
                            for record in evidence.records
                            if (
                                record.source == item.source
                                and record.entity_type == item.entity_type
                                and record.entity_id == item.entity_id
                            )
                        ),
                        {},
                    )
                ),
                object_key=item.object_key,
            )
            for item in evidence.evidence
        ]

        hypotheses = [
            Hypothesis(
                hypothesis_id=item["hypothesis_id"],
                statement=item["statement"],
                supporting_evidence_ids=item["supporting_evidence_ids"],
                confidence=item["confidence"],
            )
            for item in result["hypotheses"]
        ]

        root_cause = result["root_cause"]

        return InvestigationResponse(
            factual_observations=result["factual_observations"],
            hypotheses=hypotheses,
            root_cause=(
                RootCause(
                    hypothesis_id=root_cause["hypothesis_id"],
                    confidence=root_cause["confidence"],
                )
                if root_cause is not None
                else None
            ),
            evidence=investigation_evidence,
            missing_evidence=result["missing_evidence"],
            should_abstain=result["should_abstain"],
            abstain_reason=result["abstain_reason"],
        )