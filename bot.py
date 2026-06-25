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
CHECK_EVERY = 3  # মিনিট

KEYWORDS = [
    "কুমিল্লা বিশ্ববিদ্যালয়", "কুবি", "কু.বি",
    "comilla university", "cu student", "cu campus",
]

# ─── সাধারণ সাইট (BeautifulSoup দিয়ে scrape হবে) ─────────────────────────────
SCRAPE_SITES = [
    {
        "name": "NewsvisionBD",
        "url":  "https://newsvisionbd.com",
        "search_url": "https://newsvisionbd.com/?s={query}",
        "article_selector": "article",
        "title_selector":   "h2,h3",
    },
{
        "name": "Daily Gonokantho",
        "url":  "https://dailygonokantho.com",
        "search_url": "https://dailygonokantho.com/categories/srwsesh",  # সর্বশেষ পেজ
        "article_selector": "a[href*='/article/']",  # /article/ দিয়ে সব লিংক
        "title_selector":   "a[href*='/article/']",
    },
    {
        "name": "BD Telegraph 24",
        "url":  "https://bdtelegraph24.com",
        "search_url": "https://bdtelegraph24.com/?s={query}",
        "article_selector": "article,.post,.news-item",
        "title_selector":   "h2,h3,h4",
    },
]

# ─── RSS সাইট (feedparser দিয়ে চলবে) ─────────────────────────────────────────
RSS_SITES = [
    {
        "name": "Daily Sokaler Somoy",
        "url":  "https://dailysokalersomoy.com",
        "rss_candidates": [
            "https://dailysokalersomoy.com/feed/",
            "https://dailysokalersomoy.com/rss/",
            "https://dailysokalersomoy.com/feed/rss/",
        ],
    },
]

SEARCH_QUERIES = [
    "কুমিল্লা+বিশ্ববিদ্যালয়",
    "কুবি", "comilla+university",
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

def is_relevant(title: str) -> bool:
    return any(kw.lower() in title.lower() for kw in KEYWORDS)

def is_first_run() -> bool:
    return not os.path.exists(SENT_FILE)

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

def get_article_date(url: str) -> datetime | None:
    """আর্টিকেলের published date বের করার চেষ্টা"""
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")

        # meta tag চেক
        for meta in soup.find_all("meta"):
            prop = meta.get("property", "") + meta.get("name", "")
            if "published_time" in prop or "date" in prop.lower():
                content = meta.get("content", "")
                if content:
                    try:
                        return datetime.fromisoformat(content[:19])
                    except:
                        pass

        # time ট্যাগ চেক
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

def scrape_site(site: dict, query: str) -> list[dict]:
    """BeautifulSoup দিয়ে সাধারণ সাইট scrape করবে"""
    results = []
    search_url = site["search_url"].format(query=query)
    try:
        r = requests.get(search_url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        articles = soup.select(site["article_selector"])
        if not articles:
            articles = soup.select(".td-module-container, .jeg_post, .post, article")

        for art in articles[:10]:
            t_el = art.select_one(site["title_selector"])
            if not t_el:
                continue
            title = t_el.get_text(strip=True)

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


def scrape_rss(site: dict) -> list[dict]:
    """RSS feed দিয়ে Next.js সাইট থেকে নিউজ আনবে"""
    results = []
    for rss_url in site["rss_candidates"]:
        try:
            feed = feedparser.parse(rss_url)
            if not feed.entries:
                continue

            print(f"[RSS OK] {site['name']} → {rss_url} ({len(feed.entries)} entries)")

            for entry in feed.entries[:30]:
                title = entry.get("title", "").strip()
                link  = entry.get("link", "").strip()

                # RSS থেকে published date বের করার চেষ্টা
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
            break  # একটা কাজ করলেই থামবে

        except Exception as e:
            print(f"[RSS ERROR] {site['name']} | {rss_url} → {e}")
            continue

    if not results:
        print(f"[RSS FAIL] {site['name']} — কোনো feed কাজ করেনি")

    return results

# ─── MAIN CHECK ────────────────────────────────────────────────────────────────

def check_news(first_run: bool = False):
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] নিউজ চেক শুরু হচ্ছে...")
    sent     = load_sent()
    new_count = 0
    cutoff   = datetime.now() - timedelta(hours=24)

    if first_run:
        send_telegram(
            "✅ <b>কুবি নিউজ বট চালু হয়েছে!</b>\n"
            "🕐 গত ২৪ ঘন্টার নিউজ খোঁজা হচ্ছে...\n"
            f"প্রতি {CHECK_EVERY} মিনিটে নতুন নিউজ চেক করবে।"
        )

    # ── ১. সাধারণ সাইট scrape ─────────────────────────────────────────────────
    for site in SCRAPE_SITES:
        for query in SEARCH_QUERIES:
            items = scrape_site(site, query)
            for item in items:
                uid = make_id(item["url"])
                if uid in sent or not is_relevant(item["title"]):
                    continue

                if first_run:
                    pub_date = get_article_date(item["url"])
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

    # ── ২. RSS সাইট (Daily Sokaler Somoy ইত্যাদি) ────────────────────────────
    for site in RSS_SITES:
        items = scrape_rss(site)
        for item in items:
            uid = make_id(item["url"])
            if uid in sent or not is_relevant(item["title"]):
                continue

            if first_run:
                # RSS-এ pub_date সরাসরি আছে — get_article_date() লাগবে না
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
