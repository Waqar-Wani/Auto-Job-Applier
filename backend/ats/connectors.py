import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List

import httpx

from .models import NormalizedJob, NormalizedSalary


def _text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    return str(value)


def _is_http_url(value: str) -> bool:
    candidate = (value or "").strip().lower()
    return candidate.startswith("http://") or candidate.startswith("https://")


def infer_remote_status(location: str, title: str, description: str) -> str:
    blob = f"{location} {title} {description}".lower()
    if "hybrid" in blob:
        return "hybrid"
    if "remote" in blob or "work from home" in blob or "wfh" in blob:
        return "remote"
    if location.strip():
        return "onsite"
    return "unknown"


def _extract_salary_from_text(text: str) -> NormalizedSalary:
    if not text:
        return NormalizedSalary()
    lowered = text.lower()
    currency = ""
    if any(t in lowered for t in ["usd", "us$", "$"]):
        currency = "USD"
    elif any(t in lowered for t in ["eur", "€"]):
        currency = "EUR"
    elif any(t in lowered for t in ["gbp", "£"]):
        currency = "GBP"
    elif any(t in lowered for t in ["inr", "₹", "lpa", "lakh"]):
        currency = "INR"

    matches = re.findall(r"(\d+(?:[.,]\d+)?)\s*([kKmM]?)", text)
    values: List[int] = []
    for number, suffix in matches:
        try:
            val = float(number.replace(",", ""))
        except ValueError:
            continue
        if suffix.lower() == "k":
            val *= 1000
        elif suffix.lower() == "m":
            val *= 1000000
        values.append(int(val))
    if not values:
        return NormalizedSalary(currency=currency, text=text)
    return NormalizedSalary(min=min(values), max=max(values), currency=currency, text=text)


class ATSConnector(ABC):
    source_name: str

    @abstractmethod
    async def fetch_company_jobs(self, client: httpx.AsyncClient, company: str) -> List[NormalizedJob]:
        raise NotImplementedError


class GreenhouseConnector(ATSConnector):
    source_name = "greenhouse"

    async def fetch_company_jobs(self, client: httpx.AsyncClient, company: str) -> List[NormalizedJob]:
        url = f"https://api.greenhouse.io/v1/boards/{company}/jobs"
        response = await client.get(url, params={"content": "true"})
        response.raise_for_status()
        data = response.json()
        jobs: List[Dict[str, Any]] = []
        if isinstance(data, dict):
            if isinstance(data.get("jobs"), list):
                jobs.extend([item for item in data.get("jobs", []) if isinstance(item, dict)])
            departments = data.get("departments", [])
            if isinstance(departments, list):
                for dept in departments:
                    if not isinstance(dept, dict):
                        continue
                    dept_jobs = dept.get("jobs", [])
                    if isinstance(dept_jobs, list):
                        jobs.extend([item for item in dept_jobs if isinstance(item, dict)])

        deduped_jobs: Dict[str, Dict[str, Any]] = {}
        for item in jobs:
            dedupe_key = _text(item.get("id") or item.get("internal_job_id") or item.get("absolute_url"))
            if dedupe_key and dedupe_key not in deduped_jobs:
                deduped_jobs[dedupe_key] = item

        output: List[NormalizedJob] = []
        for item in deduped_jobs.values():
            title = _text(item.get("title"))
            description = _text(item.get("content"))
            metadata_locations: List[str] = []
            for meta in item.get("metadata", []) if isinstance(item.get("metadata"), list) else []:
                if not isinstance(meta, dict):
                    continue
                if _text(meta.get("name")).strip().lower() != "job posting location":
                    continue
                meta_value = meta.get("value")
                if isinstance(meta_value, list):
                    metadata_locations.extend([_text(loc) for loc in meta_value if _text(loc).strip()])
                elif _text(meta_value).strip():
                    metadata_locations.append(_text(meta_value).strip())

            fallback_location = _text((item.get("location") or {}).get("name"))
            if metadata_locations:
                location = " | ".join(dict.fromkeys(metadata_locations))
            else:
                location = fallback_location

            job_id = _text(item.get("id"))
            absolute_url = _text(item.get("absolute_url")).strip()
            if not _is_http_url(absolute_url):
                # Fallback pattern from Greenhouse board URLs.
                if not job_id:
                    continue
                absolute_url = f"https://boards.greenhouse.io/{company}/jobs/{job_id}"

            output.append(
                NormalizedJob(
                    source=self.source_name,
                    external_id=job_id or _text(item.get("internal_job_id")),
                    job_title=title,
                    company=_text(item.get("company_name")) or company,
                    location=location,
                    remote_status=infer_remote_status(location, title, description),
                    salary=_extract_salary_from_text(description),
                    description=description,
                    application_url=absolute_url,
                    raw=item if isinstance(item, dict) else {},
                )
            )
        return output


