# main.py
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.main_router import main_router
from app.config import cors_settings
from app.db.garage_session import GarageSession
from app.db.postgress_session import PostgresSession


@asynccontextmanager
async def lifespan(app: FastAPI):
    postgres_session = PostgresSession()
    garage_session = GarageSession()

    await postgres_session.verify_connection()

    app.state.postgres_session = postgres_session
    app.state.garage_session = garage_session

    yield

    await postgres_session.dispose()


app = FastAPI(title="ERP API", lifespan=lifespan)
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
