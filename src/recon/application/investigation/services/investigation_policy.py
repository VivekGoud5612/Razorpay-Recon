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

        # The schema declares confidence as a bare number (no min/max) --
        # the model has been observed to occasionally return it on a 0-100
        # scale (e.g. 100.0) instead of the documented 0-1 fraction. Silently
        # rescaling would be guessing the model's intent; treating an
        # out-of-contract value as untrustworthy and abstaining is the safe
        # choice ("do not fabricate confidence").
        out_of_range = [
            hypothesis.hypothesis_id
            for hypothesis in response.hypotheses
            if not (0.0 <= hypothesis.confidence <= 1.0)
        ]

        if out_of_range:
            return InvestigationResponse(
                factual_observations=response.factual_observations,
                hypotheses=response.hypotheses,
                root_cause=None,
                evidence=response.evidence,
                missing_evidence=response.missing_evidence,
                should_abstain=True,
                abstain_reason=(
                    f"Hypothesis confidence outside the valid 0-1 range: {out_of_range}."
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

        # A response can clear every hypothesis-level gate above yet still
        # not nominate a root cause at all (the model left `root_cause`
        # null while reporting `should_abstain: false`) -- that is not a
        # grounded conclusion, it is an inconsistent response, so it must
        # abstain too rather than passing through as if it had one.
        if response.root_cause is None:
            return InvestigationResponse(
                factual_observations=response.factual_observations,
                hypotheses=response.hypotheses,
                root_cause=None,
                evidence=response.evidence,
                missing_evidence=response.missing_evidence,
                should_abstain=True,
                abstain_reason=(
                    "No root cause was established from the available hypotheses."
                ),
            )

        hypothesis_ids = {
            hypothesis.hypothesis_id
            for hypothesis in response.hypotheses
        }

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