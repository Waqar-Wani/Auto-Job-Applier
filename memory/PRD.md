# PRD — AutoApply Phase 1

## Original Problem Statement
Build AutoApply as an AI-powered automated job application platform with resume upload/parsing, job discovery, AI tailoring, auto-apply, tracking ATS board, analytics dashboard, and settings controls. User confirmed phased delivery; Phase 1 only; Emergent universal key for Claude model claude-sonnet-4-20250514; job sources Remotive + Adzuna in v1; real automation queue with retries.

## Architecture Decisions
- Runtime kept on provided stack: React (CRA) + FastAPI + MongoDB template for compatibility in current environment.
- AI generation via emergentintegrations LlmChat using EMERGENT_LLM_KEY and requested Claude model name.
- Source abstraction implemented in backend: separate fetchers for Remotive and Adzuna; discovery pipeline combines/dedupes/scores.
- Auto-apply queue implemented server-side with retry backoff (5m/15m/45m), attempt logs, and proof artifacts.
- Scheduled jobs via APScheduler for discovery interval and queue processing.

## What is Implemented (Phase 1)
- CV upload (PDF/DOCX), text extraction, AI profile parsing, structured profile storage.
- Preference module (target titles, location, salary, remote mode, etc.) and settings module (Adzuna/Resend creds, threshold, limits, toggles).
- Job discovery endpoint and scheduler (Remotive live, Adzuna optional via credentials), dedupe, scoring, metadata persistence.
- Job detail flow with AI-tailored resume + AI cover letter generation; both exported to downloadable PDFs.
- Auto-apply: queue insert, process runner, daily limit enforcement, business-hours option, randomized delays in scheduler path, retry policy, attempt logging.
- ATS Kanban statuses with drag/drop + select status updates.
- Dashboard KPIs and charts (timeline/source/status) and recent activity panel.
- Premium dark responsive UI with sidebar navigation across Dashboard, Jobs, Job Detail, Applications, Profile/CV, Settings.
- Added defensive frontend error states for key page loads and improved Kanban scroll usability.

## Prioritized Backlog
### P0 (Next critical)
- Replace placeholder direct-apply proof with true Playwright form-fill automation and screenshot capture for supported sites.
- Add secure auth + per-user isolation (current Phase 1 uses single default-user profile).
- Add Adzuna credential validation UX and connection-status checks.

### P1 (High value)
- Email response parsing (Gmail/Outlook integration) and auto status transitions (Under Review/Interview).
- Follow-up reminders and recruiter/contact enrichment fields in UI edits.
- More robust ATS keyword extraction + explainable match scoring panel.

### P2 (Enhancements)
- LinkedIn/Indeed/Glassdoor source plugins (Phase 2 scope).
- Multi-template visual PDF rendering with richer layout controls.
- Advanced analytics: cohort/source conversion trends and weekly AI insights panel.

## Next Tasks
- Confirm Phase 1 acceptance with user and proceed to Phase 2 integrations/automation depth.
