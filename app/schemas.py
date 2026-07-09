"""
Non-table schemas: request bodies and response shapes that don't map
1:1 to a database table.
"""
from typing import Optional
from pydantic import BaseModel


class ProjectCreate(BaseModel):
    name: str


class DefectSummary(BaseModel):
    total: int
    open_count: int
    resolved_count: int
    by_severity: dict[str, int]
    reopen_rate: float
    mean_time_to_resolution_days: Optional[float]


class DataQualitySummary(BaseModel):
    run_id: int
    row_count: int
    column_count: int
    issue_count: int
    issues_by_type: dict[str, int]


class ReadinessResponse(BaseModel):
    project_id: int
    qa_score: float
    data_score: float
    combined_score: float
    summary_text: str
