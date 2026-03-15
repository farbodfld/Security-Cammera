from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from database import engine, Base
from routers import auth, devices, dashboard, events, telegram, ws

from fastapi.staticfiles import StaticFiles
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize database
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Security Camera Mother System API")

# Production CORS setup
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
