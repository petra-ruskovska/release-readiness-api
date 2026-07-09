"""
Data quality checks for uploaded CSVs.

Deliberately simple, explainable rules — no ML. Each check returns a list
of issue dicts that get persisted as DataQualityIssue rows.
"""
import pandas as pd

NULL_RATE_WARNING = 0.05   # 5% nulls in a column starts to matter
NULL_RATE_CRITICAL = 0.20  # 20%+ nulls is a real problem
OUTLIER_Z_THRESHOLD = 3.0  # standard deviations from mean


def run_quality_checks(df: pd.DataFrame) -> list[dict]:
    issues: list[dict] = []
    issues.extend(_check_nulls(df))
    issues.extend(_check_duplicates(df))
    issues.extend(_check_outliers(df))
    return issues


def _check_nulls(df: pd.DataFrame) -> list[dict]:
    issues = []
    for col in df.columns:
        rate = df[col].isna().mean()
        if rate >= NULL_RATE_CRITICAL:
            severity = "critical"
        elif rate >= NULL_RATE_WARNING:
            severity = "warning"
        else:
            continue
        issues.append({
            "column_name": col,
            "issue_type": "null_rate",
            "severity": severity,
            "detail": f"{rate:.1%} of values are null",
            "metric_value": rate,
        })
    return issues


def _check_duplicates(df: pd.DataFrame) -> list[dict]:
    dup_count = int(df.duplicated().sum())
    if dup_count == 0:
        return []
    rate = dup_count / len(df) if len(df) else 0
    severity = "critical" if rate > 0.1 else "warning"
    return [{
        "column_name": "*",  # applies to the whole row, not one column
        "issue_type": "duplicate_rows",
        "severity": severity,
        "detail": f"{dup_count} duplicate rows ({rate:.1%} of dataset)",
        "metric_value": rate,
    }]


def _check_outliers(df: pd.DataFrame) -> list[dict]:
    issues = []
    numeric_cols = df.select_dtypes(include="number").columns
    for col in numeric_cols:
        series = df[col].dropna()
        if series.std(ddof=0) == 0 or len(series) < 5:
            continue
        z_scores = (series - series.mean()) / series.std(ddof=0)
        outlier_count = int((z_scores.abs() > OUTLIER_Z_THRESHOLD).sum())
        if outlier_count == 0:
            continue
        issues.append({
            "column_name": col,
            "issue_type": "outlier",
            "severity": "warning",
            "detail": f"{outlier_count} values beyond {OUTLIER_Z_THRESHOLD} std devs",
            "metric_value": outlier_count / len(series),
        })
    return issues
