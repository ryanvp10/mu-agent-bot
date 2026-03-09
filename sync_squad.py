import os
from dotenv import load_dotenv
import requests

load_dotenv()
# Tips: Jika di local, script ini akan mencari variable di sistem atau file .env
# Jika di GitHub, script akan mengambil dari GitHub Secrets
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
FB_DATA_TOKEN = os.getenv("FB_DATA_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

MU_TEAM_ID = 66

def get_mu_squad():
    print("🚀 Connecting to Football-Data.org...")
    url = f"https://api.football-data.org/v4/teams/{MU_TEAM_ID}"
    headers = {"X-Auth-Token": FB_DATA_TOKEN}
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json().get('squad', [])
    except Exception as e:
        print(f"❌ Error API Football: {e}")
        return []

def upload_to_supabase(squad):
    print(f"📤 Uploading {len(squad)} players to Supabase...")
    url = f"{SUPABASE_URL}/rest/v1/players"
    
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates" 
    }

    payload = []
    for member in squad:
        payload.append({
            "name": member['name'],
            "position": member['position'],
            "status": "Fit"
        })

    try:
        res = requests.post(url, headers=headers, json=payload)
        res.raise_for_status()
        print("✅ Sync Success!")
    except Exception as e:
        print(f"❌ Error Supabase: {e}")

if __name__ == "__main__":
    # Proteksi sederhana jika key belum diset
    if not FB_DATA_TOKEN or not SUPABASE_URL:
        print("❌ Error: API Keys tidak ditemukan. Pastikan sudah set Environment Variables.")
    else:
        data = get_mu_squad()
        if data:
            upload_to_supabase(data)