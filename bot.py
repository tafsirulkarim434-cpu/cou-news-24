import os
import time
import json
import hashlib
import requests
import schedule
import feedparser
from datetime import datetime, timedelta

# ─── CONFIG ────────────────────────────────────────────────────────────────────
BOT_TOKEN   = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
CHANNEL_ID  = os.environ.get("CHANNEL_ID", "@your_channel")
CHECK_EVERY = 3  # মিনিট

# Google News RSS — প্রতিটা keyword আলাদা আলাদা সার্চ হবে
SEARCH_QUERIES = [
    "কুমিল্লা বিশ্ববিদ্যালয়",
    "কুবি",
    "comilla university",
]

# শুধু এই সাইটগুলোর নিউজ রাখবে (খালি রাখলে সব সাইট থেকে আসবে)
ALLOWED_SOURCES = [
    "dailygonokantho.com",
    "newsvisionbd.com",
    "soddosongbad.com",
    "banglatribune.com",
    "bartabazer.com",
    "bdtelegraph24.com",
    "dailysokalersomoy.com",
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

def load_sent() -> set:
    if os.path.exists(SENT_FILE):
        with open(SENT_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def save_sent(sent: set):
    with open(SENT_FILE, "w", encoding="utf-8") as f:
        json.dump(list(sent), f, ensure_ascii=False)

def make_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()

def is_first_run() -> bool:
    return not os.path.exists(SENT_FILE)

def is_allowed_source(url: str) -> bool:
    if not ALLOWED_SOURCES:
        return True
    return any(source in url for source in ALLOWED_SOURCES)

def send_telegram(text: str):
    api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id":    CHANNEL_ID,
        "text":       text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    try:
        r = requests.post(api_url, json=payload, timeout=10)
        if not r.ok:
            print(f"[TG ERROR] {r.status_code}: {r.text}")
    except Exception as e:
        print(f"[TG EXCEPTION] {e}")

def get_source_name(url: str) -> str:
    """URL থেকে সাইটের নাম বের করবে"""
    clean = url.replace("https://", "").replace("http://", "").replace("www.", "")
    domain = clean.split("/")[0]
    names = {
        "dailygonokantho.com": "দৈনিক গণকন্ঠ",
        "newsvisionbd.com": "News Vision BD",
        "soddosongbad.com": "সদ্য সংবাদ",
        "banglatribune.com": "বাংলা ট্রিবিউন",
        "bartabazer.com": "বার্তা বাজার",
        "bdtelegraph24.com": "BD Telegraph 24",
        "dailysokalersomoy.com": "দৈনিক সকালের সময়",
    }
    return names.get(domain, domain)

# ─── GOOGLE NEWS RSS ────────────────────────────────────────────────────────────

def fetch_google_news(query: str) -> list:
    results = []
    rss_url = (
        f"https://news.google.com/rss/search"
        f"?q={requests.utils.quote(query)}"
        f"&hl=bn&gl=BD&ceid=BD:bn"
    )
    try:
        feed = feedparser.parse(rss_url)
        if not feed.entries:
            print(f"[GNEWS] কোনো রেজাল্ট নেই: {query}")
            return []

        print(f"[GNEWS] '{query}' → {len(feed.entries)}টি রেজাল্ট")

        for entry in feed.entries:
            title = entry.get("title", "").strip()
            link  = entry.get("link", "").strip()

            # Google News redirect link থেকে actual URL বের করা
            if "news.google.com" in link:
                try:
                    r = requests.get(link, headers=HEADERS, timeout=10, allow_redirects=True)
                    link = r.url
                except:
                    pass

            # published date
            pub_date = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                try:
                    pub_date = datetime(*entry.published_parsed[:6])
                except:
                    pass

            if title and link:
                results.append({
                    "title":    title,
                    "url":      link,
                    "source":   get_source_name(link),
                    "pub_date": pub_date,
                })

    except Exception as e:
        print(f"[GNEWS ERROR] {query} → {e}")

    return results

# ─── MAIN CHECK ────────────────────────────────────────────────────────────────

def check_news(first_run: bool = False):
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] নিউজ চেক শুরু হচ্ছে...")
    sent = load_sent()
    new_count = 0
    cutoff = datetime.now() - timedelta(hours=24)

    if first_run:
        send_telegram(
            "✅ <b>কুবি নিউজ বট চালু হয়েছে!</b>\n"
            "🕐 গত ২৪ ঘন্টার নিউজ খোঁজা হচ্ছে...\n"
            f"প্রতি {CHECK_EVERY} মিনিটে নতুন নিউজ চেক করবে।"
        )

    for query in SEARCH_QUERIES:
        items = fetch_google_news(query)

        for item in items:
            uid = make_id(item["url"])

            # already sent চেক
            if uid in sent:
                continue

            # allowed source চেক
            if not is_allowed_source(item["url"]):
                continue

            # প্রথম রানে ২৪ ঘন্টার বাইরে হলে skip
            if first_run:
                pub_date = item.get("pub_date")
                if pub_date and pub_date < cutoff:
                    sent.add(uid)
                    continue
                label = "🕐 <i>গত ২৪ ঘন্টা</i>"
            else:
                label = "🔴 <b>সর্বশেষ</b>"

            msg = (
                f"{label}\n\n"
                f"📰 <b>{item['title']}</b>\n\n"
                f"🌐 সূত্র: {item['source']}\n"
                f"🔗 <a href=\"{item['url']}\">পুরো খবর পড়ুন</a>"
            )
            send_telegram(msg)
            sent.add(uid)
            new_count += 1
            time.sleep(2)

    save_sent(sent)

    if first_run and new_count == 0:
        send_telegram("ℹ️ গত ২৪ ঘন্টায় কুমিল্লা বিশ্ববিদ্যালয় সম্পর্কিত কোনো নিউজ পাওয়া যায়নি।")

    print(f"✅ চেক শেষ। নতুন নিউজ: {new_count}টি")

# ─── RUN ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("🤖 কুবি নিউজ বট চালু হচ্ছে...")
    first = is_first_run()
    check_news(first_run=first)
    schedule.every(CHECK_EVERY).minutes.do(check_news, first_run=False)
    while True:
        schedule.run_pending()
        time.sleep(30)
