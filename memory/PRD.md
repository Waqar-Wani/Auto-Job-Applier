# PRD — AutoApply Phase 1 + Focused Enhancements

## Original Problem Statement
Build AutoApply as an AI-powered automated job application platform with resume upload/parsing, job discovery, AI tailoring, auto-apply, ATS tracking board, analytics dashboard, and settings controls. Then add exactly 3 focused features only: Playwright auto-apply, Gmail response parsing, and 3-day follow-up drafts.

## Architecture Decisions
- Runtime: existing React + FastAPI + MongoDB template (single personal user, no auth flows).
- AI: `emergentintegrations` with `EMERGENT_LLM_KEY` and Claude `claude-sonnet-4-20250514` for parsing, tailoring, classification, and follow-up drafting.
- Job source abstraction: Remotive + Adzuna connectors with dedupe/scoring.
- Automation: APScheduler jobs for discovery, queue processing, Gmail polling (2h), and due follow-up generation.
- Playwright: headless Chromium for direct-apply form fill and proof screenshot capture.

## What is Implemented
- Phase 1 baseline (already complete): CV parsing, preferences/settings, discovery/scoring, tailored docs + PDFs, queue, ATS board, analytics dashboard.
- **Feature 1 (Playwright Auto-Apply):**
  - Direct-apply path uses Playwright to auto-fill common form fields from saved profile.
  - Uploads tailored resume PDF to file inputs when present.
  - Detects confirmation content and captures screenshot proof.
  - Retry behavior is enforced by queue with max 3 attempts; errors logged to application attempts.
  - Screenshot path stored on application record and exposed in application detail API/UI.
- **Feature 2 (Email Response Parsing):**
  - Gmail OAuth controls added to Settings (client ID/secret + connect).
  - Poll endpoint plus scheduled polling every 2 hours.
  - Claude classification labels: rejection/interview/offer/no-match.
  - Matching logic updates Kanban status and stores email summary note on application card.
- **Feature 3 (3-Day Follow-Up Drafts):**
  - Auto-generates a follow-up draft after 3 days without response for applied jobs.
  - Max one follow-up per application.
  - Draft shown in Application Detail panel.
  - One-click Gmail send endpoint integrated (requires connected Gmail OAuth).

## Prioritized Backlog
### P0
- Validate Gmail connected happy-path with real Google OAuth credentials and real inbox data in this environment.
- Expand Playwright submit-targeting heuristics for more external ATS variants.

### P1
- Improve email-to-application matching confidence using stronger entity extraction (company aliases, recruiter signatures).
- Add clearer in-app state for “awaiting Gmail connection” versus “connected and polling active”.

### P2
- Add additional job sources in next phase (LinkedIn/Indeed/Glassdoor).

## Next Tasks
- Await your verification on these 3 focused features; then we proceed only with bug fixes or the next scoped request.
