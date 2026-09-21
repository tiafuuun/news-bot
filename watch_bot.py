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
    "Investing.com": "https://www.investing.com/rss/news_1.rss",
}

# Couleurs comme ForexFactory : rouge = fort, orange = moyen,
# jaune = faible, gris = non economique
COLORS = {
    "High": "\U0001F534",
    "Medium": "\U0001F7E0",
    "Low": "\U0001F7E1",
    "Holiday": "\u26AA",
}
ALERT_IMPACTS = {"High", "Medium"}
ALERT_MINUTES = 30

# Seuls les titres contenant un de ces mots sont envoyes.
# Mets KEYWORDS = None pour recevoir tous les titres.
KEYWORDS = re.compile(
    r"\b(fed|fomc|inflation|cpi|ppi|pce|rates?|jobs?|payrolls?|gdp|"
    r"ecb|boj|boe|rba|pboc|snb|bank of japan|bank of england|"
    r"central bank|powell|lagarde|ueda|tariffs?|recession|oil|opec|"
    r"gold|yen|dollar|euro|sterling|yuan|china|treasur(y|ies)|yields?|"
    r"unemployment|economy|economic|sanctions?|war|ceasefire|stimulus|"
    r"forex)\b",
    re.I,
)


def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def save_state(seen):
    inits = [k for k in seen if k.startswith("init|")]
    others = [k for k in seen if not k.startswith("init|")][-1000:]
    with open(STATE_FILE, "w") as f:
        json.dump(inits + others, f)


def check_calendar(seen, alerts):
    now = datetime.now(TZ)
    try:
        events = requests.get(CALENDAR_URL, timeout=15).json()
    except Exception:
        return
    for e in events:
        impact = e.get("impact")
        if impact not in ALERT_IMPACTS:
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
            extra.append(f"pr\u00e9v. {e['forecast']}")
        if e.get("previous"):
            extra.append(f"pr\u00e9c. {e['previous']}")
        extra_txt = f" ({', '.join(extra)})" if extra else ""
        alerts.append(
            f"\u23F0{COLORS[impact]} <b>{html.escape(e['country'])}</b> \u2013 "
            f"{html.escape(e['title'])} \u00e0 {dt:%H:%M} ({when})"
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
        init_key = "init|" + name
        first_time = init_key not in seen
        for it in items:
            link = (it.findtext("link") or "").strip()
            title = (it.findtext("title") or "").strip()
            key = "news|" + link
            if not link or key in seen:
                continue
            seen.append(key)
            if first_time:
                continue
            if KEYWORDS and not KEYWORDS.search(title):
                continue
            alerts.append(
                f'\U0001F4F0 {html.escape(name)} : <a href="{html.escape(link)}">'
                f"{html.escape(title)}</a>"
            )
        if first_time:
            seen.append(init_key)


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
        send("\u2705 Surveillance activ\u00e9e : tu recevras uniquement les nouveaut\u00e9s.")
    elif alerts:
        send("\U0001F6A8 <b>Nouveau</b>\n\n" + "\n\n".join(alerts))
