import os
import telebot
import requests
import feedparser
import google.generativeai as genai
from dotenv import load_dotenv
from telebot import types
from supabase import create_client, Client
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from urllib.parse import urlparse

load_dotenv()

# Konfigurasi
bot = telebot.TeleBot(os.getenv("TELEGRAM_TOKEN"))
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
FB_TOKEN = os.getenv("FB_DATA_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

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

    model = genai.GenerativeModel('gemini-2.5-flash')

    safety_settings = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }
    try:
        response = model.generate_content(
            prompt_text,
            safety_settings=safety_settings
        )
        
        # Cek jika response ada dan memiliki teks
        if response and response.candidates and response.candidates[0].content.parts:
            return response.text.strip()
        else:
            # Jika diblokir atau kosong, coba berikan teks default
            print(f"⚠️ Gemini menolak menjawab. Judul yang dikirim: {prompt_text[:50]}...")
            return "Berita sedang diproses, intinya ada perkembangan terbaru di tim. Cek link di bawah!"
            
    except Exception as e:
        print(f"❌ Detail Error Gemini: {e}")
        return "AI sedang sibuk merangkum. Silakan baca detail melalui link berikut."

# --- HANDLER PERINTAH TELEGRAM ---

@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = types.ReplyKeyboardMarkup(row_width=3, resize_keyboard=True)
    markup.add('/nextmatch', '/results', '/teamnews', '/transfer')
    bot.reply_to(message, "🔴 *Manchester United Assistant* 🔴\n\nSelamat datang! Gunakan menu di bawah untuk info terbaru.", reply_markup=markup, parse_mode="Markdown")

#-- Team News
@bot.message_handler(commands=['nextmatch'])
def next_match(message):
    matches = get_match_data("SCHEDULED", 1)
    if matches:
        m = matches[0]
        msg = f"📅 *NEXT MATCH*\n\n🏆 {m['competition']['name']}\n⚽ {m['homeTeam']['name']} vs {m['awayTeam']['name']}\n⏰ {m['utcDate']}"
        bot.reply_to(message, msg, parse_mode="Markdown")
    else:
        bot.reply_to(message, "Belum ada jadwal pertandingan mendatang.")

# Results Handler
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

# Team News Handler

@bot.message_handler(commands=['teamnews'])
def team_news(message):
    bot.send_chat_action(message.chat.id, 'typing')
    args = message.text.split()
    player_query = args[1].lower() if len(args) > 1 else None

    # --- 1. AMBIL DATA DARI SEMUA SUMBER SEKALIGUS ---
    sources = [
        "https://www.manutd.com/en/rssfeed/news",
        "https://bbc.com/sport/football/teams/manchester-united/rss.xml",
        "https://www.skysports.com/rss/12461"
    ]
    
    headers = {'User-Agent': 'Mozilla/5.0'}
    raw_news_list = []

    for url in sources:
        try:
            r = requests.get(url, headers=headers, timeout=5)
            feed = feedparser.parse(r.content)
            # Ambil 5 berita teratas dari tiap sumber
            for entry in feed.entries[:5]:
                raw_news_list.append({"title": entry.title, "link": entry.link})
        except:
            print(f"⚠️ Gagal akses sumber: {url}")

    if not raw_news_list:
        bot.reply_to(message, "❌ Semua sumber berita sedang gangguan. GGMU! 🔴")
        return

    # --- 2. FILTER BERDASARKAN PLAYER (JIKA ADA) ---
    filtered_titles = []
    links_to_show = []
    
    if player_query:
        for n in raw_news_list:
            if player_query in n['title'].lower():
                filtered_titles.append(n['title'])
                links_to_show.append(n['link'])
        
        target_subject = player_query.upper()
    else:
        # Jika berita umum, ambil 5 judul terbaru saja untuk dirangkum
        filtered_titles = [n['title'] for n in raw_news_list[:5]]
        links_to_show = [n['link'] for n in raw_news_list[:3]]
        target_subject = "TIM UTAMA"

    if not filtered_titles:
        bot.reply_to(message, f"Tidak ditemukan berita terbaru untuk *{player_query}* di semua sumber.")
        return

    # --- 3. SURUH GEMINI MERANGKUM SEMUA JADI SATU ---
    # Kita gabungkan semua judul menjadi satu string panjang untuk dianalisis AI
    titles_combined = "\n- ".join(filtered_titles)
    
    prompt = (
        f"Kamu adalah asisten fans Manchester United. "
        f"Berikut adalah daftar berita terbaru tentang {target_subject}:\n\n"
        f"{titles_combined}\n"
        f"Tolong buatkan SATU paragraf rangkuman pendek (2-3 kalimat) dalam Bahasa Indonesia santai. "
        f"Fokus pada fakta terpenting saja."
    )
    
    ai_summary = get_ai_summary(prompt)

    # --- 4. TAMPILKAN HASIL & AUTO-SAVE ---
    main_link = links_to_show[0] # Link utama untuk referensi
    
    report = (
        f"🏥 *UPDATE {target_subject}* 🏟️\n\n"
        f"🤖 *Rangkuman AI:*\n{ai_summary}\n\n"
        f"🔗 *Sumber Terkait:*\n"
    )
    unique_links = list(set(links_to_show))[:4] 

    for link in unique_links:
        try:
            # Ekstrak nama domain
            domain = urlparse(link).netloc.lower()
            
            # Logika penamaan sumber yang rapi
            if "manutd.com" in domain:
                source_name = "Official MU 🔴"
            elif "bbc" in domain:
                source_name = "BBC Sport 📺"
            elif "skysports" in domain:
                source_name = "Sky Sports 🏆"
            else:
                # Ambil nama domain saja jika tidak terdaftar (misal: manutd.com)
                source_name = domain.replace('www.', '').split('.')[0].capitalize()
            report += f"▫️ [{source_name}]({link})\n"
        except:
            report += f"▫️ [Link Berita]({link})\n"

    bot.reply_to(message, report, parse_mode="Markdown", disable_web_page_preview=True)

    # Simpan rangkuman kolektif ini ke Supabase agar bisa dicari nanti
    save_to_history(f"Update Kolektif: {target_subject}", main_link, ai_summary, player_query or "General")

# --- FUNGSI HELPER UNTUK SIMPAN KE SUPABASE ---
def save_to_history(title, url, summary, tag):
    try:
        # Cek dulu apakah URL berita ini sudah pernah disimpan (biar gak duplikat)
        exists = supabase.table("news_history").select("id").eq("url", url).execute()
        if not exists.data:
            data = {
                "title": title,
                "url": url,
                "summary": summary,
                "player_tag": tag
            }
            supabase.table("news_history").insert(data).execute()
            print(f"✅ Berita berhasil diarsipkan: {title[:30]}...")
    except Exception as e:
        print(f"❌ Gagal simpan ke DB: {e}")

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

# Transfer News Handler

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