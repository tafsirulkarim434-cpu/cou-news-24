import os
import time
import json
import hashlib
import requests
import schedule
import feedparser
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# ─── CONFIG ────────────────────────────────────────────────────────────────────
BOT_TOKEN   = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
CHANNEL_ID  = os.environ.get("CHANNEL_ID", "@your_channel")
CHECK_EVERY = 3

KEYWORDS = [
    "কুমিল্লা বিশ্ববিদ্যালয়", "কুবি", "কু.বি",
    "comilla university", "কুবির",
]

SENT_FILE = "sent_articles.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}

# ─── সাইট CONFIG ───────────────────────────────────────────────────────────────
# প্রতিটা সাইটের জন্য সরাসরি কুবি-related page বা search URL
SITES = [
    {
        "name": "দৈনিক গণকন্ঠ",
        "type": "scrape",
        "urls": [
            "https://dailygonokantho.com/categories/srwsesh",
        ],
        "link_pattern": "/article/",
    },
    {
        "name": "News Vision BD",
        "type": "scrape",
        "urls": [
            "https://newsvisionbd.com/?s=%E0%A6%95%E0%A7%81%E0%A6%AE%E0%A6%BF%E0%A6%B2%E0%A7%8D%E0%A6%B2%E0%A6%BE+%E0%A6%AC%E0%A6%BF%E0%A6%B6%E0%A7%8D%E0%A6%AC%E0%A6%AC%E0%A6%BF%E0%A6%A6%E0%A7%8D%E0%A6%AF%E0%A6%BE%E0%A6%B2%E0%A7%9F",
            "https://newsvisionbd.com/?s=%E0%A6%95%E0%A7%81%E0%A6%AC%E0%A6%BF",
        ],
        "link_pattern": None,  # সব লিংক নেবে
    },
    {
        "name": "বাংলা ট্রিবিউন",
        "type": "scrape",
        "urls": [
            "https://www.banglatribune.com/topic/%E0%A6%95%E0%A7%81%E0%A6%AE%E0%A6%BF%E0%A6%B2%E0%A7%8D%E0%A6%B2%E0%A6%BE-%E0%A6%AC%E0%A6%BF%E0%A6%B6%E0%A7%8D%E0%A6%AC%E0%A6%AC%E0%A6%BF%E0%A6%A6%E0%A7%8D%E0%A6%AF%E0%A6%BE%E0%A6%B2%E0%A7%9F",
        ],
        "link_pattern": "/my-campus/",
    },
    {
        "name": "সদ্য সংবাদ",
        "type": "rss",
        "rss_urls": [
            "https://soddosongbad.com/feed/",
            "https://soddosongbad.com/rss/",
        ],
    },
    {
        "name": "বার্তা বাজার",
        "type": "rss",
        "rss_urls": [
            "https://www.bartabazer.com/feed/",
            "https://www.bartabazer.com/rss/",
        ],
    },
    {
        "name": "BD Telegraph 24",
        "type": "scrape",
        "urls": [
            "https://bdtelegraph24.com/?s=%E0%A6%95%E0%A7%81%E0%A6%AE%E0%A6%BF%E0%A6%B2%E0%A7%8D%E0%A6%B2%E0%A6%BE+%E0%A6%AC%E0%A6%BF%E0%A6%B6%E0%A7%8D%E0%A6%AC%E0%A6%AC%E0%A6%BF%E0%A6%A6%E0%A7%8D%E0%A6%AF%E0%A6%BE%E0%A6%B2%E0%A7%9F",
            "https://bdtelegraph24.com/?s=%E0%A6%95%E0%A7%81%E0%A6%AC%E0%A6%BF",
        ],
        "link_pattern": None,
    },
    {
        "name": "দৈনিক সকালের সময়",
        "type": "rss",
        "rss_urls": [
            "https://dailysokalersomoy.com/feed/",
            "https://dailysokalersomoy.com/rss/",
        ],
    },
]

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

def is_relevant(title: str) -> bool:
    return any(kw.lower() in title.lower() for kw in KEYWORDS)

