"""Flux overview: waterfall + slice table (one payload), comparisons, slices and figure lookups. User identity."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from .. import gold
from ..auth import User, current_user
from ..models import Comparison, Figure, FluxResponse, SliceOption, check_comparison, check_slice

router = APIRouter(tags=["flux"])


@router.get("/comparisons", response_model=list[Comparison])
def list_comparisons(user: User = Depends(current_user)):
    return gold.comparisons(user)


@router.get("/slices", response_model=list[SliceOption])
def list_slices(period: str = Query(...), user: User = Depends(current_user)):
    return gold.slice_options(user, check_comparison(period))


@router.get("/flux", response_model=FluxResponse)
def get_flux(period: str = Query(..., description="comparison_id, e.g. MOM_2026-09"),
             slice: str = Query("APAC"), breakdown: Optional[str] = Query(None),
             user: User = Depends(current_user)):
    return gold.flux(user, check_comparison(period), check_slice(slice), breakdown)


@router.get("/figures/{figure_key:path}", response_model=Figure)
def get_figure(figure_key: str, user: User = Depends(current_user)):
    """Value, source table, filter and Delta version behind a figure."""
    from fastapi import HTTPException

    from ..models import FIGURE_RE

    if not FIGURE_RE.match(figure_key):
        raise HTTPException(status_code=422, detail="invalid figure key")
    return gold.figure(user, figure_key)
