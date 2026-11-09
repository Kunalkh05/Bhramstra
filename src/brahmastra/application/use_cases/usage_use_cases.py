"""
Application use cases for recording and analyzing request-level token and cost usage.
"""

from typing import List, Optional
from datetime import datetime, timezone
from sqlalchemy import select, func
from sqlalchemy import Engine

from brahmastra.domain.observability.models import (
    UsageRecord,
    UsageRecordCreate,
    UsageSummary,
    ModelUsageBreakdown,
    OrgUsageBreakdown,
)
from brahmastra.infrastructure.database.models import (
    UsageRecordModel,
    OrganizationModel,
    ProviderAccountModel,
)
from brahmastra.infrastructure.database.session import get_session


def record_usage(
    data: UsageRecordCreate,
    engine: Optional[Engine] = None,
) -> UsageRecord:
    """
    Log an executed generation request with token counts and micro-USD costs.
    """
    with get_session(engine) as session:
        org = session.scalar(
            select(OrganizationModel).where(OrganizationModel.name == data.org_name)
        )
        if not org:
            raise ValueError(f"Organization '{data.org_name}' not found.")

        account = session.scalar(
            select(ProviderAccountModel).where(ProviderAccountModel.name == data.account_name)
        )
        if not account:
            raise ValueError(f"Provider account '{data.account_name}' not found.")

        total_tok = data.prompt_tokens + data.completion_tokens
        now = datetime.now(timezone.utc)

        record = UsageRecordModel(
            organization_id=org.id,
            account_id=account.id,
            model_id=data.model_id,
            prompt_tokens=data.prompt_tokens,
            completion_tokens=data.completion_tokens,
            total_tokens=total_tok,
            cost_micro_usd=data.cost_micro_usd,
            latency_ms=data.latency_ms,
            timestamp=now,
        )
        session.add(record)
        session.flush()

        return UsageRecord(
            id=record.id,
            org_name=org.name,
            account_name=account.name,
            model_id=record.model_id,
            prompt_tokens=record.prompt_tokens,
            completion_tokens=record.completion_tokens,
            total_tokens=record.total_tokens,
            cost_micro_usd=record.cost_micro_usd,
            latency_ms=record.latency_ms,
            timestamp=record.timestamp,
        )


def get_usage_summary(
    org_name: Optional[str] = None,
    engine: Optional[Engine] = None,
) -> UsageSummary:
    """
    Compute aggregated token and financial usage metrics.
    """
    with get_session(engine) as session:
        base_stmt = select(UsageRecordModel)
        if org_name:
            org = session.scalar(
                select(OrganizationModel).where(OrganizationModel.name == org_name)
            )
            if not org:
                raise ValueError(f"Organization '{org_name}' not found.")
            base_stmt = base_stmt.where(UsageRecordModel.organization_id == org.id)

        records = session.scalars(base_stmt).all()
        if not records:
            return UsageSummary(
                total_requests=0,
                total_prompt_tokens=0,
                total_completion_tokens=0,
                total_tokens=0,
                total_cost_usd=0.0,
                models=[],
                orgs=[],
            )

        total_reqs = len(records)
        total_prompt = sum(r.prompt_tokens for r in records)
        total_completion = sum(r.completion_tokens for r in records)
        total_tokens = sum(r.total_tokens for r in records)
        total_cost_micro = sum(r.cost_micro_usd for r in records)
        total_cost_usd = round(total_cost_micro / 1_000_000.0, 6)

        # Group by Model
        model_stats = {}
        for r in records:
            if r.model_id not in model_stats:
                model_stats[r.model_id] = {
                    "requests": 0,
                    "prompt": 0,
                    "completion": 0,
                    "total": 0,
                    "cost_micro": 0,
                }
            s = model_stats[r.model_id]
            s["requests"] += 1
            s["prompt"] += r.prompt_tokens
            s["completion"] += r.completion_tokens
            s["total"] += r.total_tokens
            s["cost_micro"] += r.cost_micro_usd

        models_list = [
            ModelUsageBreakdown(
                model_id=m_id,
                requests=st["requests"],
                prompt_tokens=st["prompt"],
                completion_tokens=st["completion"],
                total_tokens=st["total"],
                cost_usd=round(st["cost_micro"] / 1_000_000.0, 6),
            )
            for m_id, st in model_stats.items()
        ]

        # Group by Org
        org_map = {o.id: o.name for o in session.scalars(select(OrganizationModel)).all()}
        org_stats = {}
        for r in records:
            name = org_map.get(r.organization_id, f"org-{r.organization_id}")
            if name not in org_stats:
                org_stats[name] = {"requests": 0, "total": 0, "cost_micro": 0}
            os_rec = org_stats[name]
            os_rec["requests"] += 1
            os_rec["total"] += r.total_tokens
            os_rec["cost_micro"] += r.cost_micro_usd

        orgs_list = [
            OrgUsageBreakdown(
                org_name=o_name,
                requests=st["requests"],
                total_tokens=st["total"],
                cost_usd=round(st["cost_micro"] / 1_000_000.0, 6),
            )
            for o_name, st in org_stats.items()
        ]

        return UsageSummary(
            total_requests=total_reqs,
            total_prompt_tokens=total_prompt,
            total_completion_tokens=total_completion,
            total_tokens=total_tokens,
            total_cost_usd=total_cost_usd,
            models=models_list,
            orgs=orgs_list,
        )


def list_usage_records(
    org_name: Optional[str] = None,
    limit: int = 50,
    engine: Optional[Engine] = None,
) -> List[UsageRecord]:
    """
    List individual request usage records in reverse chronological order.
    """
    with get_session(engine) as session:
        stmt = (
            select(
                UsageRecordModel,
                OrganizationModel.name.label("org_name"),
                ProviderAccountModel.name.label("account_name"),
            )
            .join(OrganizationModel, OrganizationModel.id == UsageRecordModel.organization_id)
            .join(ProviderAccountModel, ProviderAccountModel.id == UsageRecordModel.account_id)
            .order_by(UsageRecordModel.timestamp.desc())
            .limit(limit)
        )

        if org_name:
            stmt = stmt.where(OrganizationModel.name == org_name)

        rows = session.execute(stmt).all()
        return [
            UsageRecord(
                id=rec.id,
                org_name=o_name,
                account_name=a_name,
                model_id=rec.model_id,
                prompt_tokens=rec.prompt_tokens,
                completion_tokens=rec.completion_tokens,
                total_tokens=rec.total_tokens,
                cost_micro_usd=rec.cost_micro_usd,
                latency_ms=rec.latency_ms,
                timestamp=rec.timestamp,
            )
            for rec, o_name, a_name in rows
        ]
