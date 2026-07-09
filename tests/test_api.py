"""
End-to-end tests against the running FastAPI app, using an isolated
in-memory SQLite DB so tests never touch your real release_readiness.db.
"""
import io
import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import get_session

# StaticPool keeps a single shared connection alive for the in-memory DB,
# otherwise every session would get its own empty :memory: database.
TEST_ENGINE = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


def get_test_session():
    with Session(TEST_ENGINE) as session:
        yield session


@pytest.fixture(autouse=True)
def setup_db():
    SQLModel.metadata.create_all(TEST_ENGINE)
    yield
    SQLModel.metadata.drop_all(TEST_ENGINE)


app.dependency_overrides[get_session] = get_test_session
client = TestClient(app)


def test_create_and_list_project():
    resp = client.post("/projects", json={"name": "Checkout Release 2.3"})
    assert resp.status_code == 200
    project = resp.json()
    assert project["name"] == "Checkout Release 2.3"

    resp = client.get("/projects")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_defects_upload_and_summary():
    project = client.post("/projects", json={"name": "Test Project"}).json()
    project_id = project["id"]

    csv_content = (
        "external_id,title,severity,status,module,created_date,resolved_date,reopened_count\n"
        "PROJ-1,Login fails,critical,open,auth,2024-01-01,,0\n"
        "PROJ-2,Slow search,medium,resolved,search,2024-01-02,2024-01-05,1\n"
    )
    files = {"file": ("defects.csv", io.BytesIO(csv_content.encode()), "text/csv")}
    resp = client.post(f"/projects/{project_id}/defects/upload", files=files)
    assert resp.status_code == 200
    assert resp.json()["inserted"] == 2

    resp = client.get(f"/projects/{project_id}/defects/summary")
    assert resp.status_code == 200
    summary = resp.json()
    assert summary["total"] == 2
    assert summary["open_count"] == 1
    assert summary["by_severity"]["critical"] == 1


def test_dataset_upload_and_quality():
    project = client.post("/projects", json={"name": "Data Project"}).json()
    project_id = project["id"]

    csv_content = "id,email\n" + "\n".join(f"{i},x@y.com" for i in range(10)) + "\n11,\n12,\n13,\n"
    files = {"file": ("data.csv", io.BytesIO(csv_content.encode()), "text/csv")}
    resp = client.post(f"/projects/{project_id}/dataset/upload", files=files)
    assert resp.status_code == 200
    body = resp.json()
    assert body["row_count"] == 13


def test_readiness_combines_both_signals():
    project = client.post("/projects", json={"name": "Combo Project"}).json()
    project_id = project["id"]

    defects_csv = (
        "external_id,title,severity,status,created_date,reopened_count\n"
        "PROJ-1,Bug,critical,open,2024-01-01,0\n"
    )
    client.post(
        f"/projects/{project_id}/defects/upload",
        files={"file": ("d.csv", io.BytesIO(defects_csv.encode()), "text/csv")},
    )

    resp = client.get(f"/projects/{project_id}/readiness")
    assert resp.status_code == 200
    body = resp.json()
    assert body["qa_score"] == 85.0  # 100 - 15 for one open critical
    assert body["data_score"] == 100.0  # no dataset uploaded yet
    assert "combined_score" in body
    assert "AT RISK" in body["summary_text"] or "READY" in body["summary_text"] or "NOT RECOMMENDED" in body["summary_text"]


def test_readiness_404_for_unknown_project():
    resp = client.get("/projects/9999/readiness")
    assert resp.status_code == 404


def test_defects_summary_404_when_no_defects():
    project = client.post("/projects", json={"name": "Empty Project"}).json()
    resp = client.get(f"/projects/{project['id']}/defects/summary")
    assert resp.status_code == 404
