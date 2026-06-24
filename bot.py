import os
import time
import json
import hashlib
import requests
import schedule
from bs4 import BeautifulSoup
from datetime import datetime

# ─── CONFIG ────────────────────────────────────────────────────────────────────
BOT_TOKEN   = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
CHANNEL_ID  = os.environ.get("CHANNEL_ID", "@your_channel")   # বা numeric id: -1001234567890
CHECK_EVERY = 3   # মিনিট পর পর চেক করবে

KEYWORDS = [
    "কুমিল্লা বিশ্ববিদ্যালয়", "কুবি", "কু.বি",
    "comilla university", "cu student", "cu campus",
]

SITES = [
    {
        "name": "NewsvisionBD",
        "url":  "https://newsvisionbd.com",
        "search_url": "https://newsvisionbd.com/?s={query}",
        "article_selector": "article",
        "title_selector":   "h2,h3",
        "link_selector":    "a",
    },
    {
        "name": "Daily Gonokantho",
        "url":  "https://dailygonokantho.com",
        "search_url": "https://dailygonokantho.com/?s={query}",
        "article_selector": "article,.post,.news-item",
        "title_selector":   "h2,h3,h4",
        "link_selector":    "a",
    },
    {
        "name": "BD Telegraph 24",
        "url":  "https://bdtelegraph24.com",
        "search_url": "https://bdtelegraph24.com/?s={query}",
        "article_selector": "article,.post,.news-item",
        "title_selector":   "h2,h3,h4",
        "link_selector":    "a",
    },

    {
        "name": "Tafsirul Karim Blog",
        "url": "https://tafsirulkarim.blogspot.com",
        "search_url": "https://tafsirulkarim.blogspot.com/search?q={query}",
        "article_selector": "article,div.post,div.entry",
        "title_selector": "h2,h3",
        "link_selector": "a",
    },
    
    

    {
        "name": "Dhaka Diary",
        "url": "https://thedhakadiary.com",
        "search_url": "https://thedhakadiary.com/?s={query}",
        "article_selector": "article,.post",
        "title_selector": "h2,h3",
        "link_selector": "a",
    },
    {
    "name": "Soddo Songbad",
    "url": "https://soddosongbad.com",
    "search_url": "https://soddosongbad.com/?s={query}",
    "article_selector": "article,.post,.news-item",
    "title_selector": "h2,h3,h4",
    "link_selector": "a",
},
]

SEARCH_QUERIES = [
    "কুমিল্লা+বিশ্ববিদ্যালয়",
    


  "কুবি",
    "comilla+university",
]

SENT_FILE = "sent_articles.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}

# ─── HELPERS ───────────────────────────────────────────────────────────────────

def load_sent():
    if os.path.exists(SENT_FILE):
        with open(SENT_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def save_sent(sent: set):
    with open(SENT_FILE, "w", encoding="utf-8") as f:
        json.dump(list(sent), f, ensure_ascii=False)

def make_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()

def is_relevant(title: str) -> bool:
    title_lower = title.lower()
    for kw in KEYWORDS:
        if kw.lower() in title_lower:
            return True
    return False

def send_telegram(text: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id":    CHANNEL_ID,
        "text":       text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        if not r.ok:
            print(f"[TG ERROR] {r.status_code}: {r.text}")
    except Exception as e:
        print(f"[TG EXCEPTION] {e}")

# ─── SCRAPER ───────────────────────────────────────────────────────────────────

def scrape_site(site: dict, query: str) -> list[dict]:
    results = []
    search_url = site["search_url"].format(query=query)
    try:
        r = requests.get(search_url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        articles = soup.select(site["article_selector"])
        if not articles:
            # fallback: try common containers
            articles = soup.select(".td-module-container, .jeg_post, .post, article")

        for art in articles[:10]:
            # find title
            t_el = art.select_one(site["title_selector"])
            if not t_el:
                continue
            title = t_el.get_text(strip=True)

            # find link
            a_el = t_el.find("a") or art.select_one("a[href]")
            if not a_el:
                continue
            href = a_el.get("href", "")
            if not href.startswith("http"):
                href = site["url"].rstrip("/") + "/" + href.lstrip("/")

            results.append({"title": title, "url": href, "source": site["name"]})

    except Exception as e:
        print(f"[SCRAPE ERROR] {site['name']} | {query} → {e}")

    return results

# ─── MAIN CHECK ────────────────────────────────────────────────────────────────

def check_news():
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] নিউজ চেক শুরু হচ্ছে...")
    sent = load_sent()
    new_count = 0

    for site in SITES:
        for query in SEARCH_QUERIES:
            items = scrape_site(site, query)
           print(f"[DEBUG] {site['name']} | {query} | Found: {len(items)}")
            for item in items:
                uid = make_id(item["url"])
                if uid in sent:
                    continue
                if not is_relevant(item["title"]):
                    continue

                # নতুন নিউজ পাওয়া গেছে!
                msg = (
                    f"🔴 <b>কুমিল্লা বিশ্ববিদ্যালয় আপডেট</b>\n\n"
                    f"📰 {item['title']}\n\n"
                    f"🌐 সূত্র: {item['source']}\n"
                    f"🔗 <a href=\"{item['url']}\">পুরো খবর পড়ুন</a>"
                )
                send_telegram(msg)
                sent.add(uid)
                new_count += 1
                time.sleep(2)   # rate limit

    save_sent(sent)
    print(f"✅ চেক শেষ। নতুন নিউজ: {new_count}টি")

# ─── RUN ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("🤖 কুবি নিউজ বট চালু হচ্ছে...")
    send_telegram(
        "✅ <b>কুবি নিউজ বট চালু হয়েছে!</b>\n"
        f"প্রতি {CHECK_EVERY} মিনিটে নিউজ চেক করবে।"
    )
    check_news()   # প্রথমবার তাৎক্ষণিক রান
    schedule.every(CHECK_EVERY).minutes.do(check_news)
    while True:
        schedule.run_pending()
        time.sleep(30)
