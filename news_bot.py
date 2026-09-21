import os
import html
import xml.etree.ElementTree as ET
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
TZ = ZoneInfo("Europe/Paris")

CALENDAR_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

RSS_FEEDS = {
    "CNBC": "https://www.cnbc.com/id/20910258/device/rss/rss.html",
    "MarketWatch": "https://feeds.content.dowjones.io/public/rss/mw_topstories",
    "Investing.com": "https://www.investing.com/rss/news_1.rss",
}
NEWS_PER_FEED = 5

# Couleurs comme ForexFactory : rouge = fort, orange = moyen,
# jaune = faible, gris = non economique
COLORS = {
    "High": "\U0001F534",
    "Medium": "\U0001F7E0",
    "Low": "\U0001F7E1",
    "Holiday": "\u26AA",
}


def get_calendar():
    today = datetime.now(TZ).date()
    out = ["\U0001F4C5 <b>Calendrier \u00e9co du " + today.strftime("%d/%m/%Y") + "</b>"]
    out.append(
        "\U0001F534 fort  \U0001F7E0 moyen  \U0001F7E1 faible  \u26AA non \u00e9conomique"
    )
    try:
        events = requests.get(CALENDAR_URL, timeout=15).json()
    except Exception:
        out.append("Calendrier indisponible pour le moment.")
        return "\n".join(out)

    lines = []
    for e in events:
        impact = e.get("impact")
        if impact not in COLORS:
            continue
        dt = datetime.fromisoformat(e["date"]).astimezone(TZ)
        if dt.date() != today:
            continue
        lines.append((dt, impact, e))
    lines.sort(key=lambda x: x[0])

    if not lines:
        out.append("Aucun \u00e9v\u00e9nement aujourd'hui.")
    for dt, impact, e in lines:
        extra = []
        if e.get("forecast"):
            extra.append("pr\u00e9v. " + e["forecast"])
        if e.get("previous"):
            extra.append("pr\u00e9c. " + e["previous"])
        extra_txt = " (" + ", ".join(extra) + ")" if extra else ""
        out.append(
            COLORS[impact]
            + " "
            + dt.strftime("%H:%M")
            + " <b>"
            + html.escape(e["country"])
            + "</b> \u2013 "
            + html.escape(e["title"])
            + html.escape(extra_txt)
        )
    return "\n".join(out)


def get_news():
    out = ["\U0001F4F0 <b>Actus financi\u00e8res</b>"]
    headers = {"User-Agent": "Mozilla/5.0"}
    for name, url in RSS_FEEDS.items():
        try:
            r = requests.get(url, headers=headers, timeout=15)
            root = ET.fromstring(r.content)
            items = root.findall(".//item")[:NEWS_PER_FEED]
        except Exception:
            out.append("\n<i>" + html.escape(name) + " : indisponible</i>")
            continue
        out.append("\n<b>" + html.escape(name) + "</b>")
        for it in items:
            title = html.escape((it.findtext("title") or "").strip())
            link = html.escape((it.findtext("link") or "").strip())
            out.append('\u2022 <a href="' + link + '">' + title + "</a>")
    return "\n".join(out)


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
            "https://api.telegram.org/bot" + TOKEN + "/sendMessage",
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
    send(get_calendar() + "\n\n" + get_news())
