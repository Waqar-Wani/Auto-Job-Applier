# AutoApply — Phase 1 (Implemented)

## What is included in this build
- CV upload (PDF/DOCX) with AI parsing into structured profile (skills, summary, etc.)
- Preferences + settings management (score threshold, daily limits, auto-apply toggle, Adzuna + Resend credentials)
- Job discovery engine with Remotive + Adzuna integration and deduplication
- AI job scoring and match % per job
- Job detail page with AI-tailored resume + AI cover letter generation
- PDF export for tailored resume and cover letter
- Auto-apply queue with retries (5/15/45 min), attempt logs, and proof artifacts
- Kanban application tracking board (Discovered → Applied → ...)
- Dashboard with KPIs and source/status/time charts

## Added in this update (Focused Features)
- **Playwright Auto-Apply:** direct apply flow now uses headless Playwright auto-fill, uploads tailored resume PDF to file inputs, and stores confirmation screenshot path when submission succeeds.
- **Gmail Response Parsing:** Google OAuth connection from Settings, inbox polling, Claude email classification (`rejection`/`interview`/`offer`/`no-match`), and automatic Kanban status updates with summary notes.
- **3-Day Follow-Up Drafts:** auto-generates one follow-up draft per application after 3 days without response, shows draft in Application Detail panel, and supports one-click Gmail send.

## Assumptions made
- Implemented in the provided React + FastAPI + MongoDB runtime template for compatibility with this environment.
- A single default user flow is used (no auth module in Phase 1).
- Remotive is active by default; Adzuna jobs activate after user provides app_id/app_key in Settings.
- Email auto-apply requires user-provided Resend API key and sender email in Settings.
- Gmail connected happy-path requires user-provided Google OAuth client credentials in Settings.
- Direct-apply fallback records proof as a generated artifact when possible.

## Environment notes
- Backend uses `EMERGENT_LLM_KEY` for Claude calls through `emergentintegrations`.
- Backend URL is read from `frontend/.env` (`REACT_APP_BACKEND_URL`).
- MongoDB URL is read from `backend/.env` (`MONGO_URL`).

## Core API endpoints
- `POST /api/profile/upload-cv`
- `GET/PUT /api/preferences`
- `GET/PUT /api/settings`
- `POST /api/jobs/discover`
- `GET /api/jobs`, `GET /api/jobs/{job_id}`
- `POST /api/jobs/{job_id}/generate-documents`
- `GET /api/documents/{document_id}/download/{resume|cover}`
- `POST /api/applications/queue/{job_id}`
- `POST /api/auto-apply/run`
- `GET /api/applications/kanban`
- `PATCH /api/applications/{application_id}/status`
- `GET /api/dashboard/metrics`
