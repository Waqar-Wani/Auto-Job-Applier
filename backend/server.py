import asyncio
import base64
import io
import json
import logging
import os
import random
import re
import textwrap
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from docx import Document
from dotenv import load_dotenv
from emergentintegrations.llm.chat import LlmChat, UserMessage
from fastapi import APIRouter, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from PyPDF2 import PdfReader
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas
from starlette.middleware.cors import CORSMiddleware


ROOT_DIR = Path(__file__).parent
GENERATED_DIR = ROOT_DIR / "generated_docs"
PROOF_DIR = ROOT_DIR / "proofs"
load_dotenv(ROOT_DIR / ".env")

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

DEFAULT_USER_ID = "default-user"
BACKOFF_MINUTES = [5, 15, 45]
KANBAN_STATUSES = [
    "Discovered",
    "Tailoring",
    "Applied",
    "Under Review",
    "Interview Scheduled",
    "Offer Received",
    "Rejected",
    "Withdrawn",
]


class ParsedProfile(BaseModel):
    skills_technical: List[str] = Field(default_factory=list)
    skills_soft: List[str] = Field(default_factory=list)
    work_experience: List[Dict[str, Any]] = Field(default_factory=list)
    education: List[Dict[str, Any]] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)
    projects: List[str] = Field(default_factory=list)
    languages: List[str] = Field(default_factory=list)
    summary: str = ""


class UserProfileResponse(BaseModel):
    id: str
    user_id: str
    filename: Optional[str] = None
    resume_text: str = ""
    parsed: ParsedProfile
    updated_at: str


class PreferencePayload(BaseModel):
    target_job_titles: List[str] = Field(default_factory=list)
    preferred_industries: List[str] = Field(default_factory=list)
    location_preferences: List[str] = Field(default_factory=lambda: ["Remote"])
    remote_mode: Literal["remote", "hybrid", "onsite", "any"] = "remote"
    salary_min: int = 0
    salary_max: int = 250000
    company_size_preference: Literal["startup", "mid", "enterprise", "any"] = "any"
    blacklisted_companies: List[str] = Field(default_factory=list)
    application_frequency: Literal["aggressive", "moderate", "conservative"] = "moderate"
    auto_apply_enabled: bool = False


class SettingsPayload(BaseModel):
    adzuna_app_id: str = ""
    adzuna_app_key: str = ""
    adzuna_country: str = "us"
    score_threshold: int = 70
    daily_application_limit: int = 20
    auto_apply_enabled: bool = False
    business_hours_only: bool = False
    discovery_interval_hours: int = 6
    resend_api_key: str = ""
    sender_email: str = "onboarding@resend.dev"
    notification_email: str = ""
    resume_template: Literal["Modern", "Classic", "Minimal"] = "Modern"


class ApplicationStatusUpdate(BaseModel):
    status: Literal[
        "Discovered",
        "Tailoring",
        "Applied",
        "Under Review",
        "Interview Scheduled",
        "Offer Received",
        "Rejected",
        "Withdrawn",
    ]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


def sanitize_doc(doc: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not doc:
        return {}
    return {k: v for k, v in doc.items() if k != "_id"}


def extract_first_json_block(text: str) -> Optional[Any]:
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def safe_int(value: Any, fallback: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def extract_email_from_text(text: str) -> Optional[str]:
    match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text or "")
    return match.group(0) if match else None


def wrap_lines(text: str, width: int = 95) -> List[str]:
    lines: List[str] = []
    for paragraph in (text or "").split("\n"):
        paragraph = paragraph.strip()
        if not paragraph:
            lines.append("")
            continue
        lines.extend(textwrap.wrap(paragraph, width=width))
    return lines


def create_text_pdf(file_path: Path, title: str, body: str) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(file_path), pagesize=LETTER)
    width, height = LETTER

    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(40, height - 40, title)
    pdf.setFont("Helvetica", 10)
    y = height - 70

    for line in wrap_lines(body):
        if y < 40:
            pdf.showPage()
            pdf.setFont("Helvetica", 10)
            y = height - 40
        pdf.drawString(40, y, line)
        y -= 14

    pdf.save()


def extract_pdf_text(file_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(file_bytes))
    parts: List[str] = []
    for page in reader.pages:
        parts.append(page.extract_text() or "")
    return "\n".join(parts).strip()


def extract_docx_text(file_bytes: bytes) -> str:
    document = Document(io.BytesIO(file_bytes))
    return "\n".join([p.text for p in document.paragraphs]).strip()


