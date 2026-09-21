import os
import re
import json
import html
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
TZ = ZoneInfo("Europe/Paris")
STATE_FILE = "seen.json"

CALENDAR_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
RSS_FEEDS = {
    "CNBC": "https://www.cnbc.com/id/20910258/device/rss/rss.html",
    "MarketWatch": "https://feeds.content.dowjones.io/public/rss/mw_topstories",
}
ALERT_MINUTES = 30

# Seuls les titres contenant un de ces mots sont envoyés.
# Mets KEYWORDS = None pour recevoir tous les titres.
KEYWORDS = re.compile(
    r"\b(fed|inflation|cpi|ppi|rates?|jobs?|payrolls?|gdp|ecb|powell|"
    r"tariffs?|recession|oil|treasur(y|ies)|yields?|unemployment|"
    r"economy|economic)\b",
    re.I,
)


def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def save_state(seen):
    with open(STATE_FILE, "w") as f:
        json.dump(seen[-1000:], f)


def check_calendar(seen, alerts):
    now = datetime.now(TZ)
    try:
        events = requests.get(CALENDAR_URL, timeout=15).json()
    except Exception:
        return
    for e in events:
        if e.get("impact") != "High":
            continue
        dt = datetime.fromisoformat(e["date"]).astimezone(TZ)
        if not (now - timedelta(minutes=5) <= dt <= now + timedelta(minutes=ALERT_MINUTES)):
            continue
        key = f"cal|{e['country']}|{e['title']}|{e['date']}"
        if key in seen:
            continue
        seen.append(key)
        mins = int((dt - now).total_seconds() // 60)
        when = f"dans ~{mins} min" if mins > 0 else "maintenant"
        extra = []
        if e.get("forecast"):
            extra.append(f"prév. {e['forecast']}")
        if e.get("previous"):
            extra.append(f"préc. {e['previous']}")
        extra_txt = f" ({', '.join(extra)})" if extra else ""
        alerts.append(
            f"⏰🔴 <b>{html.escape(e['country'])}</b> – "
            f"{html.escape(e['title'])} à {dt:%H:%M} ({when})"
            f"{html.escape(extra_txt)}"
        )


def check_news(seen, alerts):
    headers = {"User-Agent": "Mozilla/5.0"}
    for name, url in RSS_FEEDS.items():
        try:
            r = requests.get(url, headers=headers, timeout=15)
            items = ET.fromstring(r.content).findall(".//item")
        except Exception:
            continue
        for it in items:
            link = (it.findtext("link") or "").strip()
            title = (it.findtext("title") or "").strip()
            key = "news|" + link
            if not link or key in seen:
                continue
            seen.append(key)
            if KEYWORDS and not KEYWORDS.search(title):
                continue
            alerts.append(
                f'📰 {html.escape(name)} : <a href="{html.escape(link)}">'
                f"{html.escape(title)}</a>"
            )


def send(text):
    chunks, current = [], ""
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > 3800:
            chunks.append(current)
            current = ""
        current += line + "\n"
    if current:
        chunks.append(current)
    for chunk in chunks:
        r = requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={
                "chat_id": CHAT_ID,
                "text": chunk,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=15,
        )
        r.raise_for_status()


if __name__ == "__main__":
    seen = load_state()
    first_run = seen is None
    seen = seen or []
    alerts = []
    check_calendar(seen, alerts)
    check_news(seen, alerts)
    save_state(seen)

    if first_run:
        send("✅ Surveillance activée : tu recevras uniquement les nouveautés.")
    elif alerts:
        send("🚨 <b>Nouveau</b>\n\n" + "\n\n".join(alerts))
