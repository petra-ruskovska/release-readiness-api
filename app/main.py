"""
Release Readiness API
----------------------
Combines defect trends (QA signal) and dataset quality checks (data signal)
into a single release-readiness score.

Run locally:
    uvicorn app.main:app --reload

Docs:
    http://127.0.0.1:8000/docs
"""
from datetime import date
from io import StringIO
from collections import Counter

import pandas as pd
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.database import init_db, get_session
from app.models import Project, Defect, DataQualityRun, DataQualityIssue, ReadinessSnapshot
from app.schemas import ProjectCreate, DefectSummary, DataQualitySummary, ReadinessResponse
from app.quality import run_quality_checks
from app.scoring import compute_qa_score, compute_data_score, combine_scores, build_summary

app = FastAPI(
    title="Release Readiness API",
    description="Aggregates defect trends and data quality checks into a release-readiness score.",
    version="0.1.0",
)

@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")

@app.on_event("startup")
def on_startup():
    init_db()


# ---------------------------------------------------------------- projects

@app.post("/projects", response_model=Project)
def create_project(payload: ProjectCreate, session: Session = Depends(get_session)):
    project = Project(name=payload.name)
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


@app.get("/projects", response_model=list[Project])
def list_projects(session: Session = Depends(get_session)):
    return session.exec(select(Project)).all()


def _get_project_or_404(project_id: int, session: Session) -> Project:
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


# ----------------------------------------------------------------- defects

@app.post("/projects/{project_id}/defects/upload")
async def upload_defects(project_id: int, file: UploadFile = File(...),
                          session: Session = Depends(get_session)):
    """
    Expects a CSV with columns:
    external_id,title,severity,status,module,created_date,resolved_date,reopened_count

    severity: critical|high|medium|low
    status: open|in_progress|resolved|closed
    dates: YYYY-MM-DD
    """
    _get_project_or_404(project_id, session)
    raw = (await file.read()).decode("utf-8")
    df = pd.read_csv(StringIO(raw))

    required = {"external_id", "title", "severity", "status", "created_date"}
    missing = required - set(df.columns)
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing required columns: {missing}")

    inserted = 0
    for _, row in df.iterrows():
        defect = Defect(
            project_id=project_id,
            external_id=str(row["external_id"]),
            title=str(row["title"]),
            severity=str(row["severity"]).lower(),
            status=str(row["status"]).lower(),
            module=row.get("module") if "module" in df.columns else None,
            created_date=pd.to_datetime(row["created_date"]).date(),
            resolved_date=(
                pd.to_datetime(row["resolved_date"]).date()
                if "resolved_date" in df.columns and pd.notna(row["resolved_date"])
                else None
            ),
            reopened_count=int(row.get("reopened_count", 0) or 0),
        )
        session.add(defect)
        inserted += 1
    session.commit()
    return {"inserted": inserted}


@app.get("/projects/{project_id}/defects/summary", response_model=DefectSummary)
def defects_summary(project_id: int, session: Session = Depends(get_session)):
    _get_project_or_404(project_id, session)
    defects = session.exec(select(Defect).where(Defect.project_id == project_id)).all()
    if not defects:
        raise HTTPException(status_code=404, detail="No defects found for this project")

    open_count = sum(1 for d in defects if d.status in ("open", "in_progress"))
    resolved_count = sum(1 for d in defects if d.status in ("resolved", "closed"))
    by_severity = dict(Counter(d.severity for d in defects))
    reopened = sum(1 for d in defects if d.reopened_count > 0)
    reopen_rate = reopened / len(defects)

    resolution_days = [
        (d.resolved_date - d.created_date).days
        for d in defects if d.resolved_date
    ]
    mttr = sum(resolution_days) / len(resolution_days) if resolution_days else None

    return DefectSummary(
        total=len(defects),
        open_count=open_count,
        resolved_count=resolved_count,
        by_severity=by_severity,
        reopen_rate=round(reopen_rate, 3),
        mean_time_to_resolution_days=round(mttr, 1) if mttr is not None else None,
    )