def profile_fallback_parser(resume_text: str) -> Dict[str, Any]:
    sample_skills = [
        "Python",
        "JavaScript",
        "React",
        "FastAPI",
        "SQL",
        "MongoDB",
        "AWS",
        "Communication",
    ]
    lowered = resume_text.lower()
    found = [skill for skill in sample_skills if skill.lower() in lowered]
    return {
        "skills_technical": [skill for skill in found if skill not in {"Communication"}],
        "skills_soft": ["Communication"] if "communication" in lowered else [],
        "work_experience": [],
        "education": [],
        "certifications": [],
        "projects": [],
        "languages": ["English"],
        "summary": resume_text[:500],
    }


async def ai_json_response(system_message: str, prompt: str, fallback: Dict[str, Any]) -> Dict[str, Any]:
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        return fallback

    try:
        chat = LlmChat(api_key=api_key, session_id=str(uuid.uuid4()), system_message=system_message)
        try:
            chat = chat.with_model("anthropic", "claude-sonnet-4-20250514")
        except Exception:
            chat = chat.with_model("anthropic", "claude-4-sonnet-20250514")

        output = await chat.send_message(UserMessage(text=prompt))
        parsed = extract_first_json_block(str(output))
        if isinstance(parsed, dict):
            return parsed
    except Exception as exc:
        logger.warning("AI generation fallback triggered: %s", exc)

    return fallback


async def parse_resume_with_ai(resume_text: str) -> Dict[str, Any]:
    fallback = profile_fallback_parser(resume_text)
    prompt = (
        "Parse this resume into JSON with keys: skills_technical, skills_soft, work_experience, "
        "education, certifications, projects, languages, summary. Keep each key present. "
        "Work experience must be an array of objects with company, role, duration, achievements. "
        "Only output JSON.\n\n"
        f"RESUME:\n{resume_text[:12000]}"
    )
    result = await ai_json_response("You are an expert resume parser.", prompt, fallback)
    for key, default in fallback.items():
        result.setdefault(key, default)
    return result


def tokenize(text: str) -> List[str]:
    return [tok for tok in re.split(r"[^a-zA-Z0-9+#]+", (text or "").lower()) if len(tok) > 2]


def score_job_against_profile(job: Dict[str, Any], profile: Dict[str, Any], preferences: Dict[str, Any]) -> Dict[str, Any]:
    profile_skills = [
        *profile.get("parsed", {}).get("skills_technical", []),
        *profile.get("parsed", {}).get("skills_soft", []),
    ]
    profile_skill_tokens = {s.lower() for s in profile_skills}

    job_text = f"{job.get('title', '')} {job.get('description', '')}"
    job_tokens = set(tokenize(job_text))
    matched_skills = [skill for skill in profile_skills if skill.lower() in job_tokens]

    skill_score = 0
    if profile_skill_tokens:
        skill_score = min(100, int((len({m.lower() for m in matched_skills}) / len(profile_skill_tokens)) * 100))

    title_score = 0
    targets = [t.lower() for t in preferences.get("target_job_titles", [])]
    if targets:
        if any(target in (job.get("title", "").lower()) for target in targets):
            title_score = 100
        else:
            title_score = 30
    else:
        title_score = 60

    remote_pref = preferences.get("remote_mode", "any")
    location = (job.get("location") or "").lower()
    if remote_pref == "any":
        location_score = 80
    elif remote_pref == "remote":
        location_score = 100 if "remote" in location else 45
    elif remote_pref == "hybrid":
        location_score = 100 if "hybrid" in location else 55
    else:
        location_score = 100 if "remote" not in location else 55

    salary_min = safe_int(job.get("salary_min"), 0)
    salary_max = safe_int(job.get("salary_max"), 0)
    pref_min = safe_int(preferences.get("salary_min"), 0)
    pref_max = safe_int(preferences.get("salary_max"), 0)
    salary_score = 70
    if salary_min or salary_max:
        lower = salary_min or salary_max
        upper = salary_max or salary_min
        if pref_max and lower > pref_max:
            salary_score = 30
        elif pref_min and upper < pref_min:
            salary_score = 35
        else:
            salary_score = 100

    overall = int(skill_score * 0.45 + title_score * 0.2 + location_score * 0.2 + salary_score * 0.15)
    return {
        "match_score": max(0, min(100, overall)),
        "matched_skills": matched_skills,
        "score_breakdown": {
            "skill_score": skill_score,
            "title_score": title_score,
            "location_score": location_score,
            "salary_score": salary_score,
        },
    }


async def get_preferences() -> Dict[str, Any]:
    doc = await db.preferences.find_one({"user_id": DEFAULT_USER_ID}, {"_id": 0})
    if doc:
        return doc
    default_doc = PreferencePayload().model_dump()
    default_doc.update({"id": str(uuid.uuid4()), "user_id": DEFAULT_USER_ID, "updated_at": utc_now_iso()})
    await db.preferences.insert_one(default_doc.copy())
    return default_doc


