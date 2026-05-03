import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import async_session
from app.api.v1 import router as api_v1_router
from app.services.tray_seed import seed_tray_if_empty

# Configure logging so app loggers (kbzhuy.gigachat, kbzhuy.agent) actually emit
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
)
logging.getLogger("kbzhuy").setLevel(logging.INFO)
logging.getLogger("kbzhuy.gigachat").setLevel(logging.INFO)
logging.getLogger("kbzhuy.agent").setLevel(logging.INFO)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    try:
        async with async_session() as db:
            await seed_tray_if_empty(db)
    except Exception as e:
        # Don't crash the app if seeding fails (e.g. tables not yet migrated on first run)
        print(f"[startup] tray seed skipped: {e!r}")
    yield
    # --- Shutdown ---


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_v1_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok", "version": settings.version}
