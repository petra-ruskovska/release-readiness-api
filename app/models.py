"""
Data models. SQLModel gives us a Pydantic model + SQLAlchemy table in one
class, which keeps this small project from drowning in boilerplate.
"""
from datetime import datetime, date
from typing import Optional
from sqlmodel import SQLModel, Field


class Project(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Defect(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    external_id: str  # e.g. Jira key "PROJ-123"
    title: str
    severity: str  # critical | high | medium | low
    status: str  # open | in_progress | resolved | closed
    module: Optional[str] = None
    created_date: date
    resolved_date: Optional[date] = None
    reopened_count: int = 0


class DataQualityRun(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    source_filename: str
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
    row_count: int
    column_count: int


class DataQualityIssue(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="dataqualityrun.id", index=True)
    column_name: str
    issue_type: str  # null_rate | duplicate_rows | outlier | type_mismatch
    severity: str  # info | warning | critical
    detail: str
    metric_value: float = 0.0  # e.g. the null rate itself, for scoring


class ReadinessSnapshot(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    qa_score: float
    data_score: float
    combined_score: float
    summary_text: str
