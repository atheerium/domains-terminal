"""Domain data models — Pydantic.

Purpose: Central data contract for all modules. Every module in the project
exchanges data using these models. No raw dicts across module boundaries.

Input: Config values, DB rows, provider API responses → Domain / Score / etc.
Output: Serialized JSON, DB writes, CLI output
Dependencies: pydantic (stdlib): BaseModel, Field
Side effects: None — pure data classes"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Domain(BaseModel):
    domain: str
    source: str = ""
    tld: str = ""
    length: int = 0
    word_count: int = 0
    contains_numbers: bool = False
    seen_at: Optional[str] = None
    drop_at: Optional[str] = None
    current_price: Optional[float] = None
    end_time: Optional[str] = None
    auction_id: Optional[str] = None
    is_available: bool = True
    status: str = "active"
    raw_data: Optional[str] = None
    updated_at: Optional[str] = None


class Metric(BaseModel):
    id: Optional[int] = None
    domain: str
    metric_type: str  # e.g. "archive_year", "backlinks", "domain_authority"
    value: str
    updated_at: Optional[str] = None


class Score(BaseModel):
    id: Optional[int] = None
    domain: str
    rule: str
    score: int  # 0-100
    confidence: float = 0.0
    updated_at: Optional[str] = None


class Appraisal(BaseModel):
    id: Optional[int] = None
    domain: str
    retail_min: Optional[int] = None
    retail_max: Optional[int] = None
    wholesale_min: Optional[int] = None
    wholesale_max: Optional[int] = None
    buy_recommendation: bool = False
    confidence: float = 0.0
    reason: str = ""
    updated_at: Optional[str] = None


class Sale(BaseModel):
    id: Optional[int] = None
    keyword: str
    domain: Optional[str] = None
    sale_price: int
    sale_date: Optional[str] = None
    venue: str = ""
    created_at: Optional[str] = None


class Event(BaseModel):
    id: Optional[int] = None
    domain: str
    event_type: str
    details: Optional[str] = None
    created_at: Optional[str] = None


class PipelineResult(BaseModel):
    status: str = "ok"
    command: str = ""
    data: List[Dict[str, Any]] = Field(default_factory=list)
    meta: Dict[str, Any] = Field(default_factory=dict)

    def json_output(self) -> str:
        import json
        return json.dumps(self.model_dump(), indent=2, default=str)
