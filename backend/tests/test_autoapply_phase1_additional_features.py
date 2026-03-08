import os
import time
from pathlib import Path

import pytest
import requests

# Phase 1 additional feature regression tests: Gmail OAuth/poll preconditions, direct-apply queue path,
# application detail proof fields, and follow-up draft/send constraints.


def _load_backend_url_from_frontend_env() -> str:
    env_path = Path("/app/frontend/.env")
    if not env_path.exists():
        return ""
    for line in env_path.read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            return line.split("=", 1)[1].strip()
    return ""


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL") or _load_backend_url_from_frontend_env()


@pytest.fixture(scope="session")
def api_base_url() -> str:
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL is not set")
    return BASE_URL.rstrip("/") + "/api"


@pytest.fixture(scope="session")
def api_client() -> requests.Session:
    session = requests.Session()
    session.headers.update({"Accept": "application/json", "Content-Type": "application/json"})
    return session


@pytest.fixture(scope="session")
def original_settings(api_client: requests.Session, api_base_url: str) -> dict:
    response = api_client.get(f"{api_base_url}/settings", timeout=60)
    assert response.status_code == 200
    return response.json()


@pytest.fixture(scope="session", autouse=True)
def restore_settings_on_exit(api_client: requests.Session, api_base_url: str, original_settings: dict):
    yield
    api_client.put(f"{api_base_url}/settings", json=original_settings, timeout=60)


def _save_settings(api_client: requests.Session, api_base_url: str, settings_payload: dict) -> dict:
    response = api_client.put(f"{api_base_url}/settings", json=settings_payload, timeout=60)
    assert response.status_code == 200
    return response.json()


def _get_applications(api_client: requests.Session, api_base_url: str) -> list:
    response = api_client.get(f"{api_base_url}/applications", timeout=60)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    return data


def _get_jobs(api_client: requests.Session, api_base_url: str) -> list:
    response = api_client.get(f"{api_base_url}/jobs", params={"min_score": 0}, timeout=60)
    assert response.status_code == 200
    jobs = response.json()
    assert isinstance(jobs, list)
    return jobs


def test_01_settings_supports_google_oauth_fields(api_client: requests.Session, api_base_url: str, original_settings: dict):
    payload = {
        **original_settings,
        "google_client_id": "test-google-client-id",
        "google_client_secret": "test-google-client-secret",
        "daily_application_limit": max(int(original_settings.get("daily_application_limit", 20)), 50),
    }
    saved = _save_settings(api_client, api_base_url, payload)

    assert saved["google_client_id"] == "test-google-client-id"
    assert saved["google_client_secret"] == "test-google-client-secret"

    fetched = api_client.get(f"{api_base_url}/settings", timeout=60)
    assert fetched.status_code == 200
    fetched_json = fetched.json()
    assert fetched_json["google_client_id"] == "test-google-client-id"
    assert fetched_json["google_client_secret"] == "test-google-client-secret"


def test_02_gmail_status_endpoint_shape(api_client: requests.Session, api_base_url: str):
    response = api_client.get(f"{api_base_url}/gmail/status", timeout=60)
    assert response.status_code == 200

    data = response.json()
    assert "connected" in data
    assert isinstance(data["connected"], bool)
    assert "expires_at" in data
    assert "scope" in data


def test_03_gmail_oauth_start_without_credentials_returns_400(api_client: requests.Session, api_base_url: str, original_settings: dict):
    payload = {
        **original_settings,
        "google_client_id": "",
        "google_client_secret": "",
    }
    _save_settings(api_client, api_base_url, payload)

    response = api_client.get(
        f"{api_base_url}/gmail/oauth/start",
        params={"return_url": f"{BASE_URL.rstrip('/')}/settings"},
        timeout=60,
    )
    assert response.status_code == 400
    assert "Google Client ID and Secret" in response.json().get("detail", "")


def test_04_gmail_oauth_start_with_credentials_returns_auth_url(api_client: requests.Session, api_base_url: str, original_settings: dict):
    payload = {
        **original_settings,
        "google_client_id": "fake-client-id",
        "google_client_secret": "fake-client-secret",
    }
    _save_settings(api_client, api_base_url, payload)

    response = api_client.get(
        f"{api_base_url}/gmail/oauth/start",
        params={"return_url": f"{BASE_URL.rstrip('/')}/settings"},
        timeout=60,
    )
    assert response.status_code == 200

    data = response.json()
    auth_url = data.get("auth_url", "")
    assert auth_url.startswith("https://accounts.google.com/o/oauth2/v2/auth")
    assert "state=" in auth_url
    assert "scope=" in auth_url


