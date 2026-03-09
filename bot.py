import os
import feedparser
import google.generativeai as genai
import requests
from dotenv import load_dotenv

load_dotenv()

# Konfigurasi API
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# Sumber Berita MU (RSS Feed)
RSS_SOURCES = [
    "https://www.manutd.com/en/rssfeed/news",
    "https://bbc.com/sport/football/teams/manchester-united/rss.xml"
]

def get_latest_news():
    news_items = []
    for url in RSS_SOURCES:
        feed = feedparser.parse(url)
        for entry in feed.entries[:3]: # Ambil 3 berita terbaru per sumber
            news_items.append({
                "title": entry.title,
                "link": entry.link
            })
    return news_items

def ask_gemini_to_summarize(title):
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = f"Rangkum berita bola ini dalam 1 kalimat santai tapi informatif untuk fans MU dalam Bahasa Indonesia: {title}"
    
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Error Gemini: {e}")
        return "Gagal merangkum berita."

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    requests.post(url, data=payload)

if __name__ == "__main__":
    print("🔎 Mencari berita MU terbaru...")
    news_list = get_latest_news()
    
    for news in news_list:
        summary = ask_gemini_to_summarize(news['title'])
        
        caption = (
            f"🔴 *BERITA TERBARU MU*\n\n"
            f"📰 {news['title']}\n\n"
            f"🤖 *Gemini says:* {summary}\n\n"
            f"🔗 [Baca Selengkapnya]({news['link']})"
        )
        
        print(f"✅ Mengirim ke Telegram: {news['title']}")
        send_telegram(caption)