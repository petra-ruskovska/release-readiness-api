"""
Scoring logic: turns raw defect + data-quality data into 0-100 scores and
a plain-English summary.

Kept deliberately rule-based and transparent — every point deducted has a
named reason, which is what makes this useful to a real release manager.
"""
from app.models import Defect, DataQualityIssue

OPEN_CRITICAL_PENALTY = 15
OPEN_HIGH_PENALTY = 7
REOPEN_RATE_WEIGHT = 50

DATA_ISSUE_PENALTY = {
    "critical": 15,
    "warning": 5,
    "info": 0,
}


def compute_qa_score(defects: list[Defect]) -> tuple[float, list[str]]:
    """Returns (score, list of human-readable reasons for deductions)."""
    if not defects:
        return 100.0, ["No defect data submitted."]

    reasons = []
    score = 100.0

    open_critical = sum(1 for d in defects if d.status == "open" and d.severity == "critical")
    open_high = sum(1 for d in defects if d.status == "open" and d.severity == "high")
    reopened = sum(d.reopened_count for d in defects if d.reopened_count > 0)
    reopen_rate = reopened / len(defects)

    if open_critical:
        score -= open_critical * OPEN_CRITICAL_PENALTY
        reasons.append(f"{open_critical} open critical defect(s) (-{open_critical * OPEN_CRITICAL_PENALTY} pts)")

    if open_high:
        score -= open_high * OPEN_HIGH_PENALTY
        reasons.append(f"{open_high} open high-severity defect(s) (-{open_high * OPEN_HIGH_PENALTY} pts)")

    if reopen_rate > 0:
        penalty = round(reopen_rate * REOPEN_RATE_WEIGHT, 1)
        score -= penalty
        reasons.append(f"{reopen_rate:.1%} reopen rate (-{penalty} pts)")

    score = max(0.0, min(100.0, score))
    if not reasons:
        reasons.append("No significant defect issues found.")
    return score, reasons


def compute_data_score(issues: list[DataQualityIssue]) -> tuple[float, list[str]]:
    if not issues:
        return 100.0, ["No data quality issues found."]

    score = 100.0
    reasons = []
    for issue in issues:
        penalty = DATA_ISSUE_PENALTY.get(issue.severity, 0)
        if penalty:
            score -= penalty
            reasons.append(f"{issue.column_name}: {issue.detail} (-{penalty} pts)")

    score = max(0.0, min(100.0, score))
    return score, reasons


def combine_scores(qa_score: float, data_score: float, qa_weight: float = 0.5) -> float:
    data_weight = 1 - qa_weight
    return round(qa_score * qa_weight + data_score * data_weight, 1)


def build_summary(qa_score: float, data_score: float, combined: float,
                   qa_reasons: list[str], data_reasons: list[str]) -> str:
    verdict = "READY" if combined >= 80 else "AT RISK" if combined >= 60 else "NOT RECOMMENDED"
    top_reasons = (qa_reasons[:2] + data_reasons[:2])
    reasons_text = "; ".join(top_reasons) if top_reasons else "no significant issues"
    return (
        f"{verdict} — combined score {combined}/100 "
        f"(QA {qa_score}/100, Data {data_score}/100). "
        f"Key factors: {reasons_text}."
    )
