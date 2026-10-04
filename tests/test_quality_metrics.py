import pandas as pd

from app.agents.data_quality.quality_aggregator import QualityAggregator
from app.agents.data_quality.validator import DeterministicValidator


def report_for(frame):
    issues = DeterministicValidator().validate_sov(frame, current_year=2026)
    return QualityAggregator().aggregate(issues, dataframe=frame)


def test_completeness_rate_per_field():
    frame = pd.DataFrame({"City": ["A", None, "B", None], "Reference": ["1", "2", "3", "4"]})

    quality = report_for(frame).field_quality

    assert quality["City"].completeness_rate == 0.5
    assert quality["Reference"].completeness_rate == 1.0
    assert quality["Building Value"].present is False
    assert quality["Building Value"].completeness_rate == 0.0


def test_validity_rate_excludes_missing_cells():
    frame = pd.DataFrame({"Building Value": [100.0, -5.0, None, 200.0]})

    quality = report_for(frame).field_quality["Building Value"]

    assert quality.non_null_count == 3
    assert quality.validity_rate == round(2 / 3, 4)


def test_row_flags_list_fields_with_issues():
    frame = pd.DataFrame({"Building Value": [100.0, -5.0], "Storeys": [1, 0]})

    flags = report_for(frame).row_flags

    assert flags[1] == ["Building Value", "Storeys"]
    assert 0 not in flags


def test_intake_score_does_not_collapse_on_large_files():
    rows = 2000
    frame = pd.DataFrame({field: ["x"] * rows for field in ["Reference"]})
    frame["Reference"] = [f"R{i}" for i in range(rows)]
    frame.loc[:9, "Reference"] = None

    report = report_for(frame)

    # The legacy penalty score saturates at 0; the intake score stays
    # meaningful.
    assert report.quality_score == 0.0
    assert 0.0 < report.intake_quality_score < 100.0


def test_clean_full_schema_scores_100():
    frame = pd.DataFrame(
        {
            "Reference": ["R1"],
            "Address": ["1 Main St"],
            "City": ["Boston"],
            "State": ["MA"],
            "Zip": ["02108"],
            "County": ["Suffolk"],
            "Country": ["USA"],
            "Building Value": [1e6],
            "Contents": [1e5],
            "BI": [5e4],
            "Occupancy": ["Office"],
            "Construction": ["Masonry"],
            "Storeys": [3],
            "Number of Buildings": [1],
            "Year Built": [1990],
            "Fire Sprinklers (Y/N)": ["Y"],
            "Other": [0.0],
        }
    )

    report = report_for(frame)

    assert report.total_issues == 0
    assert report.intake_quality_score == 100.0
