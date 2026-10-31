# main.py
from contextlib import asynccontextmanager

import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.bootstrap import bootstrap_super_admin
from app.api.cleanup import refresh_cleanup_loop
from app.api.routes.production.job_reminders import production_reminder_loop
from app.api.main_router import main_router
from app.api.security.access import AccessTokenMiddleware
from app.api.security.csrf import CsrfMiddleware
from app.config import cors_settings
from app.db.garage_session import GarageSession
from app.db.postgress_session import PostgresSession


@asynccontextmanager
async def lifespan(app: FastAPI):
    postgres_session = PostgresSession()
    garage_session = GarageSession()

    await postgres_session.verify_connection()
    async with postgres_session._sessionmaker() as session:
        await bootstrap_super_admin(session)

    app.state.postgres_session = postgres_session
    app.state.garage_session = garage_session
    cleanup = asyncio.create_task(
        refresh_cleanup_loop(postgres_session._sessionmaker)
    )
    reminders = asyncio.create_task(
        production_reminder_loop(postgres_session._sessionmaker)
    )

    yield

    cleanup.cancel()
    reminders.cancel()
    await postgres_session.dispose()


app = FastAPI(title="ERP API", lifespan=lifespan)
app.add_middleware(CsrfMiddleware)
app.add_middleware(AccessTokenMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(main_router)

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
