from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
from database import engine, Base, get_db
from routers import auth, devices, dashboard, events, telegram, ws
from sqlalchemy.orm import Session
from sqlalchemy import text

from fastapi.staticfiles import StaticFiles
import os

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize database
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Security Camera Mother System API")

# Production CORS setup
ALLOWED_ORIGINS = [o.strip().rstrip("/") for o in os.environ.get("ALLOWED_ORIGINS", "*").split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {
            "status": "ok", 
            "database": "connected", 
            "driver": engine.url.drivername,
            "origins": ALLOWED_ORIGINS
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Global error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)}
    )

# Create media directory if it doesn't exist
os.makedirs("media/events", exist_ok=True)
app.mount("/media", StaticFiles(directory="media"), name="media")

# Include Routers
app.include_router(auth.router)
app.include_router(devices.router)
app.include_router(dashboard.router)
app.include_router(events.router)
app.include_router(telegram.router)
app.include_router(ws.router)

@app.get("/")
def read_root():
    return {"status": "ok", "service": "Security Camera Backend"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
