import asyncio
from typing import Any, Dict, List, Tuple

import httpx

from .connectors import CONNECTOR_REGISTRY
from .models import ATSSettings, DiscoveryRunResult, NormalizedJob


def _to_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        return [x.strip() for x in value.split(",") if x.strip()]
    return []


def parse_ats_settings(raw_settings: Dict[str, Any]) -> ATSSettings:
    defaults = ATSSettings()
    merged = defaults.model_dump()
    merged.update({k: v for k, v in (raw_settings or {}).items() if k in merged and k != "company_sources"})

    company_sources = defaults.company_sources.copy()
    raw_company_sources = (raw_settings or {}).get("company_sources", {})
    for source in company_sources.keys():
        company_sources[source] = _to_list(raw_company_sources.get(source, []))
    merged["company_sources"] = company_sources
    return ATSSettings(**merged)


def parse_ats_settings_from_app_settings(settings: Dict[str, Any]) -> ATSSettings:
    ats_settings = parse_ats_settings((settings or {}).get("ats_settings", {}))

    # Backward-compatible shortcut key for app settings payloads.
    company_sources = (settings or {}).get("ats_company_sources", {})
    if isinstance(company_sources, dict):
        merged = ats_settings.model_dump()
        for source in merged["company_sources"].keys():
            if source in company_sources:
                merged["company_sources"][source] = _to_list(company_sources.get(source))
        ats_settings = ATSSettings(**merged)
    return ats_settings


def _remote_matches(job_remote_status: str, remote_pref: str) -> bool:
    pref = (remote_pref or "any").lower()
    status = (job_remote_status or "unknown").lower()
    if pref == "any":
        return True
    if pref == "remote":
        return status == "remote"
    if pref == "hybrid":
        return status in {"hybrid", "remote"}
    if pref == "onsite":
        return status == "onsite"
    return True


def _title_matches(job_title: str, preferred_titles: List[str]) -> bool:
    if not preferred_titles:
        return True
    lowered_job = (job_title or "").lower()
    return any(title.lower() in lowered_job for title in preferred_titles)


def _location_matches(job_location: str, location_preferences: List[str], remote_status: str) -> bool:
    if remote_status == "remote":
        return True
    if not location_preferences:
        return True
    lowered_loc = (job_location or "").lower()
    return any(loc.lower() in lowered_loc for loc in location_preferences if loc)


def _salary_matches(job: NormalizedJob, pref_min: int, pref_max: int) -> bool:
    if not pref_min and not pref_max:
        return True
    salary_low = job.salary.min or job.salary.max
    salary_high = job.salary.max or job.salary.min
    if not salary_low and not salary_high:
        return True
    if pref_max and salary_low > pref_max:
        return False
    if pref_min and salary_high < pref_min:
        return False
    return True


def _normalize_pref_salary(value: Any) -> int:
    amount = int(value or 0)
    if amount <= 0:
        return 0
    # Supports INR-LPA shorthand (for example: 12 means 12 LPA).
    if amount <= 500:
        return amount * 100000
    return amount


def matches_preferences(job: NormalizedJob, preferences: Dict[str, Any]) -> bool:
    preferred_titles = _to_list(preferences.get("target_job_titles", []))
    location_preferences = _to_list(preferences.get("location_preferences", []))
    remote_pref = str(preferences.get("remote_mode", "any"))
    pref_min = _normalize_pref_salary(preferences.get("salary_min", 0))
    pref_max = _normalize_pref_salary(preferences.get("salary_max", 0))

    if not _title_matches(job.job_title, preferred_titles):
        return False
    if not _remote_matches(job.remote_status, remote_pref):
        return False
    if not _location_matches(job.location, location_preferences, job.remote_status):
        return False
    if not _salary_matches(job, pref_min, pref_max):
        return False
    return True


def dedupe_jobs(jobs: List[NormalizedJob]) -> List[NormalizedJob]:
    seen: Dict[str, NormalizedJob] = {}
    for job in jobs:
        key = (
            f"{job.job_title.lower()}::"
            f"{job.company.lower()}::"
            f"{job.location.lower()}::"
            f"{(job.application_url or '').lower()}"
        )
        if key not in seen:
            seen[key] = job
    return list(seen.values())


async def _fetch_one_company(
    source: str,
    company: str,
    connector,
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
) -> Tuple[str, str, List[NormalizedJob], str]:
    async with semaphore:
        try:
            jobs = await connector.fetch_company_jobs(client, company)
            return source, company, jobs, ""
        except Exception as exc:  # noqa: BLE001
            return source, company, [], str(exc)


async def discover_ats_jobs(preferences: Dict[str, Any], settings: Dict[str, Any]) -> DiscoveryRunResult:
    ats_settings = parse_ats_settings_from_app_settings(settings)
    if not ats_settings.enabled:
        return DiscoveryRunResult()

    tasks: List[asyncio.Task] = []
    semaphore = asyncio.Semaphore(max(1, int(ats_settings.concurrency_limit)))
    timeout = httpx.Timeout(max(10, int(ats_settings.request_timeout_seconds)))
    per_source_counts: Dict[str, int] = {}
    errors: List[str] = []
    all_jobs: List[NormalizedJob] = []

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        for source, companies in ats_settings.company_sources.items():
            connector = CONNECTOR_REGISTRY.get(source)
            if connector is None:
                continue
            if not companies:
                continue
            limited_companies = companies[: ats_settings.max_companies_per_source]
            for company in limited_companies:
                tasks.append(
                    asyncio.create_task(_fetch_one_company(source, company, connector, client, semaphore))
                )

        if tasks:
            results = await asyncio.gather(*tasks)
        else:
            results = []

    for source, company, jobs, err in results:
        if err:
            errors.append(f"{source}:{company} -> {err[:180]}")
            continue
        all_jobs.extend(jobs)
        per_source_counts[source] = per_source_counts.get(source, 0) + len(jobs)

    deduped = dedupe_jobs(all_jobs)
    filtered = [job for job in deduped if matches_preferences(job, preferences)]
    return DiscoveryRunResult(
        fetched=len(all_jobs),
        filtered_out=max(0, len(deduped) - len(filtered)),
        returned=len(filtered),
        errors=errors,
        per_source_counts=per_source_counts,
        jobs=[job.to_legacy_schema() for job in filtered],
    )
