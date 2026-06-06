from datetime import date, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, desc, func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import require_admin
from app.models import AggregatedDailyStat, DailyStatVisitor, VisitLog, Visitor
from app.schemas import (
    FrequencyPoint,
    LocationPoint,
    LocationTrendPoint,
    PageMeta,
    RetentionPoint,
    Summary,
    TrendPoint,
    VisitItem,
    VisitPage,
    VisitorItem,
    VisitorPage,
)

router = APIRouter(prefix="/analytics", tags=["analytics"], dependencies=[Depends(require_admin)])


def _date_bounds(start: date | None, end: date | None) -> tuple[datetime | None, datetime | None]:
    return (
        datetime.combine(start, datetime.min.time()) if start else None,
        datetime.combine(end + timedelta(days=1), datetime.min.time()) if end else None,
    )


@router.get("/summary", response_model=Summary)
def summary(db: Session = Depends(get_db)) -> Summary:
    total_visits = db.scalar(select(func.coalesce(func.sum(AggregatedDailyStat.visit_count), 0))) or 0
    average_confidence = db.scalar(select(func.coalesce(func.avg(VisitLog.confidence_score), 0))) or 0
    unique = db.scalar(select(func.count(Visitor.id))) or 0
    returning = db.scalar(select(func.count(Visitor.id)).where(Visitor.total_visits > 1)) or 0
    top_city = db.execute(
        select(AggregatedDailyStat.city, func.sum(AggregatedDailyStat.visit_count).label("visits"))
        .where(AggregatedDailyStat.city != "Unknown")
        .group_by(AggregatedDailyStat.city).order_by(desc("visits")).limit(1)
    ).first()
    top_state = db.execute(
        select(AggregatedDailyStat.state, func.sum(AggregatedDailyStat.visit_count).label("visits"))
        .where(AggregatedDailyStat.state != "Unknown")
        .group_by(AggregatedDailyStat.state).order_by(desc("visits")).limit(1)
    ).first()
    return Summary(
        total_visits=int(total_visits),
        unique_visitors=unique,
        returning_visitors=returning,
        top_city=top_city[0] if top_city else None,
        top_state=top_state[0] if top_state else None,
        average_confidence=round(float(average_confidence), 1),
    )


VISITOR_SORTS = {
    "most_visits": Visitor.total_visits.desc(),
    "least_visits": Visitor.total_visits.asc(),
    "most_recent": Visitor.last_seen.desc(),
    "oldest": Visitor.first_seen.asc(),
    "city": Visitor.current_city.asc(),
    "state": Visitor.current_state.asc(),
    "confidence": Visitor.confidence_score.desc(),
    "first_seen": Visitor.first_seen.desc(),
    "last_seen": Visitor.last_seen.desc(),
}


