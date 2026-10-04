import pandas as pd

from app.agents.data_quality.config import get_sov_validation_config
from app.agents.data_quality.quality_aggregator import (
    QualityAggregator,
    QualityReport,
)
from app.agents.data_quality.validator import DeterministicValidator


def test_real_validator_output_can_be_aggregated():
    dataframe = pd.DataFrame(
        {
            "Reference": [
                "REF001",
                "REF002",
                "REF003",
            ],
            "Address": [
                "123 Main Street",
                "456 Oak Street",
                "789 Pine Street",
            ],
            "City": [
                "New York",
                "Chicago",
                "Boston",
            ],
            "State": [
                "NY",
                "IL",
                "MA",
            ],
            "Zip": [
                "10001",
                "60601",
                "02108",
            ],
            "County": [
                "New York",
                "Cook",
                "Suffolk",
            ],
            "Country": [
                "USA",
                "USA",
                "USA",
            ],
            "Building Value": [
                1000000.0,
                -500000.0,
                750000.0,
            ],
            "Contents": [
                100000.0,
                200000.0,
                150000.0,
            ],
            "BI": [
                50000.0,
                75000.0,
                60000.0,
            ],
            "Occupancy": [
                "Office",
                "Retail",
                "Warehouse",
            ],
            "Construction": [
                "Masonry",
                "Steel",
                "Concrete",
            ],
            "Storeys": [
                5,
                3,
                2,
            ],
            "Number of Buildings": [
                1,
                1,
                2,
            ],
            "Year Built": [
                2000,
                2010,
                2020,
            ],
            "Fire Sprinklers (Y/N)": [
                "Y",
                "MAYBE",
                "N",
            ],
            "Other": [
                10000.0,
                20000.0,
                15000.0,
            ],
        }
    )

    config = get_sov_validation_config()

    validator = DeterministicValidator()

    issues = validator.validate(
        dataframe=dataframe,
        required_fields=config["required_fields"],
        field_types=config["field_types"],
        non_negative_fields=config["non_negative_fields"],
        allowed_categories=config["allowed_categories"],
        field_ranges=config["field_ranges"],
        current_year=2026,
        unique_fields=config["unique_fields"],
    )

    aggregator = QualityAggregator()

    report = aggregator.aggregate(issues)

    assert isinstance(report, QualityReport)

    assert report.total_issues > 0
    assert report.high_issue_count > 0
    assert report.medium_issue_count >= 0

    assert report.human_review_required is True
    assert report.quality_score < 100

    assert report.issues == issues


def test_clean_dataframe_produces_clean_quality_report():
    dataframe = pd.DataFrame(
        {
            "Reference": [
                "REF001",
            ],
            "Address": [
                "123 Main Street",
            ],
            "City": [
                "New York",
            ],
            "State": [
                "NY",
            ],
            "Zip": [
                "10001",
            ],
            "County": [
                "New York",
            ],
            "Country": [
                "USA",
            ],
            "Building Value": [
                1000000.0,
            ],
            "Contents": [
                100000.0,
            ],
            "BI": [
                50000.0,
            ],
            "Occupancy": [
                "Office",
            ],
            "Construction": [
                "Masonry",
            ],
            "Storeys": [
                5,
            ],
            "Number of Buildings": [
                1,
            ],
            "Year Built": [
                2000,
            ],
            "Fire Sprinklers (Y/N)": [
                "Y",
            ],
            "Other": [
                10000.0,
            ],
        }
    )

    config = get_sov_validation_config()

    validator = DeterministicValidator()

    issues = validator.validate(
        dataframe=dataframe,
        required_fields=config["required_fields"],
        field_types=config["field_types"],
        non_negative_fields=config["non_negative_fields"],
        allowed_categories=config["allowed_categories"],
        field_ranges=config["field_ranges"],
        current_year=2026,
        unique_fields=config["unique_fields"],
    )

    aggregator = QualityAggregator()

    report = aggregator.aggregate(issues)

    assert isinstance(report, QualityReport)

    assert report.total_issues == 0
    assert report.critical_issue_count == 0
    assert report.high_issue_count == 0
    assert report.medium_issue_count == 0
    assert report.low_issue_count == 0

    assert report.human_review_required is False
    assert report.quality_score == 100.0
    assert report.issues == []