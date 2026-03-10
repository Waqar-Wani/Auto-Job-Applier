from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


RemoteStatus = Literal["remote", "hybrid", "onsite", "unknown"]


class NormalizedSalary(BaseModel):
    min: int = 0
    max: int = 0
    currency: str = ""
    text: str = ""


class NormalizedJob(BaseModel):
    source: str
    external_id: str
    job_title: str
    company: str
    location: str
    remote_status: RemoteStatus = "unknown"
    salary: NormalizedSalary = Field(default_factory=NormalizedSalary)
    description: str = ""
    application_url: str = ""
    job_type: str = ""
    industry: str = ""
    raw: Dict[str, Any] = Field(default_factory=dict)

    def to_legacy_schema(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "external_id": self.external_id,
            "title": self.job_title,
            "company": self.company,
            "location": self.location,
            "remote_status": self.remote_status,
            "description": self.description,
            "job_type": self.job_type,
            "salary_min": self.salary.min,
            "salary_max": self.salary.max,
            "salary_currency": self.salary.currency,
            "salary_text": self.salary.text,
            "industry": self.industry,
            "apply_url": self.application_url,
            "application_email": "",
            "company_size": "",
            "raw": self.raw,
        }


class ATSSettings(BaseModel):
    enabled: bool = True
    company_sources: Dict[str, List[str]] = Field(
        default_factory=lambda: {
            "greenhouse": [],
            "lever": [],
            "ashby": [],
            "workable": [],
            "recruitee": [],
            "smartrecruiters": [],
        }
    )
    request_timeout_seconds: int = 30
    max_companies_per_source: int = 200
    concurrency_limit: int = 12


class DiscoveryRunResult(BaseModel):
    fetched: int = 0
    filtered_out: int = 0
    returned: int = 0
    errors: List[str] = Field(default_factory=list)
    per_source_counts: Dict[str, int] = Field(default_factory=dict)
    jobs: List[Dict[str, Any]] = Field(default_factory=list)

