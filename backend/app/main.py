from dotenv import load_dotenv
load_dotenv()

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.api.claims import router as claims_router
from app.api.test_submit import router as test_router
from app.api.members import router as members_router
from app.db.database import engine
from app.db.models import Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    try:
        from app.db.seed import seed
        seed()
    except Exception as e:
        print(f"[startup] seed skipped: {e}")
    yield


app = FastAPI(
    title="Plum OPD Claims Adjudication",
    version="1.0.0",
    description="AI-powered OPD insurance claim adjudication system",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(claims_router)
app.include_router(test_router)
app.include_router(members_router)


@app.get("/health")
def health():
    return {"status": "ok"}


# Serve React frontend when built (npm run build → frontend/dist → backend/static)
_static = Path(__file__).parent.parent / "static"
if _static.exists():
    _assets = _static / "assets"
    if _assets.exists():
        app.mount("/assets", StaticFiles(directory=str(_assets)), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        return FileResponse(str(_static / "index.html"))