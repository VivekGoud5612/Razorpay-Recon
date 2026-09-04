from recon.application.investigation.dto.evidence import EvidencePackage
from recon.application.investigation.dto.response import Hypothesis, InvestigationResponse, RootCause
from recon.application.investigation.services.investigation_policy import InvestigationPolicy
from recon.domain.reconciliation.evidence import EvidenceRef

VALID_EVIDENCE_ID = "ev:merchant:merchant_order:MORD-1:ORDER_AMOUNT_MISMATCH"


def _package() -> EvidencePackage:
    return EvidencePackage(
        findings=[],
        evidence=[
            EvidenceRef(
                source="merchant",
                entity_type="merchant_order",
                entity_id="MORD-1",
                evidence_id=VALID_EVIDENCE_ID,
                reason="ORDER_AMOUNT_MISMATCH",
                object_key=None,
            ),
        ],
        records=[],
        nodes=[],
        edges=[],
    )


def _response(**overrides) -> InvestigationResponse:
    defaults = dict(
        factual_observations=["Amount mismatch observed."],
        hypotheses=[
            Hypothesis(
                hypothesis_id="H1",
                statement="Merchant order amount is incorrect.",
                supporting_evidence_ids=[VALID_EVIDENCE_ID],
                confidence=0.8,
            ),
        ],
        root_cause=RootCause(hypothesis_id="H1", confidence=0.8),
        evidence=[],
        missing_evidence=[],
        should_abstain=False,
        abstain_reason=None,
    )
    defaults.update(overrides)
    return InvestigationResponse(**defaults)


def test_valid_response_passes_through_unchanged():
    response = _response()

    result = InvestigationPolicy().validate(response, _package())

    assert result.should_abstain is False
    assert result.root_cause is not None
    assert result.root_cause.hypothesis_id == "H1"
    assert result.hypotheses == response.hypotheses


def test_hypothesis_citing_unsupplied_evidence_forces_abstention():
    response = _response(
        hypotheses=[
            Hypothesis(
                hypothesis_id="H1",
                statement="Cites evidence that was never supplied.",
                supporting_evidence_ids=["ev:not:in:package"],
                confidence=0.9,
            ),
        ],
    )

    result = InvestigationPolicy().validate(response, _package())

    assert result.should_abstain is True
    assert result.hypotheses == []
    assert result.root_cause is None
    assert "Invalid evidence references" in result.missing_evidence[-1]


def test_no_hypotheses_forces_abstention():
    response = _response(hypotheses=[], root_cause=None)

    result = InvestigationPolicy().validate(response, _package())

    assert result.should_abstain is True
    assert result.abstain_reason == "No supported hypothesis was produced."


def test_all_hypotheses_below_min_confidence_forces_abstention():
    response = _response(
        hypotheses=[
            Hypothesis(
                hypothesis_id="H1",
                statement="Weak evidence.",
                supporting_evidence_ids=[VALID_EVIDENCE_ID],
                confidence=0.59,
            ),
        ],
        root_cause=None,
    )

    result = InvestigationPolicy().validate(response, _package())

    assert result.should_abstain is True
    assert result.root_cause is None
    assert "minimum confidence" in result.abstain_reason


def test_root_cause_referencing_unknown_hypothesis_forces_abstention():
    response = _response(root_cause=RootCause(hypothesis_id="H_DOES_NOT_EXIST", confidence=0.9))

    result = InvestigationPolicy().validate(response, _package())

    assert result.should_abstain is True
    assert result.root_cause is None
    assert "unknown hypothesis" in result.abstain_reason


def test_root_cause_below_min_confidence_forces_abstention():
    # The policy gates on the referenced *hypothesis's* confidence, not
    # RootCause.confidence (a separate value the model also reports). A
    # second, high-confidence hypothesis keeps this from tripping the
    # earlier "all hypotheses below threshold" gate, isolating the
    # root-cause-specific confidence check.
    response = _response(
        hypotheses=[
            Hypothesis(
                hypothesis_id="H1",
                statement="Below the minimum confidence threshold.",
                supporting_evidence_ids=[VALID_EVIDENCE_ID],
                confidence=0.5,
            ),
            Hypothesis(
                hypothesis_id="H2",
                statement="Comfortably above the minimum confidence threshold.",
                supporting_evidence_ids=[VALID_EVIDENCE_ID],
                confidence=0.9,
            ),
        ],
        root_cause=RootCause(hypothesis_id="H1", confidence=0.5),
    )

    result = InvestigationPolicy().validate(response, _package())

    assert result.should_abstain is True
    assert result.root_cause is None
    assert "below the minimum" in result.abstain_reason


def test_root_cause_hypothesis_without_supporting_evidence_forces_abstention():
    response = _response(
        hypotheses=[
            Hypothesis(
                hypothesis_id="H1",
                statement="No evidence cited at all.",
                supporting_evidence_ids=[],
                confidence=0.9,
            ),
        ],
        root_cause=RootCause(hypothesis_id="H1", confidence=0.9),
    )

    result = InvestigationPolicy().validate(response, _package())

    assert result.should_abstain is True
    assert result.root_cause is None
    assert "no supporting evidence" in result.abstain_reason


def test_root_cause_with_missing_evidence_forces_abstention():
    response = _response(missing_evidence=["Could not retrieve the bank statement document."])

    result = InvestigationPolicy().validate(response, _package())

    assert result.should_abstain is True
    assert result.root_cause is None
    assert "required" in result.abstain_reason


def test_missing_root_cause_forces_abstention_even_with_valid_hypotheses():
    # Regression: a response can clear every hypothesis-level gate (valid
    # evidence citations, confidence above threshold) yet still leave
    # root_cause null while reporting should_abstain=False. Observed live
    # against a real HuggingFace-hosted model response -- the policy must
    # not pass that through as a grounded conclusion.
    response = _response(root_cause=None, should_abstain=False)

    result = InvestigationPolicy().validate(response, _package())

    assert result.should_abstain is True
    assert result.root_cause is None
    assert "No root cause was established" in result.abstain_reason


def test_confidence_outside_valid_range_forces_abstention():
    # Regression: observed live against a real model response returning
    # confidence=100.0 (a 0-100 scale) instead of the documented 0-1
    # fraction. Must not be silently rescaled/trusted.
    response = _response(
        hypotheses=[
            Hypothesis(
                hypothesis_id="H1",
                statement="Confidence reported on the wrong scale.",
                supporting_evidence_ids=[VALID_EVIDENCE_ID],
                confidence=100.0,
            ),
        ],
        root_cause=RootCause(hypothesis_id="H1", confidence=100.0),
    )

    result = InvestigationPolicy().validate(response, _package())

    assert result.should_abstain is True
    assert result.root_cause is None
    assert "valid 0-1 range" in result.abstain_reason
