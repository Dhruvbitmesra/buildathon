from app.agents.schema_mapping.agent import (
    SchemaMappingAgent,
    SchemaMappingInput,
)
from app.agents.schema_mapping.batch_mapper import (
    SourceColumnEvidence,
)
from app.agents.schema_mapping.llm_decision import (
    LLMMappingDecision,
)


class FakeLLMClient:

    def __init__(self):

        self.calls = []

    def decide(self, context):

        self.calls.append(
            context.source_header
        )

        return LLMMappingDecision(
            target_field="Construction",
            confidence=0.81,
            reason=(
                "Sample values indicate "
                "construction material."
            ),
        )


def test_agent_accepts_input():

    agent = SchemaMappingAgent()

    mapping_input = SchemaMappingInput(
        source_headers=[
            "Building Value",
            "Contents",
        ]
    )

    assert mapping_input.source_headers == [
        "Building Value",
        "Contents",
    ]


def test_agent_builds_column_evidence():

    agent = SchemaMappingAgent()

    fake_evidence = SourceColumnEvidence(
        source_header="Building Value",
        candidates=[
            {
                "target_field": "Building Value",
                "score": 0.90,
            }
        ],
    )

    agent._build_column_evidence = (
        lambda source_header, samples:
        fake_evidence
    )

    evidence = agent._build_column_evidence(
        "Building Value",
        [],
    )

    assert evidence.source_header == (
        "Building Value"
    )

    assert len(evidence.candidates) == 1


def test_agent_maps_multiple_columns():

    agent = SchemaMappingAgent()

    def fake_build(
        source_header,
        samples,
    ):

        target = {
            "Building Value": "Building Value",
            "Contents": "Contents",
        }[source_header]

        return SourceColumnEvidence(
            source_header=source_header,
            candidates=[
                {
                    "target_field": target,
                    "score": 0.90,
                }
            ],
        )

    agent._build_column_evidence = fake_build

    result = agent.map(
        SchemaMappingInput(
            source_headers=[
                "Building Value",
                "Contents",
            ]
        )
    )

    assignments = {
        mapping.source_header:
        mapping.target_field
        for mapping in result.mappings
    }

    assert assignments == {
        "Building Value": "Building Value",
        "Contents": "Contents",
    }


def test_agent_handles_processing_failure():

    agent = SchemaMappingAgent()

    def failing_build(
        source_header,
        samples,
    ):
        raise RuntimeError(
            "test failure"
        )

    agent._build_column_evidence = failing_build

    result = agent.map(
        SchemaMappingInput(
            source_headers=[
                "Broken Column",
            ]
        )
    )

    assert "Broken Column" in (
        result.unresolved_columns
    )

    assert len(result.warnings) == 1


def test_agent_preserves_unique_targets():

    agent = SchemaMappingAgent()

    def fake_build(
        source_header,
        samples,
    ):

        return SourceColumnEvidence(
            source_header=source_header,
            candidates=[
                {
                    "target_field": "Building Value",
                    "score": 0.90,
                },
                {
                    "target_field": "Contents",
                    "score": 0.80,
                },
            ],
        )

    agent._build_column_evidence = fake_build

    result = agent.map(
        SchemaMappingInput(
            source_headers=[
                "Column A",
                "Column B",
            ]
        )
    )

    targets = [
        mapping.target_field
        for mapping in result.mappings
        if mapping.target_field is not None
    ]

    assert len(targets) == len(set(targets))