async def get_settings() -> Dict[str, Any]:
    doc = await db.settings.find_one({"user_id": DEFAULT_USER_ID}, {"_id": 0})
    if doc:
        return doc
    default_doc = SettingsPayload().model_dump()
    default_doc.update({"id": str(uuid.uuid4()), "user_id": DEFAULT_USER_ID, "updated_at": utc_now_iso()})
    await db.settings.insert_one(default_doc.copy())
    return default_doc


async def get_profile() -> Dict[str, Any]:
    profile = await db.user_profiles.find_one({"user_id": DEFAULT_USER_ID}, {"_id": 0})
    if profile:
        return profile
    empty = {
        "id": str(uuid.uuid4()),
        "user_id": DEFAULT_USER_ID,
        "filename": None,
        "resume_text": "",
        "parsed": ParsedProfile().model_dump(),
        "updated_at": utc_now_iso(),
    }
    await db.user_profiles.insert_one(empty.copy())
    return empty


async def store_application_if_missing(job_doc: Dict[str, Any]) -> Dict[str, Any]:
    existing = await db.applications.find_one(
        {"user_id": DEFAULT_USER_ID, "job_id": job_doc["id"]},
        {"_id": 0},
    )
    if existing:
        return existing

    app_doc = {
        "id": str(uuid.uuid4()),
        "user_id": DEFAULT_USER_ID,
        "job_id": job_doc["id"],
        "job_title": job_doc.get("title", ""),
        "company": job_doc.get("company", ""),
        "source": job_doc.get("source", ""),
        "status": "Discovered",
        "notes": "",
        "recruiter_name": "",
        "recruiter_email": job_doc.get("application_email", ""),
        "recruiter_linkedin": "",
        "interview_datetime": "",
        "proof_url": "",
        "created_at": utc_now_iso(),
        "updated_at": utc_now_iso(),
        "last_attempt_at": "",
    }
    await db.applications.insert_one(app_doc.copy())
    return app_doc


async def queue_application(application_id: str, job_id: str) -> None:
    existing = await db.application_queue.find_one(
        {
            "application_id": application_id,
            "status": {"$in": ["pending", "retrying"]},
        },
        {"_id": 0},
    )
    if existing:
        return

    queue_doc = {
        "id": str(uuid.uuid4()),
        "application_id": application_id,
        "job_id": job_id,
        "status": "pending",
        "retry_count": 0,
        "next_attempt_at": utc_now_iso(),
        "created_at": utc_now_iso(),
        "updated_at": utc_now_iso(),
    }
    await db.application_queue.insert_one(queue_doc.copy())


async def fetch_remotive_jobs(preferences: Dict[str, Any]) -> List[Dict[str, Any]]:
    search = ""
    if preferences.get("target_job_titles"):
        search = preferences["target_job_titles"][0]

    params: Dict[str, Any] = {}
    if search:
        params["search"] = search

    async with httpx.AsyncClient(timeout=40.0) as http:
        response = await http.get("https://remotive.com/api/remote-jobs", params=params)
        response.raise_for_status()
        payload = response.json()

    jobs: List[Dict[str, Any]] = []
    for item in payload.get("jobs", []):
        description = item.get("description", "")
        jobs.append(
            {
                "source": "remotive",
                "external_id": str(item.get("id") or uuid.uuid4()),
                "title": item.get("title") or "",
                "company": item.get("company_name") or "",
                "location": item.get("candidate_required_location") or "Remote",
                "description": description,
                "job_type": item.get("job_type") or "",
                "salary_min": 0,
                "salary_max": 0,
                "salary_text": item.get("salary") or "",
                "industry": item.get("category") or "",
                "apply_url": item.get("url") or "",
                "application_email": extract_email_from_text(description),
                "company_size": "",
                "raw": item,
            }
        )
    return jobs


