import io
import os
import uuid

import pytest
import requests
from reportlab.pdfgen import canvas

# Phase 1 critical API regression tests: profile/CV, preferences/settings, jobs, docs, queue, kanban, dashboard.

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")


@pytest.fixture(scope="session")
def api_base_url() -> str:
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL is not set")
    return BASE_URL.rstrip("/") + "/api"


@pytest.fixture(scope="session")
def api_client() -> requests.Session:
    session = requests.Session()
    session.headers.update({"Accept": "application/json"})
    return session


@pytest.fixture(scope="session")
def state() -> dict:
    return {}


def _build_pdf_bytes(text: str) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.drawString(72, 800, text)
    pdf.drawString(72, 780, "Skills: Python, FastAPI, React, MongoDB, Communication")
    pdf.drawString(72, 760, "Experience: Built APIs and frontend dashboards")
    pdf.save()
    buffer.seek(0)
    return buffer.read()


def test_01_health(api_client: requests.Session, api_base_url: str):
    response = api_client.get(f"{api_base_url}/health", timeout=60)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert isinstance(data["time"], str)


def test_02_upload_cv_pdf_and_parse_profile(api_client: requests.Session, api_base_url: str, state: dict):
    pdf_bytes = _build_pdf_bytes(f"TEST CV {uuid.uuid4()}")
    files = {"file": ("test_resume.pdf", pdf_bytes, "application/pdf")}

    response = api_client.post(f"{api_base_url}/profile/upload-cv", files=files, timeout=120)
    assert response.status_code == 200
    data = response.json()

    assert data["filename"] == "test_resume.pdf"
    assert isinstance(data["resume_text"], str)
    assert len(data["resume_text"].strip()) > 0
    assert "parsed" in data
    assert isinstance(data["parsed"].get("skills_technical", []), list)
    assert "summary" in data["parsed"]

    state["profile_after_upload"] = data


def test_03_preferences_save_and_retrieve(api_client: requests.Session, api_base_url: str, state: dict):
    payload = {
        "target_job_titles": ["Backend Engineer", "Python Developer"],
        "preferred_industries": ["SaaS", "AI"],
        "location_preferences": ["Remote"],
        "remote_mode": "remote",
        "salary_min": 120000,
        "salary_max": 220000,
        "company_size_preference": "any",
        "blacklisted_companies": ["TEST_BlacklistCo"],
        "application_frequency": "moderate",
        "auto_apply_enabled": False,
    }

    put_response = api_client.put(f"{api_base_url}/preferences", json=payload, timeout=60)
    assert put_response.status_code == 200
    saved = put_response.json()
    assert saved["target_job_titles"] == payload["target_job_titles"]
    assert saved["salary_min"] == payload["salary_min"]

    get_response = api_client.get(f"{api_base_url}/preferences", timeout=60)
    assert get_response.status_code == 200
    fetched = get_response.json()
    assert fetched["preferred_industries"] == payload["preferred_industries"]
    assert fetched["remote_mode"] == payload["remote_mode"]

    state["preferences"] = fetched


def test_04_settings_save_and_retrieve(api_client: requests.Session, api_base_url: str, state: dict):
    current = api_client.get(f"{api_base_url}/settings", timeout=60)
    assert current.status_code == 200
    current_data = current.json()

    payload = {
        **current_data,
        "adzuna_country": "us",
        "score_threshold": 65,
        "daily_application_limit": 15,
        "auto_apply_enabled": False,
        "business_hours_only": False,
        "discovery_interval_hours": 6,
        "resume_template": "Modern",
    }

    put_response = api_client.put(f"{api_base_url}/settings", json=payload, timeout=60)
    assert put_response.status_code == 200
    saved = put_response.json()
    assert saved["score_threshold"] == 65
    assert saved["daily_application_limit"] == 15

    get_response = api_client.get(f"{api_base_url}/settings", timeout=60)
    assert get_response.status_code == 200
    fetched = get_response.json()
    assert fetched["discovery_interval_hours"] == 6
    assert fetched["resume_template"] == "Modern"

    state["settings"] = fetched