class LeverConnector(ATSConnector):
    source_name = "lever"

    async def fetch_company_jobs(self, client: httpx.AsyncClient, company: str) -> List[NormalizedJob]:
        url = f"https://api.lever.co/v0/postings/{company}"
        response = await client.get(url, params={"mode": "json"})
        response.raise_for_status()
        data = response.json()
        jobs = data if isinstance(data, list) else []
        output: List[NormalizedJob] = []
        for item in jobs:
            categories = item.get("categories") or {}
            title = _text(item.get("text"))
            location = _text(categories.get("location"))
            description = _text(item.get("descriptionPlain")) or _text(item.get("description"))
            output.append(
                NormalizedJob(
                    source=self.source_name,
                    external_id=_text(item.get("id")),
                    job_title=title,
                    company=company,
                    location=location,
                    remote_status=infer_remote_status(location, title, description),
                    salary=_extract_salary_from_text(description),
                    description=description,
                    application_url=_text(item.get("hostedUrl") or item.get("applyUrl")),
                    job_type=_text(categories.get("commitment")),
                    raw=item if isinstance(item, dict) else {},
                )
            )
        return output


class AshbyConnector(ATSConnector):
    source_name = "ashby"

    async def fetch_company_jobs(self, client: httpx.AsyncClient, company: str) -> List[NormalizedJob]:
        url = f"https://api.ashbyhq.com/posting-api/job-board/{company}"
        response = await client.get(url, params={"includeCompensation": "true"})
        response.raise_for_status()
        data = response.json()
        jobs = data.get("jobs", []) if isinstance(data, dict) else []
        output: List[NormalizedJob] = []
        for item in jobs:
            title = _text(item.get("title"))
            description = _text(item.get("descriptionHtml")) or _text(item.get("description"))
            location = _text((item.get("location") or {}).get("locationName"))
            comp = item.get("compensation") or {}
            salary = NormalizedSalary()
            if isinstance(comp, dict):
                salary = NormalizedSalary(
                    min=int(comp.get("minValue", 0) or 0),
                    max=int(comp.get("maxValue", 0) or 0),
                    currency=_text(comp.get("currencyCode")),
                    text=_text(comp.get("summary")),
                )
            elif isinstance(comp, list) and comp:
                first = comp[0] if isinstance(comp[0], dict) else {}
                salary = NormalizedSalary(
                    min=int(first.get("minValue", 0) or 0),
                    max=int(first.get("maxValue", 0) or 0),
                    currency=_text(first.get("currencyCode")),
                    text=_text(first.get("summary")),
                )
            elif isinstance(comp, str):
                salary = _extract_salary_from_text(comp)
            if not salary.min and not salary.max:
                salary = _extract_salary_from_text(description)
            output.append(
                NormalizedJob(
                    source=self.source_name,
                    external_id=_text(item.get("id")),
                    job_title=title,
                    company=company,
                    location=location,
                    remote_status=infer_remote_status(location, title, description),
                    salary=salary,
                    description=description,
                    application_url=_text(item.get("jobUrl") or item.get("applyUrl")),
                    job_type=_text(item.get("employmentType")),
                    raw=item if isinstance(item, dict) else {},
                )
            )
        return output


