"""
Unit tests for scoring.py — pure functions, fast, no DB or HTTP needed.
This is the kind of test suite that shows QA rigor: edge cases, not just
the happy path.
"""
from datetime import date

from app.models import Defect, DataQualityIssue
from app.scoring import compute_qa_score, compute_data_score, combine_scores


def make_defect(**overrides) -> Defect:
    defaults = dict(
        project_id=1,
        external_id="X-1",
        title="test defect",
        severity="medium",
        status="open",
        created_date=date(2024, 1, 1),
        resolved_date=None,
        reopened_count=0,
    )
    defaults.update(overrides)
    return Defect(**defaults)


def test_qa_score_with_no_defects_is_perfect():
    score, reasons = compute_qa_score([])
    assert score == 100.0
    assert "No defect data" in reasons[0]


def test_qa_score_penalizes_open_critical_defects():
    defects = [make_defect(severity="critical", status="open")]
    score, reasons = compute_qa_score(defects)
    assert score == 85.0  # 100 - 15
    assert any("critical" in r for r in reasons)


def test_qa_score_penalizes_reopen_rate():
    defects = [make_defect(reopened_count=1), make_defect(reopened_count=0)]
    score, _ = compute_qa_score(defects)
    # 1 of 2 defects reopened -> 50% reopen rate -> -25 pts
    assert score == 75.0


def test_qa_score_never_goes_below_zero():
    defects = [make_defect(severity="critical", status="open") for _ in range(20)]
    score, _ = compute_qa_score(defects)
    assert score == 0.0


def test_qa_score_never_exceeds_100():
    defects = [make_defect(severity="low", status="closed")]
    score, _ = compute_qa_score(defects)
    assert score <= 100.0


def make_issue(**overrides) -> DataQualityIssue:
    defaults = dict(
        run_id=1,
        column_name="col",
        issue_type="null_rate",
        severity="warning",
        detail="test issue",
        metric_value=0.1,
    )
    defaults.update(overrides)
    return DataQualityIssue(**defaults)


def test_data_score_with_no_issues_is_perfect():
    score, reasons = compute_data_score([])
    assert score == 100.0


def test_data_score_penalizes_critical_more_than_warning():
    critical_score, _ = compute_data_score([make_issue(severity="critical")])
    warning_score, _ = compute_data_score([make_issue(severity="warning")])
    assert critical_score < warning_score


def test_combine_scores_respects_weighting():
    # qa=100, data=0, weighted fully toward qa -> should equal 100
    assert combine_scores(100, 0, qa_weight=1.0) == 100.0
    # weighted fully toward data -> should equal 0
    assert combine_scores(100, 0, qa_weight=0.0) == 0.0
    # equal weighting -> midpoint
    assert combine_scores(100, 0, qa_weight=0.5) == 50.0
