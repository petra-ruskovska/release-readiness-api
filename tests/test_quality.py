"""Unit tests for quality.py checks against known-bad DataFrames."""
import pandas as pd

from app.quality import run_quality_checks


def test_detects_high_null_rate():
    df = pd.DataFrame({
        "id": range(20),
        "email": [None] * 15 + ["a@b.com"] * 5,  # 75% null
    })
    issues = run_quality_checks(df)
    null_issues = [i for i in issues if i["issue_type"] == "null_rate" and i["column_name"] == "email"]
    assert len(null_issues) == 1
    assert null_issues[0]["severity"] == "critical"


def test_no_issue_for_clean_column():
    df = pd.DataFrame({"id": range(20), "value": range(20)})
    issues = run_quality_checks(df)
    assert issues == []


def test_detects_duplicate_rows():
    df = pd.DataFrame({"id": [1, 1, 2, 3], "value": ["a", "a", "b", "c"]})
    issues = run_quality_checks(df)
    dup_issues = [i for i in issues if i["issue_type"] == "duplicate_rows"]
    assert len(dup_issues) == 1


def test_detects_numeric_outliers():
    # 20 normal values around 10, one wild outlier
    values = [10] * 19 + [10000]
    df = pd.DataFrame({"amount": values})
    issues = run_quality_checks(df)
    outlier_issues = [i for i in issues if i["issue_type"] == "outlier"]
    assert len(outlier_issues) == 1


def test_empty_dataframe_does_not_crash():
    df = pd.DataFrame({"col": []})
    issues = run_quality_checks(df)
    assert isinstance(issues, list)
