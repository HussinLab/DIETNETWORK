from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import auth, jobs, uploads

settings = get_settings()

# Schema is owned by Alembic (backend/alembic/) and applied by
# docker-entrypoint.sh before this app starts, in every environment.
app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(uploads.router)
app.include_router(jobs.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
