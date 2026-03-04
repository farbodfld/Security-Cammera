# 📷 Security Camera System

A production-grade, self-hosted AI security camera system. Uses a laptop webcam as a smart camera agent that reports detections to a cloud backend, with a rich web dashboard and Telegram bot alerts.

---

## Architecture

```
┌──────────────┐    HTTP / WebSocket    ┌────────────────┐    HTTP     ┌─────────────┐
│  Agent       │  ──────────────────►  │  Backend       │  ◄────────  │  Dashboard  │
│  (Python)    │  ◄──────────────────  │  (FastAPI)     │            │  (Next.js)  │
│  Webcam +    │    set_state msgs      │  SQLite / PG   │            └─────────────┘
│  YOLOv8      │                        └───────┬────────┘
└──────────────┘                                │ Telegram Bot API
                                                ▼
                                        ┌──────────────┐
                                        │  Telegram    │
                                        │  (Mobile)    │
                                        └──────────────┘
```

| Component | Tech | Directory |
|---|---|---|
| Agent | Python 3.11, OpenCV, YOLOv8, websocket-client | `agent/` |
| Backend | FastAPI, SQLAlchemy, SQLite, websocket-client | `backend/` |
| Dashboard | Next.js 15, TypeScript, pure CSS | `dashboard/` |

---

## Quick Start

### 1. Backend

```powershell
cd backend

# Create & activate virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# Install deps
pip install -r requirements.txt

# Configure (copy and edit)
copy .env.example .env
# → Set TELEGRAM_BOT_TOKEN, JWT_SECRET_KEY

# Start server
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 2. Dashboard

```powershell
cd dashboard
npm install
npm run dev
# Open http://localhost:3000
```

### 3. Agent

**First time (pairing):**

1. Register on the dashboard and go to **Devices → Add Device**
2. Copy the 6-digit pair code shown
3. On the machine with the webcam:

```powershell
cd agent
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

python src/main.py --pair-code 123456 --server-url http://<your-server>:8000
```

**Subsequent starts:**
```powershell
python src/main.py
# or headless (no GUI window):
python src/main.py --headless
```

### 4. Remote Control & Spawning
The system supports **Remote Arming**:
- If a paired agent is offline, clicking **Arm** in the dashboard will automatically spawn the agent process in the background on the host machine.
- **Headless Toggle**: In **Devices → Settings**, you can toggle "Headless Mode". When enabled, remote starts will be completely invisible (no GUI or CMD window).
- **Auto-Sync**: The agent automatically arms itself when it connects to the server and cleans up its process when disarmed via the dashboard.

---

## Telegram Bot Setup

1. Open Telegram and search for **@BotFather**
2. Send `/newbot` and follow the prompts
3. Copy the token and add it to `backend/.env` as `TELEGRAM_BOT_TOKEN`
4. For production, register the webhook:
   ```
   https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://<your-domain>/telegram/webhook
   ```
5. In the dashboard → **Telegram** → Generate OTP → send it to your bot

### Bot Commands

| Command | Description |
|---|---|
| `/start` | Get a link code for your dashboard |
| `/devices` | List all paired cameras |
| `/arm` | Arm your camera (shows menu if multiple) |
| `/arm 2` | Arm camera #2 |
| `/disarm` | Disarm your camera |
| `/disarm 1` | Disarm camera #1 |

---

## Agent Controls (with GUI)

| Key | Action |
|---|---|
| `Q` | Quit |
| `Space` | Pause / Resume |
| `+` / `-` | Increase / decrease confidence threshold |

---

## Event Management
- **Snapshot History**: View a chronological timeline of all detected persons.
- **Delete All**: Use the "🗑️ Delete All" button to instantly wipe all events and delete their associated image files from the server's disk.

---

## Project Structure

```
Security Cammera/
├── backend/
│   ├── main.py               # FastAPI app, router mounting
│   ├── models.py             # SQLAlchemy ORM models
│   ├── schemas.py            # Pydantic schemas
│   ├── database.py           # Engine + session factory
│   ├── security.py           # JWT + password hashing
│   ├── requirements.txt
│   ├── .env.example
│   └── routers/
│       ├── auth.py           # Register / Login
│       ├── devices.py        # Pair code generation + device pairing
│       ├── dashboard.py      # Device management (dashboard users)
│       ├── events.py         # Event creation + snapshot upload
│       ├── telegram.py       # Telegram webhook + OTP + alerts
│       └── ws.py             # WebSocket endpoint for agents
│
├── agent/
│   ├── requirements.txt
│   └── src/
│       ├── main.py           # Entry point + CLI flags + pairing
│       ├── api_client.py     # HTTP + WebSocket backend client
│       ├── config_manager.py # Token persistence (device_credentials.json)
│       ├── event_handler.py  # Detection events → backend + local files
│       ├── detector.py       # YOLOv8 person detection
│       ├── config.py         # App-wide configuration constants
│       ├── display.py        # OpenCV overlay utilities
│       └── notifier.py       # Legacy Telegram notifier (now bypassed)
│
└── dashboard/
    ├── .env.local            # NEXT_PUBLIC_API_URL
    └── src/
        ├── app/
        │   ├── layout.tsx
        │   ├── page.tsx      # → redirects to /login or /dashboard
        │   ├── login/
        │   ├── register/
        │   └── dashboard/
        │       ├── layout.tsx
        │       ├── page.tsx       # Overview + stat cards
        │       ├── devices/       # Pair, arm/disarm, settings (Headless toggle)
        │       ├── events/        # Timeline + snapshot viewer, Delete All
        │       └── telegram/      # OTP linking + command reference
        ├── components/
        │   └── Sidebar.tsx
        ├── context/
        │   └── AuthContext.tsx
        └── lib/
            └── api.ts             # Typed backend client
```

---

## Security Notes

- **Agent auth**: `X-Device-Token` header (separate from JWT)
- **Dashboard auth**: `Authorization: Bearer <jwt>` 
- **Pair codes**: 10-min expiry, single-use, atomic DB transaction
- **Snapshots**: UUID filenames, ownership-verified serving
- **Telegram commands**: device-aware, `control_mode` enforced
- **Webhook**: idempotent (`update_id` dedup)

---

## Environment Variables

See `backend/.env.example` for the full list. The minimum required:

| Variable | Required | Description |
|---|---|---|
| `JWT_SECRET_KEY` | ✅ | Random 64-char hex string |
| `TELEGRAM_BOT_TOKEN` | Optional | Enables Telegram alerts |
| `DATABASE_URL` | Optional | Defaults to SQLite |