async def fetch_adzuna_jobs(preferences: Dict[str, Any], settings: Dict[str, Any]) -> List[Dict[str, Any]]:
    app_id = settings.get("adzuna_app_id") or ""
    app_key = settings.get("adzuna_app_key") or ""
    if not app_id or not app_key:
        return []

    query_title = ""
    if preferences.get("target_job_titles"):
        query_title = preferences["target_job_titles"][0]

    where = ""
    if preferences.get("location_preferences"):
        where = preferences["location_preferences"][0]

    country = (settings.get("adzuna_country") or "us").lower()
    endpoint = f"https://api.adzuna.com/v1/api/jobs/{country}/search/1"
    params = {
        "app_id": app_id,
        "app_key": app_key,
        "what": query_title,
        "where": where,
        "results_per_page": 30,
        "content-type": "application/json",
    }

    async with httpx.AsyncClient(timeout=40.0) as http:
        response = await http.get(endpoint, params=params)
        response.raise_for_status()
        payload = response.json()

    jobs: List[Dict[str, Any]] = []
    for item in payload.get("results", []):
        description = item.get("description", "")
        company_obj = item.get("company") or {}
        location_obj = item.get("location") or {}

        jobs.append(
            {
                "source": "adzuna",
                "external_id": str(item.get("id") or uuid.uuid4()),
                "title": item.get("title") or "",
                "company": company_obj.get("display_name") or "",
                "location": location_obj.get("display_name") or "",
                "description": description,
                "job_type": item.get("contract_type") or "",
                "salary_min": safe_int(item.get("salary_min"), 0),
                "salary_max": safe_int(item.get("salary_max"), 0),
                "salary_text": "",
                "industry": item.get("category", {}).get("label", ""),
                "apply_url": item.get("redirect_url") or "",
                "application_email": extract_email_from_text(description),
                "company_size": "",
                "raw": item,
            }
        )
    return jobs


async def run_job_discovery() -> Dict[str, Any]:
    preferences = await get_preferences()
    settings = await get_settings()
    profile = await get_profile()

    remotive_jobs, adzuna_jobs = await asyncio.gather(
        fetch_remotive_jobs(preferences),
        fetch_adzuna_jobs(preferences, settings),
    )

    combined = [*remotive_jobs, *adzuna_jobs]
    deduped: Dict[str, Dict[str, Any]] = {}
    for job in combined:
        key = f"{job.get('title', '').lower()}::{job.get('company', '').lower()}::{job.get('location', '').lower()}"
        if key not in deduped:
            deduped[key] = job

    created = 0
    updated = 0
    queued = 0

    for job in deduped.values():
        score = score_job_against_profile(job, profile, preferences)
        now = utc_now_iso()
        filter_query = {
            "user_id": DEFAULT_USER_ID,
            "source": job["source"],
            "external_id": job["external_id"],
        }

        existing = await db.jobs.find_one(filter_query, {"_id": 0, "id": 1})
        job_id = existing["id"] if existing else str(uuid.uuid4())
        job_doc = {
            "id": job_id,
            "user_id": DEFAULT_USER_ID,
            **job,
            "match_score": score["match_score"],
            "matched_skills": score["matched_skills"],
            "score_breakdown": score["score_breakdown"],
            "updated_at": now,
            "discovered_at": now,
        }

        await db.jobs.update_one(filter_query, {"$set": job_doc}, upsert=True)
        if existing:
            updated += 1
        else:
            created += 1

        application = await store_application_if_missing(job_doc)
        if settings.get("auto_apply_enabled") and job_doc["match_score"] >= settings.get("score_threshold", 70):
            await queue_application(application["id"], job_doc["id"])
            queued += 1

    return {
        "fetched": len(combined),
        "deduped": len(deduped),
        "created": created,
        "updated": updated,
        "queued": queued,
    }