@router.get("/visitors", response_model=VisitorPage)
def visitors(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    city: str | None = Query(None, max_length=120),
    state: str | None = Query(None, max_length=120),
    returning: bool | None = None,
    min_confidence: int | None = Query(None, ge=0, le=100),
    start_date: date | None = None,
    end_date: date | None = None,
    sort: Literal[
        "most_visits", "least_visits", "most_recent", "oldest", "city",
        "state", "confidence", "first_seen", "last_seen"
    ] = "most_recent",
) -> VisitorPage:
    query = select(Visitor)
    if city:
        query = query.where(Visitor.current_city == city)
    if state:
        query = query.where(Visitor.current_state == state)
    if returning is not None:
        query = query.where(Visitor.total_visits > 1 if returning else Visitor.total_visits == 1)
    if min_confidence is not None:
        query = query.where(Visitor.confidence_score >= min_confidence)
    start, end = _date_bounds(start_date, end_date)
    if start:
        query = query.where(Visitor.last_seen >= start)
    if end:
        query = query.where(Visitor.last_seen < end)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(
        query.order_by(VISITOR_SORTS[sort]).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return VisitorPage(
        items=[
            VisitorItem(
                id=row.id,
                anonymous_id=row.visitor_hash[:12],
                first_seen=row.first_seen,
                last_seen=row.last_seen,
                total_visits=row.total_visits,
                current_city=row.current_city,
                current_state=row.current_state,
                current_country=row.current_country,
                confidence_score=row.confidence_score,
            )
            for row in rows
        ],
        meta=PageMeta(page=page, page_size=page_size, total=total),
    )


@router.get("/visits", response_model=VisitPage)
def visits(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    city: str | None = Query(None, max_length=120),
    state: str | None = Query(None, max_length=120),
    device_type: str | None = Query(None, max_length=40),
    browser: str | None = Query(None, max_length=80),
    min_confidence: int | None = Query(None, ge=0, le=100),
    start_date: date | None = None,
    end_date: date | None = None,
) -> VisitPage:
    query = select(VisitLog, Visitor.visitor_hash).join(Visitor)
    if city:
        query = query.where(VisitLog.city == city)
    if state:
        query = query.where(VisitLog.state == state)
    if device_type:
        query = query.where(VisitLog.device_type == device_type)
    if browser:
        query = query.where(VisitLog.browser == browser)
    if min_confidence is not None:
        query = query.where(VisitLog.confidence_score >= min_confidence)
    start, end = _date_bounds(start_date, end_date)
    if start:
        query = query.where(VisitLog.timestamp >= start)
    if end:
        query = query.where(VisitLog.timestamp < end)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.execute(
        query.order_by(VisitLog.timestamp.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return VisitPage(
        items=[
            VisitItem(
                id=visit.id,
                anonymous_id=visitor_hash[:12],
                timestamp=visit.timestamp,
                city=visit.city,
                state=visit.state,
                country=visit.country,
                confidence_score=visit.confidence_score,
                browser=visit.browser,
                os=visit.os,
                device_type=visit.device_type,
                network_type=visit.network_type,
                is_anomalous=visit.is_anomalous,
                anomaly_reasons=visit.anomaly_reasons,
            )
            for visit, visitor_hash in rows
        ],
        meta=PageMeta(page=page, page_size=page_size, total=total),
    )


@router.get("/trends", response_model=list[TrendPoint])
def trends(
    period: Literal["daily", "weekly", "monthly"] = "daily",
    days: int = Query(90, ge=7, le=730),
    db: Session = Depends(get_db),
) -> list[TrendPoint]:
    since = date.today() - timedelta(days=days - 1)
    if period == "daily":
        key = func.strftime("%Y-%m-%d", AggregatedDailyStat.date)
    elif period == "weekly":
        key = func.strftime("%Y-W%W", AggregatedDailyStat.date)
    else:
        key = func.strftime("%Y-%m", AggregatedDailyStat.date)
    rows = db.execute(
        select(
            key.label("period"),
            func.sum(AggregatedDailyStat.visit_count),
            func.count(func.distinct(DailyStatVisitor.visitor_id)),
        )
        .outerjoin(DailyStatVisitor, DailyStatVisitor.daily_stat_id == AggregatedDailyStat.id)
        .where(AggregatedDailyStat.date >= since)
        .group_by(key)
        .order_by(key)
    ).all()
    return [TrendPoint(period=row[0], visits=row[1] or 0, unique_visitors=row[2] or 0) for row in rows]


@router.get("/locations/{group_by}", response_model=list[LocationPoint])
def locations(
    group_by: Literal["city", "state"],
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[LocationPoint]:
    column = AggregatedDailyStat.city if group_by == "city" else AggregatedDailyStat.state
    rows = db.execute(
        select(
            column.label("name"),
            func.sum(AggregatedDailyStat.visit_count).label("visits"),
        )
        .group_by(column).order_by(desc("visits")).limit(limit)
    ).all()
    result = []
    for row in rows:
        details = db.execute(
            select(
                func.count(func.distinct(DailyStatVisitor.visitor_id)),
                func.avg(Visitor.confidence_score),
            )
            .select_from(AggregatedDailyStat)
            .join(DailyStatVisitor, DailyStatVisitor.daily_stat_id == AggregatedDailyStat.id)
            .join(Visitor, Visitor.id == DailyStatVisitor.visitor_id)
            .where(column == row.name)
        ).one()
        result.append(
            LocationPoint(
                name=row.name,
                visits=row.visits,
                unique_visitors=details[0] or 0,
                average_confidence=round(float(details[1] or 0), 1),
            )
        )
    return result


@router.get("/retention", response_model=list[RetentionPoint])
def retention(db: Session = Depends(get_db)) -> list[RetentionPoint]:
    cohort = func.strftime("%Y-W%W", Visitor.first_seen)
    rows = db.execute(
        select(
            cohort.label("cohort"),
            func.count(Visitor.id).label("cohort_size"),
            func.sum(case((Visitor.total_visits > 1, 1), else_=0)).label("returned"),
        ).group_by(cohort).order_by(cohort.desc()).limit(12)
    ).all()
    return [
        RetentionPoint(
            cohort=row.cohort,
            cohort_size=row.cohort_size,
            returned=row.returned or 0,
            retention_rate=round((row.returned or 0) * 100 / row.cohort_size, 1),
        )
        for row in reversed(rows)
    ]


@router.get("/frequency", response_model=list[FrequencyPoint])
def frequency(db: Session = Depends(get_db)) -> list[FrequencyPoint]:
    bucket = case(
        (Visitor.total_visits == 1, "1"),
        (Visitor.total_visits <= 3, "2-3"),
        (Visitor.total_visits <= 9, "4-9"),
        else_="10+",
    )
    rows = dict(db.execute(select(bucket, func.count(Visitor.id)).group_by(bucket)).all())
    return [FrequencyPoint(bucket=label, visitors=rows.get(label, 0)) for label in ("1", "2-3", "4-9", "10+")]


@router.get("/location-trends", response_model=list[LocationTrendPoint])
def location_trends(
    group_by: Literal["city", "state"] = "city",
    days: int = Query(90, ge=7, le=365),
    limit: int = Query(5, ge=1, le=10),
    db: Session = Depends(get_db),
) -> list[LocationTrendPoint]:
    column = AggregatedDailyStat.city if group_by == "city" else AggregatedDailyStat.state
    since = date.today() - timedelta(days=days - 1)
    top_locations = db.scalars(
        select(column)
        .where(AggregatedDailyStat.date >= since, column != "Unknown")
        .group_by(column)
        .order_by(func.sum(AggregatedDailyStat.visit_count).desc())
        .limit(limit)
    ).all()
    if not top_locations:
        return []
    rows = db.execute(
        select(
            func.strftime("%Y-%m-%d", AggregatedDailyStat.date),
            column,
            func.sum(AggregatedDailyStat.visit_count),
        )
        .where(AggregatedDailyStat.date >= since, column.in_(top_locations))
        .group_by(AggregatedDailyStat.date, column)
        .order_by(AggregatedDailyStat.date, column)
    ).all()
    return [LocationTrendPoint(period=row[0], location=row[1], visits=row[2]) for row in rows]
