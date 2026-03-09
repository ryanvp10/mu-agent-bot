import os
import telebot
import requests
import feedparser
import google.generativeai as genai
from dotenv import load_dotenv
from telebot import types

load_dotenv()

# Konfigurasi
bot = telebot.TeleBot(os.getenv("TELEGRAM_TOKEN"))
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
FB_TOKEN = os.getenv("FB_DATA_TOKEN")

# --- FUNGSI LOGIKA DATA ---

def get_match_data(status="SCHEDULED", limit=1):
    """Fungsi umum untuk mengambil jadwal atau hasil pertandingan"""
    url = f"https://api.football-data.org/v4/teams/66/matches?status={status}&limit={limit}"
    headers = {"X-Auth-Token": FB_TOKEN}
    try:
        res = requests.get(url, headers=headers).json()
        return res['matches']
    except:
        return None

def get_ai_summary(prompt_text):
    """Fungsi AI Gemini untuk merangkum teks apa pun"""
    model = genai.GenerativeModel('gemini-3-flash')
    try:
        response = model.generate_content(prompt_text)
        return response.text.strip()
    except:
        return "Gagal mendapatkan rangkuman AI."

# --- HANDLER PERINTAH TELEGRAM ---

@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = types.ReplyKeyboardMarkup(row_width=3, resize_keyboard=True)
    markup.add('/nextmatch', '/results', '/teamnews', '/transfer')
    bot.reply_to(message, "🔴 *Manchester United Assistant* 🔴\n\nSelamat datang! Gunakan menu di bawah untuk info terbaru.", reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(commands=['nextmatch'])
def next_match(message):
    matches = get_match_data("SCHEDULED", 1)
    if matches:
        m = matches[0]
        msg = f"📅 *NEXT MATCH*\n\n🏆 {m['competition']['name']}\n⚽ {m['homeTeam']['name']} vs {m['awayTeam']['name']}\n⏰ {m['utcDate']}"
        bot.reply_to(message, msg, parse_mode="Markdown")
    else:
        bot.reply_to(message, "Belum ada jadwal pertandingan mendatang.")

@bot.message_handler(commands=['results'])
def last_results(message):
    matches = get_match_data("FINISHED", 5) # Ambil 5 hasil terakhir
    if matches:
        text = "🏟️ *HASIL PERTANDINGAN TERAKHIR*\n\n"
        for m in matches:
            home_name = m['homeTeam']['shortName'] or m['homeTeam']['name']
            away_name = m['awayTeam']['shortName'] or m['awayTeam']['name']
            home_score = m['score']['fullTime']['home']
            away_score = m['score']['fullTime']['away']
            if home_score > away_score:
                result_line = f"✅ *{home_name}* {home_score} - {away_score} {away_name}"
            elif away_score > home_score:
                result_line = f"{home_name} {home_score} - {away_score} *{away_name}* ✅"
            else:
                result_line = f"🤝 {home_name} {home_score} - {away_score} {away_name} (Draw)"
            
            competition = m['competition']['name']
            text += f"🏆 {competition}\n{result_line}\n\n"
            
        bot.reply_to(message, text, parse_mode="Markdown")
    else:
        bot.reply_to(message, "Gagal mengambil data hasil pertandingan.")

@bot.message_handler(commands=['teamnews'])
def team_news(message):
    bot.send_chat_action(message.chat.id, 'typing')
    feed = feedparser.parse("https://www.manutd.com/en/rssfeed/news")
    # Cari berita yang mengandung kata kunci cedera/skuad/latihan
    news_found = False
    for entry in feed.entries[:5]:
        summary = get_ai_summary(f"Rangkum berita kondisi tim MU ini dalam 1 kalimat: {entry.title}")
        caption = f"🏥 *TEAM NEWS*\n\n📰 {entry.title}\n🤖 {summary}\n🔗 [Detail]({entry.link})"
        bot.send_message(message.chat.id, caption, parse_mode="Markdown")
        news_found = True
        break # Ambil 1 yang paling relevan
    if not news_found:
        bot.reply_to(message, "Tidak ada berita tim spesifik saat ini.")

def get_transfer_news():
    # Daftar sumber RSS terpercaya untuk transfer
    sources = [
        "https://www.skysports.com/rss/12461", # Sky Sports Transfer
        "https://www.theguardian.com/football/manchester-united/rss", # The Guardian MU
        "https://bbc.com/sport/football/teams/manchester-united/rss.xml" # BBC MU
    ]
    
    all_entries = []
    for url in sources:
        feed = feedparser.parse(url)
        all_entries.extend(feed.entries[:3]) # Ambil 3 dari tiap sumber
    
    return all_entries

@bot.message_handler(commands=['transfer'])
def transfer_talk(message):
    bot.send_chat_action(message.chat.id, 'typing')
    entries = get_transfer_news()
    
    found = False
    # Kita filter berita yang HANYA mengandung kata kunci transfer
    keywords = ['transfer', 'sign', 'buy', 'sell', 'bid', 'contract', 'loan', 'target']
    
    for entry in entries[:8]: # Cek 8 berita terbaru
        title_lower = entry.title.lower()
        if any(key in title_lower for key in keywords):
            # Perkuat Prompt agar Gemini tidak error
            prompt = (
                f"Tolong rangkum berita transfer Manchester United ini dalam 1 kalimat pendek "
                f"yang santai (gaya bahasa fans bola): '{entry.title}'. "
                f"Jika bukan tentang transfer pemain, katakan 'Bukan berita transfer'."
            )
            
            summary = get_ai_summary(prompt)
            
            if "Bukan berita transfer" not in summary:
                caption = (
                    f"💸 *TRANSFER UPDATE*\n\n"
                    f"📰 {entry.title}\n"
                    f"🤖 *Gemini:* {summary}\n\n"
                    f"🔗 [Baca Detail]({entry.link})"
                )
                bot.send_message(message.chat.id, caption, parse_mode="Markdown")
                found = True
                break # Kirim 1 yang paling hot saja agar tidak spam
                
    if not found:
        bot.reply_to(message, "Belum ada rumor transfer panas hari ini. Pantau terus! 🔴")
    
# --- RUN ---
if __name__ == "__main__":
    print("🚀 Bot Interaktif Aktif...")
    bot.infinity_polling()