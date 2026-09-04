INVESTIGATION_RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "factual_observations": {
            "type": "array",
            "items": {"type": "string"},
        },
        "hypotheses": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "hypothesis_id": {"type": "string"},
                    "statement": {"type": "string"},
                    "supporting_evidence_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "confidence": {
                        "type": "number",
                    },
                },
                "required": [
                    "hypothesis_id",
                    "statement",
                    "supporting_evidence_ids",
                    "confidence",
                ],
            },
        },
        "root_cause": {
            "anyOf": [
                {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "hypothesis_id": {"type": "string"},
                        "confidence": {
                            "type": "number",
                        },
                    },
                    "required": [
                        "hypothesis_id",
                        "confidence",
                    ],
                },
                {"type": "null"},
            ],
        },
        "missing_evidence": {
            "type": "array",
            "items": {"type": "string"},
        },
        "should_abstain": {
            "type": "boolean",
        },
        "abstain_reason": {
            "anyOf": [
                {"type": "string"},
                {"type": "null"},
            ],
        },
    },
    "required": [
        "factual_observations",
        "hypotheses",
        "root_cause",
        "missing_evidence",
        "should_abstain",
        "abstain_reason",
    ],
}