def test_05_gmail_poll_disconnected_returns_400(api_client: requests.Session, api_base_url: str):
    status_response = api_client.get(f"{api_base_url}/gmail/status", timeout=60)
    assert status_response.status_code == 200
    status_json = status_response.json()

    if status_json.get("connected"):
        pytest.skip("Gmail already connected in this environment; disconnected precondition not applicable")

    response = api_client.post(f"{api_base_url}/gmail/poll", timeout=60)
    assert response.status_code == 400
    assert "Gmail is not connected" in response.json().get("detail", "")


def test_06_direct_apply_queue_path_for_jobs_without_application_email(api_client: requests.Session, api_base_url: str):
    settings_response = api_client.get(f"{api_base_url}/settings", timeout=60)
    assert settings_response.status_code == 200
    settings = settings_response.json()
    settings["daily_application_limit"] = max(int(settings.get("daily_application_limit", 20)), 50)
    _save_settings(api_client, api_base_url, settings)

    jobs = _get_jobs(api_client, api_base_url)
    candidate = next(
        (
            j
            for j in jobs
            if not (j.get("application_email") or "").strip() and (j.get("apply_url") or "").startswith("http")
        ),
        None,
    )
    if not candidate:
        pytest.skip("No job found with direct-apply URL and empty application_email")

    queue_response = api_client.post(f"{api_base_url}/applications/queue/{candidate['id']}", timeout=60)
    assert queue_response.status_code == 200
    queue_data = queue_response.json()
    application_id = queue_data["application_id"]

    run_response = api_client.post(f"{api_base_url}/auto-apply/run", timeout=240)
    assert run_response.status_code == 200
    run_data = run_response.json()
    assert "processed" in run_data

    # Allow async processing / persistence flush time.
    time.sleep(2)

    detail_response = api_client.get(f"{api_base_url}/applications/detail/{application_id}", timeout=60)
    assert detail_response.status_code == 200
    detail = detail_response.json()
    attempts = detail.get("attempts", [])
    assert isinstance(attempts, list)
    assert len(attempts) >= 1

    latest_attempt = attempts[0]
    assert latest_attempt.get("method") == "direct_apply"
    assert "success" in latest_attempt


def test_07_application_detail_proof_fields_consistency(api_client: requests.Session, api_base_url: str):
    apps = _get_applications(api_client, api_base_url)
    if not apps:
        pytest.skip("No applications found for detail proof checks")

    application_id = apps[0]["id"]
    detail_response = api_client.get(f"{api_base_url}/applications/detail/{application_id}", timeout=60)
    assert detail_response.status_code == 200
    detail = detail_response.json()

    assert "proof_image_available" in detail
    assert "proof_image_url" in detail

    if detail["proof_image_available"]:
        assert detail["proof_image_url"].startswith("/api/applications/detail/")
        proof_response = api_client.get(f"{BASE_URL.rstrip('/')}{detail['proof_image_url']}", timeout=60)
        assert proof_response.status_code == 200
    else:
        assert detail["proof_image_url"] == ""


def test_08_followup_generate_stores_draft_fields(api_client: requests.Session, api_base_url: str):
    apps = _get_applications(api_client, api_base_url)
    if not apps:
        pytest.skip("No applications found for follow-up generation")

    application_id = apps[0]["id"]

    response = api_client.post(f"{api_base_url}/applications/detail/{application_id}/followup/generate", timeout=120)
    assert response.status_code == 200

    detail_response = api_client.get(f"{api_base_url}/applications/detail/{application_id}", timeout=60)
    assert detail_response.status_code == 200
    detail = detail_response.json()
    app = detail["application"]

    assert isinstance(app.get("followup_draft_subject", ""), str)
    assert isinstance(app.get("followup_draft_body", ""), str)
    assert len((app.get("followup_draft_subject") or "").strip()) > 0
    assert len((app.get("followup_draft_body") or "").strip()) > 0


def test_09_followup_send_handles_missing_gmail_or_recipient_gracefully(api_client: requests.Session, api_base_url: str):
    apps = _get_applications(api_client, api_base_url)
    if not apps:
        pytest.skip("No applications found for follow-up send validation")

    target = None
    for app in apps:
        if app.get("followup_sent_at"):
            target = app
            break

    if target:
        response = api_client.post(f"{api_base_url}/applications/detail/{target['id']}/followup/send", timeout=60)
        assert response.status_code == 400
        assert "already sent" in response.json().get("detail", "").lower()
        return

    target = next((a for a in apps if not (a.get("recruiter_email") or "").strip()), None)
    if not target:
        pytest.skip("No application with missing recruiter_email found for graceful error validation")

    response = api_client.post(f"{api_base_url}/applications/detail/{target['id']}/followup/send", timeout=90)
    assert response.status_code == 400
    detail_text = response.json().get("detail", "")
    # Depending on app data and Gmail connectivity, backend can fail for missing recipient or Gmail precondition.
    assert (
        "No recruiter email" in detail_text
        or "Gmail is not connected" in detail_text
        or "Gmail refresh token" in detail_text
    )