async def generate_documents_for_job(job_id: str) -> Dict[str, Any]:
    profile = await get_profile()
    if not profile.get("resume_text"):
        raise HTTPException(status_code=400, detail="Upload CV before generating tailored documents.")

    job = await db.jobs.find_one({"id": job_id, "user_id": DEFAULT_USER_ID}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    fallback_resume = (
        f"Tailored Resume for {job.get('title')} at {job.get('company')}\n\n"
        f"Core Skills: {', '.join(job.get('matched_skills', []) or profile.get('parsed', {}).get('skills_technical', [])[:8])}\n\n"
        f"Professional Summary:\n{profile.get('parsed', {}).get('summary', '')}\n"
    )
    fallback_cover = (
        f"Dear Hiring Team at {job.get('company')},\n\n"
        f"I am excited to apply for the {job.get('title')} role. My experience aligns with your requirements and I would love "
        f"to contribute to your team.\n\n"
        "In previous roles, I delivered measurable outcomes and collaborated cross-functionally to ship high-impact projects. "
        "I am confident this background can add value quickly.\n\n"
        "Thank you for your time and consideration. I look forward to discussing how I can contribute.\n"
    )

    prompt = (
        "Return JSON only with keys tailored_resume and cover_letter. "
        "Tailored resume must be ATS optimized and truthful to source CV. "
        "Cover letter must be 3-4 paragraphs and under 400 words.\n\n"
        f"JOB:\n{json.dumps(job, ensure_ascii=False)[:8000]}\n\n"
        f"PROFILE:\n{json.dumps(profile.get('parsed', {}), ensure_ascii=False)[:8000]}\n\n"
        f"ORIGINAL RESUME:\n{profile.get('resume_text', '')[:9000]}"
    )

    generated = await ai_json_response(
        "You are a senior recruiting writer crafting job-specific documents.",
        prompt,
        {"tailored_resume": fallback_resume, "cover_letter": fallback_cover},
    )

    tailored_resume = generated.get("tailored_resume") or fallback_resume
    cover_letter = generated.get("cover_letter") or fallback_cover

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    resume_path = GENERATED_DIR / f"resume_{job_id}_{timestamp}.pdf"
    cover_path = GENERATED_DIR / f"cover_{job_id}_{timestamp}.pdf"
    create_text_pdf(resume_path, f"Tailored Resume • {job.get('title', '')}", tailored_resume)
    create_text_pdf(cover_path, f"Cover Letter • {job.get('company', '')}", cover_letter)

    doc_record = {
        "id": str(uuid.uuid4()),
        "user_id": DEFAULT_USER_ID,
        "job_id": job_id,
        "tailored_resume_text": tailored_resume,
        "cover_letter_text": cover_letter,
        "resume_pdf_path": str(resume_path),
        "cover_pdf_path": str(cover_path),
        "created_at": utc_now_iso(),
    }
    await db.documents.insert_one(doc_record.copy())

    await db.applications.update_one(
        {"job_id": job_id, "user_id": DEFAULT_USER_ID},
        {"$set": {"status": "Tailoring", "updated_at": utc_now_iso()}},
    )

    return doc_record


async def send_email_via_resend(
    to_email: str,
    settings: Dict[str, Any],
    job: Dict[str, Any],
    document: Dict[str, Any],
) -> Dict[str, Any]:
    resend_key = settings.get("resend_api_key")
    if not resend_key:
        raise RuntimeError("Resend API key not configured in settings.")

    resume_path = Path(document["resume_pdf_path"])
    cover_path = Path(document["cover_pdf_path"])
    with open(resume_path, "rb") as resume_file:
        resume_b64 = base64.b64encode(resume_file.read()).decode("utf-8")
    with open(cover_path, "rb") as cover_file:
        cover_b64 = base64.b64encode(cover_file.read()).decode("utf-8")

    payload = {
        "from": settings.get("sender_email") or "onboarding@resend.dev",
        "to": [to_email],
        "subject": f"Application: {job.get('title')} - {job.get('company')}",
        "html": (
            f"<p>Hello,</p><p>Please find my application for the <strong>{job.get('title')}</strong> role at "
            f"<strong>{job.get('company')}</strong>.</p><p>Best regards,</p>"
        ),
        "attachments": [
            {"filename": "resume.pdf", "content": resume_b64},
            {"filename": "cover_letter.pdf", "content": cover_b64},
        ],
    }

    async with httpx.AsyncClient(timeout=40.0) as http:
        response = await http.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json"},
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

    return {"provider": "resend", "message_id": data.get("id", ""), "raw": data}


async def execute_direct_apply(job: Dict[str, Any], application_id: str) -> Dict[str, Any]:
    apply_url = job.get("apply_url")
    if not apply_url:
        raise RuntimeError("No direct apply URL found.")

    async with httpx.AsyncClient(timeout=40.0, follow_redirects=True) as http:
        response = await http.get(apply_url)

    PROOF_DIR.mkdir(parents=True, exist_ok=True)
    proof_path = PROOF_DIR / f"direct_apply_{application_id}_{int(datetime.now(timezone.utc).timestamp())}.txt"
    proof_text = (
        f"DIRECT APPLY PROOF\n"
        f"Timestamp: {utc_now_iso()}\n"
        f"URL: {apply_url}\n"
        f"Status Code: {response.status_code}\n"
        f"Final URL: {str(response.url)}\n"
    )
    proof_path.write_text(proof_text, encoding="utf-8")

    if response.status_code >= 400:
        raise RuntimeError(f"Direct apply URL returned {response.status_code}")

    return {"provider": "direct_apply", "proof_path": str(proof_path), "status_code": response.status_code}


async def process_one_application(queue_item: Dict[str, Any]) -> Dict[str, Any]:
    application = await db.applications.find_one({"id": queue_item["application_id"]}, {"_id": 0})
    if not application:
        await db.application_queue.update_one(
            {"id": queue_item["id"]},
            {"$set": {"status": "failed", "updated_at": utc_now_iso()}},
        )
        return {"application_id": queue_item["application_id"], "success": False, "error": "Application not found"}

    job = await db.jobs.find_one({"id": application["job_id"]}, {"_id": 0})
    if not job:
        await db.application_queue.update_one(
            {"id": queue_item["id"]},
            {"$set": {"status": "failed", "updated_at": utc_now_iso()}},
        )
        return {"application_id": application["id"], "success": False, "error": "Job not found"}

    settings = await get_settings()
    if settings.get("business_hours_only"):
        now = datetime.now(timezone.utc)
        if now.weekday() >= 5 or now.hour < 9 or now.hour > 17:
            await db.application_queue.update_one(
                {"id": queue_item["id"]},
                {"$set": {"next_attempt_at": (now + timedelta(minutes=30)).isoformat(), "updated_at": utc_now_iso()}},
            )
            return {"application_id": application["id"], "success": False, "error": "Outside business hours"}

    document = await db.documents.find_one(
        {"job_id": job["id"], "user_id": DEFAULT_USER_ID},
        {"_id": 0},
        sort=[("created_at", -1)],
    )
    if not document:
        document = await generate_documents_for_job(job["id"])

    method = "direct_apply"
    success = False
    proof = ""
    error = ""

    try:
        if job.get("application_email"):
            method = "email"
            email_result = await send_email_via_resend(job["application_email"], settings, job, document)
            success = True
            proof = email_result.get("message_id", "")
        else:
            direct_result = await execute_direct_apply(job, application["id"])
            success = True
            proof = direct_result.get("proof_path", "")
    except Exception as exc:
        error = str(exc)

    attempt = {
        "id": str(uuid.uuid4()),
        "application_id": application["id"],
        "job_id": job["id"],
        "method": method,
        "success": success,
        "error": error,
        "proof": proof,
        "timestamp": utc_now_iso(),
    }
    await db.application_attempts.insert_one(attempt.copy())

    if success:
        await db.applications.update_one(
            {"id": application["id"]},
            {
                "$set": {
                    "status": "Applied",
                    "proof_url": proof,
                    "last_attempt_at": utc_now_iso(),
                    "updated_at": utc_now_iso(),
                }
            },
        )
        await db.application_queue.update_one(
            {"id": queue_item["id"]},
            {"$set": {"status": "done", "updated_at": utc_now_iso()}},
        )
        return {"application_id": application["id"], "success": True, "method": method}

    retry_count = queue_item.get("retry_count", 0) + 1
    if retry_count > 3:
        await db.application_queue.update_one(
            {"id": queue_item["id"]},
            {"$set": {"status": "failed", "updated_at": utc_now_iso(), "retry_count": retry_count}},
        )
        return {"application_id": application["id"], "success": False, "error": error}

    delay_minutes = BACKOFF_MINUTES[min(retry_count - 1, len(BACKOFF_MINUTES) - 1)]
    next_attempt = datetime.now(timezone.utc) + timedelta(minutes=delay_minutes)
    await db.application_queue.update_one(
        {"id": queue_item["id"]},
        {
            "$set": {
                "status": "retrying",
                "retry_count": retry_count,
                "next_attempt_at": next_attempt.isoformat(),
                "updated_at": utc_now_iso(),
            }
        },
    )
    return {"application_id": application["id"], "success": False, "error": error}


async def process_queue(max_items: int = 5, fast_mode: bool = False) -> Dict[str, Any]:
    settings = await get_settings()
    now = datetime.now(timezone.utc)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()

    today_count = await db.application_attempts.count_documents(
        {"success": True, "timestamp": {"$gte": start_of_day}}
    )
    remaining = max(0, settings.get("daily_application_limit", 20) - today_count)
    if remaining <= 0:
        return {"processed": 0, "message": "Daily application limit reached."}

    queue_items = await db.application_queue.find(
        {
            "status": {"$in": ["pending", "retrying"]},
            "next_attempt_at": {"$lte": now.isoformat()},
        },
        {"_id": 0},
    ).sort("created_at", 1).to_list(min(max_items, remaining))

    results: List[Dict[str, Any]] = []
    for item in queue_items:
        result = await process_one_application(item)
        results.append(result)
        if not fast_mode:
            await asyncio.sleep(random.randint(30, 120))

    return {
        "processed": len(results),
        "success_count": len([r for r in results if r.get("success")]),
        "failure_count": len([r for r in results if not r.get("success")]),
        "results": results,
    }


scheduler = AsyncIOScheduler()


async def scheduled_discovery_job() -> None:
    try:
        await run_job_discovery()
    except Exception as exc:
        logger.error("Scheduled discovery failed: %s", exc)


async def scheduled_queue_job() -> None:
    try:
        settings = await get_settings()
        if settings.get("auto_apply_enabled"):
            await process_queue(max_items=3, fast_mode=True)
    except Exception as exc:
        logger.error("Scheduled queue processing failed: %s", exc)


async def refresh_scheduler() -> None:
    settings = await get_settings()
    interval_hours = max(1, safe_int(settings.get("discovery_interval_hours"), 6))

    if scheduler.get_job("discovery_job"):
        scheduler.remove_job("discovery_job")
    scheduler.add_job(
        scheduled_discovery_job,
        trigger="interval",
        hours=interval_hours,
        id="discovery_job",
        replace_existing=True,
    )


app = FastAPI(title="AutoApply API")
api_router = APIRouter(prefix="/api")


@api_router.get("/")
async def root() -> Dict[str, str]:
    return {"message": "AutoApply backend is running"}


@api_router.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok", "time": utc_now_iso()}


@api_router.get("/profile", response_model=UserProfileResponse)
async def read_profile() -> UserProfileResponse:
    profile = await get_profile()
    return UserProfileResponse(**sanitize_doc(profile))


@api_router.post("/profile/upload-cv", response_model=UserProfileResponse)
async def upload_cv(file: UploadFile = File(...)) -> UserProfileResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="File name missing.")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in {".pdf", ".docx"}:
        raise HTTPException(status_code=400, detail="Only PDF and DOCX are supported.")

    content = await file.read()
    if suffix == ".pdf":
        resume_text = extract_pdf_text(content)
    else:
        resume_text = extract_docx_text(content)

    if not resume_text.strip():
        raise HTTPException(status_code=400, detail="Could not extract text from uploaded file.")

    parsed_profile = await parse_resume_with_ai(resume_text)
    now = utc_now_iso()
    profile_doc = {
        "id": str(uuid.uuid4()),
        "user_id": DEFAULT_USER_ID,
        "filename": file.filename,
        "resume_text": resume_text,
        "parsed": parsed_profile,
        "updated_at": now,
    }
    await db.user_profiles.update_one({"user_id": DEFAULT_USER_ID}, {"$set": profile_doc}, upsert=True)

    await run_job_discovery()
    return UserProfileResponse(**profile_doc)