def test_05_discover_jobs_and_list_with_scores(api_client: requests.Session, api_base_url: str, state: dict):
    discover_response = api_client.post(f"{api_base_url}/jobs/discover", timeout=120)
    assert discover_response.status_code == 200
    discover_data = discover_response.json()
    assert "fetched" in discover_data
    assert "deduped" in discover_data

    jobs_response = api_client.get(f"{api_base_url}/jobs", params={"min_score": 0}, timeout=60)
    assert jobs_response.status_code == 200
    jobs = jobs_response.json()
    assert isinstance(jobs, list)
    assert len(jobs) > 0

    first_job = jobs[0]
    assert isinstance(first_job["id"], str)
    assert isinstance(first_job.get("match_score"), int)
    assert 0 <= first_job["match_score"] <= 100
    assert isinstance(first_job.get("score_breakdown"), dict)
    assert "matched_skills" in first_job

    sources = {job.get("source") for job in jobs if job.get("source")}
    assert "remotive" in sources

    state["job_id"] = first_job["id"]


def test_06_job_detail_and_generate_docs(api_client: requests.Session, api_base_url: str, state: dict):
    job_id = state.get("job_id")
    assert job_id, "No job_id from discovery/list test"

    detail_response = api_client.get(f"{api_base_url}/jobs/{job_id}", timeout=60)
    assert detail_response.status_code == 200
    detail_data = detail_response.json()
    assert detail_data["job"]["id"] == job_id

    generate_response = api_client.post(f"{api_base_url}/jobs/{job_id}/generate-documents", timeout=180)
    assert generate_response.status_code == 200
    doc = generate_response.json()

    assert doc["job_id"] == job_id
    assert isinstance(doc.get("tailored_resume_text"), str)
    assert len(doc["tailored_resume_text"].strip()) > 0
    assert isinstance(doc.get("cover_letter_text"), str)
    assert len(doc["cover_letter_text"].strip()) > 0

    state["document_id"] = doc["id"]


def test_07_pdf_download_endpoints(api_client: requests.Session, api_base_url: str, state: dict):
    document_id = state.get("document_id")
    assert document_id, "No document_id from document generation test"

    resume_response = api_client.get(f"{api_base_url}/documents/{document_id}/download/resume", timeout=60)
    assert resume_response.status_code == 200
    assert "application/pdf" in resume_response.headers.get("content-type", "")
    assert len(resume_response.content) > 100

    cover_response = api_client.get(f"{api_base_url}/documents/{document_id}/download/cover", timeout=60)
    assert cover_response.status_code == 200
    assert "application/pdf" in cover_response.headers.get("content-type", "")
    assert len(cover_response.content) > 100


def test_08_queue_and_run_auto_apply(api_client: requests.Session, api_base_url: str, state: dict):
    job_id = state.get("job_id")
    assert job_id, "No job_id from discovery/list test"

    queue_response = api_client.post(f"{api_base_url}/applications/queue/{job_id}", timeout=60)
    assert queue_response.status_code == 200
    queue_data = queue_response.json()
    assert queue_data["queued"] is True
    assert queue_data["job_id"] == job_id

    run_response = api_client.post(f"{api_base_url}/auto-apply/run", timeout=180)
    assert run_response.status_code == 200
    run_data = run_response.json()
    assert "processed" in run_data
    assert "success_count" in run_data or "message" in run_data

    state["application_id"] = queue_data["application_id"]


def test_09_applications_attempts_and_kanban(api_client: requests.Session, api_base_url: str, state: dict):
    apps_response = api_client.get(f"{api_base_url}/applications", timeout=60)
    assert apps_response.status_code == 200
    apps = apps_response.json()
    assert isinstance(apps, list)
    assert len(apps) > 0

    app = next((a for a in apps if a.get("id") == state.get("application_id")), apps[0])
    assert isinstance(app.get("status"), str)
    assert app.get("status") in {
        "Discovered",
        "Tailoring",
        "Applied",
        "Under Review",
        "Interview Scheduled",
        "Offer Received",
        "Rejected",
        "Withdrawn",
    }

    kanban_response = api_client.get(f"{api_base_url}/applications/kanban", timeout=60)
    assert kanban_response.status_code == 200
    kanban = kanban_response.json()
    assert isinstance(kanban, dict)
    assert "Discovered" in kanban


def test_10_dashboard_metrics(api_client: requests.Session, api_base_url: str):
    response = api_client.get(f"{api_base_url}/dashboard/metrics", timeout=60)
    assert response.status_code == 200
    data = response.json()

    assert "kpis" in data
    assert isinstance(data["kpis"].get("applications_total"), int)
    assert isinstance(data.get("source_breakdown"), list)
    assert isinstance(data.get("status_breakdown"), list)
    assert isinstance(data.get("applications_over_time"), list)
