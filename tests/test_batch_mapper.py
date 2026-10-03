from app.agents.schema_mapping.batch_mapper import (
    SourceColumnEvidence,
    assign_one_to_one,
    build_score_matrix,
)


def test_score_matrix_contains_candidate_scores():

    columns = [
        SourceColumnEvidence(
            source_header="Building Cost",
            candidates=[
                {
                    "target_field": "Building Value",
                    "score": 0.90,
                },
                {
                    "target_field": "Contents",
                    "score": 0.40,
                },
            ],
        ),
        SourceColumnEvidence(
            source_header="Contents Value",
            candidates=[
                {
                    "target_field": "Contents",
                    "score": 0.88,
                },
            ],
        ),
    ]

    matrix = build_score_matrix(columns)

    assert matrix.shape[0] == 2
    assert matrix.shape[1] == 17

    building_index = 7
    contents_index = 8

    assert matrix[
        0,
        building_index
    ] == 0.90

    assert matrix[
        1,
        contents_index
    ] == 0.88


def test_one_to_one_assignment():

    columns = [
        SourceColumnEvidence(
            source_header="Column A",
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
        ),
        SourceColumnEvidence(
            source_header="Column B",
            candidates=[
                {
                    "target_field": "Building Value",
                    "score": 0.85,
                },
                {
                    "target_field": "Contents",
                    "score": 0.82,
                },
            ],
        ),
    ]

    result = assign_one_to_one(columns)

    assignments = {
        mapping.source_header:
        mapping.target_field
        for mapping in result.mappings
    }

    assert assignments["Column A"] == "Building Value"
    assert assignments["Column B"] == "Contents"

    assert len(
        result.assigned_targets
    ) == len(
        set(result.assigned_targets)
    )


def test_global_assignment_can_override_local_best():

    columns = [
        SourceColumnEvidence(
            source_header="Column A",
            candidates=[
                {
                    "target_field": "Building Value",
                    "score": 0.95,
                },
                {
                    "target_field": "Contents",
                    "score": 0.80,
                },
            ],
        ),
        SourceColumnEvidence(
            source_header="Column B",
            candidates=[
                {
                    "target_field": "Building Value",
                    "score": 0.94,
                },
                {
                    "target_field": "Contents",
                    "score": 0.10,
                },
            ],
        ),
    ]

    result = assign_one_to_one(columns)

    assignments = {
        mapping.source_header:
        mapping.target_field
        for mapping in result.mappings
    }

    # Column A keeps Building Value because it has
    # the stronger global configuration.
    assert assignments["Column A"] == "Contents"
    assert assignments["Column B"] == "Building Value"


def test_low_score_requires_review():

    columns = [
        SourceColumnEvidence(
            source_header="Unknown Column",
            candidates=[
                {
                    "target_field": "Building Value",
                    "score": 0.20,
                },
            ],
        ),
    ]

    result = assign_one_to_one(columns)

    mapping = result.mappings[0]

    assert mapping.target_field is None
    assert mapping.human_review_required is True
    assert (
        "below"
        in mapping.reason.lower()
    )


def test_empty_input():

    result = assign_one_to_one([])

    assert result.mappings == []
    assert result.unresolved_columns == []
    assert result.assigned_targets == []


def test_unknown_target_is_ignored():

    columns = [
        SourceColumnEvidence(
            source_header="Unknown",
            candidates=[
                {
                    "target_field": "Not A Real Field",
                    "score": 0.99,
                },
            ],
        ),
    ]

    matrix = build_score_matrix(columns)

    assert matrix.sum() == 0.0