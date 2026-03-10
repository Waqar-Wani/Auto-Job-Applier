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
        jobs = data.get("jobs", []) if isinstance(data, dict) else []
        output: List[NormalizedJob] = []
        for item in jobs:
            title = _text(item.get("title"))
            description = _text(item.get("content"))
            location = _text((item.get("location") or {}).get("name"))
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
                    application_url=_text(item.get("absolute_url")),
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
            salary = NormalizedSalary(
                min=int(comp.get("minValue", 0) or 0),
                max=int(comp.get("maxValue", 0) or 0),
                currency=_text(comp.get("currencyCode")),
                text=_text(comp.get("summary")),
            )
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

