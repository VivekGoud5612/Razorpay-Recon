from __future__ import annotations

from recon.application.investigation.dto.evidence import EvidencePackage
from recon.application.investigation.dto.response import InvestigationResponse


class InvestigationPolicy:

    MIN_CONFIDENCE = 0.60

    def validate(
        self,
        response: InvestigationResponse,
        evidence: EvidencePackage,
    ) -> InvestigationResponse:

        valid_evidence_ids = {
            item.evidence_id
            for item in evidence.evidence
        }

        invalid_ids: list[str] = []

        for hypothesis in response.hypotheses:
            for evidence_id in hypothesis.supporting_evidence_ids:
                if evidence_id not in valid_evidence_ids:
                    invalid_ids.append(evidence_id)

        if invalid_ids:
            return InvestigationResponse(
                factual_observations=response.factual_observations,
                hypotheses=[],
                root_cause=None,
                evidence=response.evidence,
                missing_evidence=[
                    *response.missing_evidence,
                    f"Invalid evidence references: {invalid_ids}",
                ],
                should_abstain=True,
                abstain_reason=(
                    "AI cited evidence outside the supplied evidence package."
                ),
            )

        if not response.hypotheses:
            return InvestigationResponse(
                factual_observations=response.factual_observations,
                hypotheses=[],
                root_cause=None,
                evidence=response.evidence,
                missing_evidence=response.missing_evidence,
                should_abstain=True,
                abstain_reason="No supported hypothesis was produced.",
            )

        if all(
            hypothesis.confidence < self.MIN_CONFIDENCE
            for hypothesis in response.hypotheses
        ):
            return InvestigationResponse(
                factual_observations=response.factual_observations,
                hypotheses=response.hypotheses,
                root_cause=None,
                evidence=response.evidence,
                missing_evidence=response.missing_evidence,
                should_abstain=True,
                abstain_reason=(
                    "No hypothesis reached the minimum confidence threshold."
                ),
            )

        hypothesis_ids = {
            hypothesis.hypothesis_id
            for hypothesis in response.hypotheses
        }

        if response.root_cause is not None:

            if response.root_cause.hypothesis_id not in hypothesis_ids:
                return InvestigationResponse(
                    factual_observations=response.factual_observations,
                    hypotheses=response.hypotheses,
                    root_cause=None,
                    evidence=response.evidence,
                    missing_evidence=response.missing_evidence,
                    should_abstain=True,
                    abstain_reason=(
                        "Root cause references an unknown hypothesis."
                    ),
                )

            root_hypothesis = next(
                hypothesis
                for hypothesis in response.hypotheses
                if hypothesis.hypothesis_id
                == response.root_cause.hypothesis_id
            )

            if root_hypothesis.confidence < self.MIN_CONFIDENCE:
                return InvestigationResponse(
                    factual_observations=response.factual_observations,
                    hypotheses=response.hypotheses,
                    root_cause=None,
                    evidence=response.evidence,
                    missing_evidence=response.missing_evidence,
                    should_abstain=True,
                    abstain_reason=(
                        "Root cause hypothesis is below the minimum "
                        "confidence threshold."
                    ),
                )

            if not root_hypothesis.supporting_evidence_ids:
                return InvestigationResponse(
                    factual_observations=response.factual_observations,
                    hypotheses=response.hypotheses,
                    root_cause=None,
                    evidence=response.evidence,
                    missing_evidence=response.missing_evidence,
                    should_abstain=True,
                    abstain_reason=(
                        "Root cause has no supporting evidence."
                    ),
                )

            if response.missing_evidence:
                return InvestigationResponse(
                    factual_observations=response.factual_observations,
                    hypotheses=response.hypotheses,
                    root_cause=None,
                    evidence=response.evidence,
                    missing_evidence=response.missing_evidence,
                    should_abstain=True,
                    abstain_reason=(
                        "Root cause cannot be accepted while required "
                        "evidence is missing."
                    ),
                )

        return response