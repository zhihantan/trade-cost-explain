"""Pydantic request / response models (mirrored by frontend/src/api/types.ts)."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

Status = Literal["draft", "in_review", "approved", "rejected"]
JobStatus = Literal["queued", "running", "succeeded", "failed"]

COMPARISON_RE = re.compile(r"^(MOM_\d{4}-\d{2}|QOQ_FY\d{4}Q[1-4])$")
SLICE_RE = re.compile(r"^(APAC|ED_EXCH_CLR|REST|BUS:[A-Z0-9_]{2,12}|DESK:[A-Z0-9_]{2,12})$")
FIGURE_RE = re.compile(r"^[A-Za-z0-9_:|.\-&() ,/]{3,200}$")  # CAT:<cost_category> keys carry spaces, & and ()


def check_comparison(v: str) -> str:
    if not COMPARISON_RE.match(v):
        raise ValueError("invalid comparison id")
    return v


def check_slice(v: str) -> str:
    if not SLICE_RE.match(v):
        raise ValueError("invalid slice key")
    return v


# ---------- flux ----------
class Comparison(BaseModel):
    comparison_id: str
    comparison_type: str
    period_p0: str
    period_p1: str
    p0_label: str
    p1_label: str
    sort_order: int = 0
    is_default: bool = False
    comparison_label: Optional[str] = None


class Effect(BaseModel):
    effect: str
    label: str
    amount: float
    order: int
    flux_class: str


class FluxTotals(BaseModel):
    p0: float
    p1: float
    p1_cc: float
    flux: float
    flux_pct: Optional[float]


class FluxRow(BaseModel):
    key: str
    p0: float
    p1: float
    volume: float
    mix: float
    rate: float
    fx: float
    fails: float
    fixed: float
    timing: float
    unexplained: float
    flux: float


class DataSource(BaseModel):
    table: str
    mode: Literal["live", "fixtures"]
    delta_version: Optional[int] = None
    as_of_ts: Optional[str] = None
    snapshot_ref: Optional[str] = None  # pipeline update id for materialized views (no Delta history)
    note: Optional[str] = None


class FluxResponse(BaseModel):
    comparison: Comparison
    slice_key: str
    slice_label: str
    breakdown: str
    totals: FluxTotals
    effects: list[Effect]
    classes: dict[str, float]
    rows: list[FluxRow]
    source: DataSource


class SliceOption(BaseModel):
    key: str
    label: str
    group: str


# ---------- figures ----------
class Figure(BaseModel):
    figure_key: str
    comparison_id: Optional[str] = None
    scope_key: Optional[str] = None
    scope_label: Optional[str] = None
    metric: Optional[str] = None
    metric_label: Optional[str] = None
    label: str
    value: Optional[float]
    unit: str = "USD"
    source_table: str
    filter: str = ""
    description: Optional[str] = None
    delta_version: Optional[int] = None
    as_of_ts: Optional[str] = None
    snapshot_ref: Optional[str] = None
    mode: Literal["live", "fixtures", "snapshot"] = "live"


# ---------- commentary ----------
class CommentaryCreate(BaseModel):
    period: str
    slice_key: str
    title: Optional[str] = Field(None, max_length=200)

    _p = field_validator("period")(lambda cls, v: check_comparison(v))
    _s = field_validator("slice_key")(lambda cls, v: check_slice(v))


class CommentaryUpdate(BaseModel):
    version: int = Field(..., ge=1)
    edited_text: str = Field(..., max_length=20000)
    title: Optional[str] = Field(None, max_length=200)


class VersionedAction(BaseModel):
    version: int = Field(..., ge=1)
    note: Optional[str] = Field(None, max_length=2000)


class RejectAction(VersionedAction):
    note: str = Field(..., min_length=3, max_length=2000)


class CommentaryFigure(BaseModel):
    figure_key: str
    label: Optional[str]
    value: Optional[float]
    unit: Optional[str]
    source_table: Optional[str]
    filter: Optional[str]
    delta_version: Optional[int]
    as_of_ts: Optional[datetime]
    snapshot_ref: Optional[str] = None


class Commentary(BaseModel):
    id: UUID
    period: str
    slice_key: str
    title: str
    version: int
    status: Status
    draft_text: Optional[str]
    edited_text: Optional[str]
    author_email: str
    last_edited_by: Optional[str]
    submitted_by: Optional[str]
    decided_by: Optional[str]
    decision_note: Optional[str]
    drafted_by_model: Optional[str]
    created_at: datetime
    updated_at: datetime
    submitted_at: Optional[datetime]
    decided_at: Optional[datetime]


class CommentaryDetail(Commentary):
    figures: list[CommentaryFigure] = []
    permissions: dict[str, bool] = {}
    blockers: dict[str, str] = {}


class DraftAccepted(BaseModel):
    job_id: UUID
    status: JobStatus


class Job(BaseModel):
    job_id: UUID
    commentary_id: UUID
    status: JobStatus
    error: Optional[str]
    requested_by: str
    result: Optional[dict]
    created_at: datetime
    started_at: Optional[datetime]
    finished_at: Optional[datetime]


class AuditEvent(BaseModel):
    event_id: int
    commentary_id: UUID
    version: int
    action: str
    from_status: Optional[str]
    to_status: Optional[str]
    actor_email: str
    request_id: Optional[str]
    note: Optional[str]
    created_at: datetime


class CommentaryVersion(BaseModel):
    version: int
    text: Optional[str]
    change_type: str
    actor_email: str
    created_at: datetime


class AuditResponse(BaseModel):
    commentary: Optional[Commentary]
    events: list[AuditEvent]
    versions: list[CommentaryVersion]
    figures_by_version: dict[int, list[CommentaryFigure]]


class Me(BaseModel):
    email: str
    display_name: Optional[str]
    roles: list[str]
    is_analyst: bool
    is_approver: bool
    workspace_host: str
    features: dict[str, bool]
    data_mode: str
    default_comparison: str


class GenieAsk(BaseModel):
    question: str = Field(..., min_length=3, max_length=1000)
    figure_key: Optional[str] = Field(None, max_length=160)
