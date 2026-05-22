from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.api.sessions import get_cost_logger
from app.services.cost_logger import CostLogger, DailyStats

router = APIRouter()


class StatsData(BaseModel):
    days: list[DailyStats]


class StatsResponse(BaseModel):
    success: Literal[True]
    data: StatsData


@router.get("/v1/stats", response_model=StatsResponse)
async def get_stats(
    cost_logger: Annotated[CostLogger, Depends(get_cost_logger)],
    days: Annotated[int, Query(ge=1, le=2)] = 1,
) -> StatsResponse:
    today = datetime.now(UTC).date()
    daily = [
        await cost_logger.daily(today - timedelta(days=offset))
        for offset in range(days)
    ]
    return StatsResponse(success=True, data=StatsData(days=daily))
