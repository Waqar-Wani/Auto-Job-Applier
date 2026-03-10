from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class ATSSourceConfig(BaseModel):
    source: Literal["greenhouse", "lever", "ashby", "workable", "recruitee", "smartrecruiters"]
    companies: List[str] = Field(default_factory=list)
    enabled: bool = True


class JobDocument(BaseModel):
    id: str
    user_id: str
    source: str
    external_id: str
    title: str
    company: str
    location: str
    remote_status: str = "unknown"
    description: str = ""
    job_type: str = ""
    salary_min: int = 0
    salary_max: int = 0
    salary_currency: str = ""
    salary_text: str = ""
    apply_url: str = ""
    match_score: int = 0
    matched_skills: List[str] = Field(default_factory=list)
    score_breakdown: Dict[str, Any] = Field(default_factory=dict)
    discovered_at: str = ""
    updated_at: str = ""
    raw: Dict[str, Any] = Field(default_factory=dict)


class AutoApplyQueueItem(BaseModel):
    id: str
    application_id: str
    job_id: str
    status: Literal["pending", "retrying", "done", "failed"] = "pending"
    retry_count: int = 0
    next_attempt_at: str = ""
    created_at: str = ""
    updated_at: str = ""


class DiscoveryRunLog(BaseModel):
    id: str
    user_id: str
    started_at: str
    finished_at: str
    fetched_total: int = 0
    deduped_total: int = 0
    created_total: int = 0
    updated_total: int = 0
    queued_total: int = 0
    source_breakdown: Dict[str, int] = Field(default_factory=dict)
    errors: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

