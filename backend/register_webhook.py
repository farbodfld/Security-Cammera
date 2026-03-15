import os
import httpx
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
BASE_URL = os.environ.get("APP_BASE_URL", "http://localhost:8000")

def register():
    if not TOKEN:
        print("❌ ERROR: TELEGRAM_BOT_TOKEN not found in .env")
        return

    if "localhost" in BASE_URL or "127.0.0.1" in BASE_URL:
        print("⚠️ WARNING: APP_BASE_URL is set to localhost.")
        print("Telegram cannot send webhooks to localhost.")
        print("Please use a tool like 'ngrok' to get a public URL and update your .env first.")
        print(f"Example: APP_BASE_URL=https://your-ngrok-id.ngrok-free.app")
        return

    webhook_url = f"{BASE_URL.rstrip('/')}/telegram/webhook"
    telegram_url = f"https://api.telegram.org/bot{TOKEN}/setWebhook"
    
    print(f"📡 Registering webhook...")
    print(f"🔗 Target: {webhook_url}")
    
    try:
        resp = httpx.post(telegram_url, json={"url": webhook_url})
        result = resp.json()
        
        if result.get("ok"):
            print("✅ SUCCESS: Webhook registered with Telegram!")
        else:
            print(f"❌ FAILED: {result.get('description', 'Unknown error')}")
    except Exception as e:
        print(f"❌ ERROR: Could not connect to Telegram: {e}")

if __name__ == "__main__":
    register()