# ------------------------------------------------------------- data quality

@app.post("/projects/{project_id}/dataset/upload", response_model=DataQualitySummary)
async def upload_dataset(project_id: int, file: UploadFile = File(...),
                          session: Session = Depends(get_session)):
    """Accepts any CSV, runs quality checks, and stores the results."""
    _get_project_or_404(project_id, session)
    raw = (await file.read()).decode("utf-8")
    df = pd.read_csv(StringIO(raw))

    run = DataQualityRun(
        project_id=project_id,
        source_filename=file.filename or "unknown.csv",
        row_count=len(df),
        column_count=len(df.columns),
    )
    session.add(run)
    session.commit()
    session.refresh(run)

    issues = run_quality_checks(df)
    for issue in issues:
        session.add(DataQualityIssue(run_id=run.id, **issue))
    session.commit()

    return DataQualitySummary(
        run_id=run.id,
        row_count=run.row_count,
        column_count=run.column_count,
        issue_count=len(issues),
        issues_by_type=dict(Counter(i["issue_type"] for i in issues)),
    )


@app.get("/projects/{project_id}/dataset/quality", response_model=DataQualitySummary)
def dataset_quality(project_id: int, session: Session = Depends(get_session)):
    _get_project_or_404(project_id, session)
    latest_run = session.exec(
        select(DataQualityRun)
        .where(DataQualityRun.project_id == project_id)
        .order_by(DataQualityRun.uploaded_at.desc())
    ).first()
    if not latest_run:
        raise HTTPException(status_code=404, detail="No dataset uploaded for this project yet")

    issues = session.exec(
        select(DataQualityIssue).where(DataQualityIssue.run_id == latest_run.id)
    ).all()

    return DataQualitySummary(
        run_id=latest_run.id,
        row_count=latest_run.row_count,
        column_count=latest_run.column_count,
        issue_count=len(issues),
        issues_by_type=dict(Counter(i.issue_type for i in issues)),
    )


# --------------------------------------------------------------- readiness

@app.get("/projects/{project_id}/readiness", response_model=ReadinessResponse)
def readiness(project_id: int, qa_weight: float = 0.5, session: Session = Depends(get_session)):
    """
    Combines the latest defect data and latest data-quality run into a
    single readiness score.

    qa_weight: 0.0-1.0, how much the QA score counts vs the data score
               (default 0.5 = equal weighting).
    """
    _get_project_or_404(project_id, session)
    if not 0 <= qa_weight <= 1:
        raise HTTPException(status_code=400, detail="qa_weight must be between 0 and 1")

    defects = session.exec(select(Defect).where(Defect.project_id == project_id)).all()
    qa_score, qa_reasons = compute_qa_score(defects)

    latest_run = session.exec(
        select(DataQualityRun)
        .where(DataQualityRun.project_id == project_id)
        .order_by(DataQualityRun.uploaded_at.desc())
    ).first()
    data_issues = []
    if latest_run:
        data_issues = session.exec(
            select(DataQualityIssue).where(DataQualityIssue.run_id == latest_run.id)
        ).all()
    data_score, data_reasons = compute_data_score(data_issues)

    combined = combine_scores(qa_score, data_score, qa_weight)
    summary = build_summary(qa_score, data_score, combined, qa_reasons, data_reasons)

    snapshot = ReadinessSnapshot(
        project_id=project_id,
        qa_score=qa_score,
        data_score=data_score,
        combined_score=combined,
        summary_text=summary,
    )
    session.add(snapshot)
    session.commit()

    return ReadinessResponse(
        project_id=project_id,
        qa_score=qa_score,
        data_score=data_score,
        combined_score=combined,
        summary_text=summary,
    )


@app.get("/projects/{project_id}/readiness/history", response_model=list[ReadinessSnapshot])
def readiness_history(project_id: int, session: Session = Depends(get_session)):
    _get_project_or_404(project_id, session)
    return session.exec(
        select(ReadinessSnapshot)
        .where(ReadinessSnapshot.project_id == project_id)
        .order_by(ReadinessSnapshot.generated_at)
    ).all()
