import asyncio
import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm.attributes import flag_modified
from sqlmodel import select

from app.api.routes.notification.notification_services import notify
from app.api.routes.product.product_model import Product
from app.api.routes.production.production_model import ProductionJob, ProductionJobStage
from app.api.routes.user.user_model import Role, User
from app.config import auth_settings

logger = logging.getLogger(__name__)

_OPEN = ("pending", "in_progress", "awaiting_approval")


async def production_reminder_loop(sessionmaker: async_sessionmaker) -> None:
    while True:
        try:
            await _tick(sessionmaker)
        except Exception:
            logger.exception("production reminder check failed")
        await asyncio.sleep(60)


async def _tick(sessionmaker: async_sessionmaker) -> None:
    tz = ZoneInfo(auth_settings.APP_TIMEZONE)
    now_local = datetime.now(tz)
    now = datetime.now(timezone.utc)
    morning = now_local.hour == 10 and now_local.minute < 20
    async with sessionmaker() as session:
        jobs = list(
            await session.scalars(select(ProductionJob).where(ProductionJob.status.in_(_OPEN)))  # type: ignore[attr-defined]
        )
        if not jobs:
            return
        admin_ids = list(
            await session.scalars(
                select(User.id).join(Role, Role.id == User.role_id).where(
                    Role.role_name.in_(["admin", "super_admin"])  # type: ignore[attr-defined]
                )
            )
        )
        changed = False
        for job in jobs:
            flow = dict(job.operation_flow or {})
            reminders = dict(flow.get("reminders") or {})
            product = await session.get(Product, job.product_id)
            name = product.product_name if product else "A production job"
            if job.due_at is not None and flow.get("deadline_set") and job.due_at <= now and not reminders.get("deadline"):
                await notify(
                    session,
                    admin_ids,
                    title=f"Deadline passed · {name}",
                    body=f"{name} is still {job.status.replace('_', ' ')} after its deadline.",
                    kind="job_deadline",
                    link="/production",
                )
                reminders["deadline"] = now.isoformat()
                changed = True
            if morning and job.estimated_minutes < 24 * 60:
                created = job.created_at
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                if created.astimezone(tz).date() == now_local.date() and reminders.get("same_day") != now_local.date().isoformat():
                    stages = list(
                        await session.scalars(
                            select(ProductionJobStage).where(ProductionJobStage.job_id == job.id)
                        )
                    )
                    moved = any(stage.status == "done" for stage in stages) or job.status == "awaiting_approval"
                    if not moved:
                        people = [stage.assigned_user_id for stage in stages if stage.assigned_user_id]
                        if job.created_by_user_id is not None:
                            people.append(job.created_by_user_id)
                        await notify(
                            session,
                            people,
                            title=f"Update {name} today",
                            body="This job is due today. Update it or mark the stage complete.",
                            kind="job_same_day",
                            link="/production",
                        )
                        reminders["same_day"] = now_local.date().isoformat()
                        changed = True
            if reminders != (job.operation_flow or {}).get("reminders"):
                flow["reminders"] = reminders
                job.operation_flow = flow
                flag_modified(job, "operation_flow")
                session.add(job)
        if changed:
            await session.commit()