class WorkableConnector(ATSConnector):
    source_name = "workable"

    async def fetch_company_jobs(self, client: httpx.AsyncClient, company: str) -> List[NormalizedJob]:
        url = f"https://apply.workable.com/api/v1/widget/accounts/{company}"
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()
        jobs = data.get("jobs", []) if isinstance(data, dict) else []
        output: List[NormalizedJob] = []
        for item in jobs:
            title = _text(item.get("title"))
            description = _text(item.get("shortcode")) + " " + _text(item.get("description"))
            location = _text((item.get("location") or {}).get("location_str") or item.get("location"))
            output.append(
                NormalizedJob(
                    source=self.source_name,
                    external_id=_text(item.get("shortcode") or item.get("id")),
                    job_title=title,
                    company=company,
                    location=location,
                    remote_status=infer_remote_status(location, title, description),
                    salary=_extract_salary_from_text(description),
                    description=description.strip(),
                    application_url=_text(item.get("url")),
                    job_type=_text(item.get("employment_type")),
                    raw=item if isinstance(item, dict) else {},
                )
            )
        return output


class RecruiteeConnector(ATSConnector):
    source_name = "recruitee"

    async def fetch_company_jobs(self, client: httpx.AsyncClient, company: str) -> List[NormalizedJob]:
        url = f"https://{company}.recruitee.com/api/offers"
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()
        jobs = data.get("offers", []) if isinstance(data, dict) else []
        output: List[NormalizedJob] = []
        for item in jobs:
            title = _text(item.get("title"))
            description = _text(item.get("description"))
            location = _text((item.get("location") or {}).get("name"))
            careers_url = _text(item.get("careers_url"))
            output.append(
                NormalizedJob(
                    source=self.source_name,
                    external_id=_text(item.get("id")),
                    job_title=title,
                    company=_text(item.get("company_name") or company),
                    location=location,
                    remote_status=infer_remote_status(location, title, description),
                    salary=_extract_salary_from_text(description),
                    description=description,
                    application_url=careers_url,
                    job_type=_text(item.get("employment_type_code")),
                    raw=item if isinstance(item, dict) else {},
                )
            )
        return output


class SmartRecruitersConnector(ATSConnector):
    source_name = "smartrecruiters"

    async def fetch_company_jobs(self, client: httpx.AsyncClient, company: str) -> List[NormalizedJob]:
        url = f"https://api.smartrecruiters.com/v1/companies/{company}/postings"
        response = await client.get(url, params={"limit": 100, "offset": 0})
        response.raise_for_status()
        data = response.json()
        jobs = data.get("content", []) if isinstance(data, dict) else []
        output: List[NormalizedJob] = []
        for item in jobs:
            title = _text(item.get("name"))
            location_obj = item.get("location") or {}
            location = ", ".join(
                [part for part in [_text(location_obj.get("city")), _text(location_obj.get("country"))] if part]
            )
            description = _text(item.get("jobAd", {}).get("sections", {}).get("jobDescription", {}).get("text"))
            output.append(
                NormalizedJob(
                    source=self.source_name,
                    external_id=_text(item.get("id")),
                    job_title=title,
                    company=company,
                    location=location,
                    remote_status=infer_remote_status(location, title, description),
                    salary=_extract_salary_from_text(description),
                    description=description,
                    application_url=_text(item.get("ref") or item.get("applyUrl")),
                    job_type=_text(item.get("typeOfEmployment", {}).get("label")),
                    raw=item if isinstance(item, dict) else {},
                )
            )
        return output


CONNECTOR_REGISTRY: Dict[str, ATSConnector] = {
    "greenhouse": GreenhouseConnector(),
    "lever": LeverConnector(),
    "ashby": AshbyConnector(),
    "workable": WorkableConnector(),
    "recruitee": RecruiteeConnector(),
    "smartrecruiters": SmartRecruitersConnector(),
}