@api_router.get("/preferences")
async def read_preferences() -> Dict[str, Any]:
    return await get_preferences()


@api_router.put("/preferences")
async def update_preferences(payload: PreferencePayload) -> Dict[str, Any]:
    doc = payload.model_dump()
    doc.update({"id": str(uuid.uuid4()), "user_id": DEFAULT_USER_ID, "updated_at": utc_now_iso()})
    await db.preferences.update_one({"user_id": DEFAULT_USER_ID}, {"$set": doc}, upsert=True)
    return doc


@api_router.get("/settings")
async def read_settings() -> Dict[str, Any]:
    return await get_settings()


@api_router.put("/settings")
async def update_settings(payload: SettingsPayload) -> Dict[str, Any]:
    doc = payload.model_dump()
    doc.update({"id": str(uuid.uuid4()), "user_id": DEFAULT_USER_ID, "updated_at": utc_now_iso()})
    await db.settings.update_one({"user_id": DEFAULT_USER_ID}, {"$set": doc}, upsert=True)
    await refresh_scheduler()
    return doc


@api_router.post("/jobs/discover")
async def discover_jobs() -> Dict[str, Any]:
    return await run_job_discovery()


@api_router.get("/jobs")
async def list_jobs(min_score: int = 0, source: str = "") -> List[Dict[str, Any]]:
    query: Dict[str, Any] = {"user_id": DEFAULT_USER_ID, "match_score": {"$gte": min_score}}
    if source:
        query["source"] = source
    jobs = await db.jobs.find(query, {"_id": 0}).sort("match_score", -1).to_list(500)
    return jobs