def is_first_run() -> bool:
    return not os.path.exists(SENT_FILE)

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

def get_article_date(url: str):
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        for meta in soup.find_all("meta"):
            prop = meta.get("property", "") + meta.get("name", "")
            if "published_time" in prop or "date" in prop.lower():
                content = meta.get("content", "")
                if content:
                    try:
                        return datetime.fromisoformat(content[:19])
                    except:
                        pass
        time_tag = soup.find("time")
        if time_tag:
            dt = time_tag.get("datetime", "")
            if dt:
                try:
                    return datetime.fromisoformat(dt[:19])
                except:
                    pass
    except:
        pass
    return None

# ─── SCRAPERS ──────────────────────────────────────────────────────────────────

def scrape_page(site: dict) -> list:
    results = []
    seen = set()

    for url in site["urls"]:
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")

            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"]
                title = a_tag.get_text(strip=True)

                # link pattern filter
                if site["link_pattern"] and site["link_pattern"] not in href:
                    continue

                # title minimum length
                if len(title) < 10:
                    continue

                # duplicate skip
                if href in seen:
                    continue
                seen.add(href)

                if not href.startswith("http"):
                    base = site["urls"][0].split("/")[0] + "//" + site["urls"][0].split("/")[2]
                    href = base + href

                results.append({
                    "title":    title,
                    "url":      href,
                    "source":   site["name"],
                    "pub_date": None,
                })

            print(f"[SCRAPE] {site['name']} | {url} → {len(results)} items")

        except Exception as e:
            print(f"[SCRAPE ERROR] {site['name']} | {url} → {e}")

    return results


def scrape_rss(site: dict) -> list:
    results = []
    for rss_url in site["rss_urls"]:
        try:
            feed = feedparser.parse(rss_url)
            if not feed.entries:
                continue

            print(f"[RSS] {site['name']} → {len(feed.entries)} entries")

            for entry in feed.entries[:30]:
                title = entry.get("title", "").strip()
                link  = entry.get("link", "").strip()
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
                        "source":   site["name"],
                        "pub_date": pub_date,
                    })
            break
        except Exception as e:
            print(f"[RSS ERROR] {site['name']} | {rss_url} → {e}")

    if not results:
        print(f"[RSS FAIL] {site['name']}")
    return results

# ─── MAIN CHECK ────────────────────────────────────────────────────────────────

def check_news(first_run: bool = False):
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] চেক শুরু...")
    sent = load_sent()
    new_count = 0
    cutoff = datetime.now() - timedelta(hours=24)

    if first_run:
        send_telegram(
            "✅ <b>কুবি নিউজ বট চালু হয়েছে!</b>\n"
            "🕐 গত ২৪ ঘন্টার নিউজ খোঁজা হচ্ছে...\n"
            f"প্রতি {CHECK_EVERY} মিনিটে আপডেট পাবেন।"
        )

    def process(item):
        nonlocal new_count
        uid = make_id(item["url"])
        if uid in sent:
            return
        if not is_relevant(item["title"]):
            return

        if first_run:
            pub_date = item.get("pub_date") or get_article_date(item["url"])
            if pub_date and pub_date < cutoff:
                sent.add(uid)
                return
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

    for site in SITES:
        if site["type"] == "scrape":
            for item in scrape_page(site):
                process(item)
        else:
            for item in scrape_rss(site):
                process(item)

    save_sent(sent)

    if first_run and new_count == 0:
        send_telegram("ℹ️ গত ২৪ ঘন্টায় কুমিল্লা বিশ্ববিদ্যালয় সম্পর্কিত কোনো নিউজ পাওয়া যায়নি।")

    print(f"✅ চেক শেষ। নতুন: {new_count}টি")

# ─── RUN ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("🤖 কুবি নিউজ বট চালু হচ্ছে...")
    first = is_first_run()
    check_news(first_run=first)
    schedule.every(CHECK_EVERY).minutes.do(check_news, first_run=False)
    while True:
        schedule.run_pending()
        time.sleep(30)