@api_router.get("/jobs/{job_id}")
async def job_detail(job_id: str) -> Dict[str, Any]:
    job = await db.jobs.find_one({"id": job_id, "user_id": DEFAULT_USER_ID}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    latest_doc = await db.documents.find_one(
        {"job_id": job_id, "user_id": DEFAULT_USER_ID},
        {"_id": 0},
        sort=[("created_at", -1)],
    )
    return {"job": job, "latest_document": latest_doc}


@api_router.post("/jobs/{job_id}/generate-documents")
async def generate_documents(job_id: str) -> Dict[str, Any]:
    return await generate_documents_for_job(job_id)


@api_router.get("/documents/{document_id}/download/{doc_type}")
async def download_document(document_id: str, doc_type: Literal["resume", "cover"]) -> FileResponse:
    document = await db.documents.find_one({"id": document_id, "user_id": DEFAULT_USER_ID}, {"_id": 0})
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    path = document["resume_pdf_path"] if doc_type == "resume" else document["cover_pdf_path"]
    if not Path(path).exists():
        raise HTTPException(status_code=404, detail="PDF file missing")

    return FileResponse(path, media_type="application/pdf", filename=f"{doc_type}_{document_id}.pdf")


@api_router.post("/applications/queue/{job_id}")
async def queue_job_application(job_id: str) -> Dict[str, Any]:
    job = await db.jobs.find_one({"id": job_id, "user_id": DEFAULT_USER_ID}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    application = await store_application_if_missing(job)
    await queue_application(application["id"], job_id)
    return {"queued": True, "application_id": application["id"], "job_id": job_id}


@api_router.post("/auto-apply/run")
async def run_auto_apply(fast_mode: bool = True) -> Dict[str, Any]:
    return await process_queue(max_items=10, fast_mode=fast_mode)


@api_router.get("/applications")
async def list_applications() -> List[Dict[str, Any]]:
    applications = await db.applications.find({"user_id": DEFAULT_USER_ID}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return applications


@api_router.get("/applications/kanban")
async def applications_kanban() -> Dict[str, List[Dict[str, Any]]]:
    applications = await db.applications.find({"user_id": DEFAULT_USER_ID}, {"_id": 0}).to_list(1000)
    by_status: Dict[str, List[Dict[str, Any]]] = {status: [] for status in KANBAN_STATUSES}
    for app_doc in applications:
        status = app_doc.get("status", "Discovered")
        by_status.setdefault(status, []).append(app_doc)
    return by_status


@api_router.patch("/applications/{application_id}/status")
async def update_application_status(application_id: str, payload: ApplicationStatusUpdate) -> Dict[str, Any]:
    result = await db.applications.update_one(
        {"id": application_id, "user_id": DEFAULT_USER_ID},
        {"$set": {"status": payload.status, "updated_at": utc_now_iso()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Application not found")
    updated = await db.applications.find_one({"id": application_id, "user_id": DEFAULT_USER_ID}, {"_id": 0})
    return updated or {}


@api_router.get("/dashboard/metrics")
async def dashboard_metrics() -> Dict[str, Any]:
    apps = await db.applications.find({"user_id": DEFAULT_USER_ID}, {"_id": 0}).to_list(1000)
    jobs = await db.jobs.find({"user_id": DEFAULT_USER_ID}, {"_id": 0}).to_list(2000)
    attempts = await db.application_attempts.find({}, {"_id": 0}).to_list(2000)

    total_applied = len([a for a in apps if a.get("status") in {"Applied", "Under Review", "Interview Scheduled", "Offer Received"}])
    responses = len([a for a in apps if a.get("status") in {"Under Review", "Interview Scheduled", "Offer Received"}])
    interviews = len([a for a in apps if a.get("status") in {"Interview Scheduled", "Offer Received"}])

    response_rate = round((responses / total_applied) * 100, 2) if total_applied else 0
    interview_rate = round((interviews / total_applied) * 100, 2) if total_applied else 0
    avg_match = round(sum([j.get("match_score", 0) for j in jobs]) / len(jobs), 2) if jobs else 0

    source_breakdown: Dict[str, int] = {}
    for app_doc in apps:
        src = app_doc.get("source", "unknown")
        source_breakdown[src] = source_breakdown.get(src, 0) + 1

    status_breakdown: Dict[str, int] = {}
    for app_doc in apps:
        st = app_doc.get("status", "Discovered")
        status_breakdown[st] = status_breakdown.get(st, 0) + 1

    by_day: Dict[str, int] = {}
    for attempt in attempts:
        stamp = attempt.get("timestamp", "")
        day = stamp[:10] if stamp else ""
        if day:
            by_day[day] = by_day.get(day, 0) + 1

    sorted_days = sorted(by_day.items())[-90:]
    timeline = [{"date": day, "applications": count} for day, count in sorted_days]

    return {
        "kpis": {
            "total_applied": total_applied,
            "response_rate": response_rate,
            "interview_rate": interview_rate,
            "active_applications": len([a for a in apps if a.get("status") not in {"Rejected", "Withdrawn"}]),
            "avg_autoapply_score": avg_match,
            "applications_total": len(apps),
        },
        "source_breakdown": [{"source": k, "count": v} for k, v in source_breakdown.items()],
        "status_breakdown": [{"status": k, "count": v} for k, v in status_breakdown.items()],
        "applications_over_time": timeline,
    }


app.include_router(api_router)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@app.on_event("startup")
async def startup_event() -> None:
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    PROOF_DIR.mkdir(parents=True, exist_ok=True)

    await db.jobs.create_index([("user_id", 1), ("source", 1), ("external_id", 1)], unique=True)
    await db.applications.create_index([("user_id", 1), ("job_id", 1)], unique=True)
    await db.application_queue.create_index([("application_id", 1), ("status", 1)])

    await get_profile()
    await get_preferences()
    await get_settings()

    if not scheduler.running:
        scheduler.add_job(scheduled_queue_job, trigger="interval", minutes=2, id="queue_job", replace_existing=True)
        await refresh_scheduler()
        scheduler.start()


@app.on_event("shutdown")
async def shutdown_db_client() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
    client.close()