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
    "CNBC Économie": "https://www.cnbc.com/id/20910258/device/rss/rss.html",
    "MarketWatch": "https://feeds.content.dowjones.io/public/rss/mw_topstories",
}
NEWS_PER_FEED = 5
IMPACTS = {"High": "🔴", "Medium": "🟠"}


def get_calendar() -> str:
    today = datetime.now(TZ).date()
    events = requests.get(CALENDAR_URL, timeout=15).json()
    lines = []
    for e in events:
        if e.get("impact") not in IMPACTS:
            continue
        dt = datetime.fromisoformat(e["date"]).astimezone(TZ)
        if dt.date() != today:
            continue
        lines.append((dt, e))
    lines.sort(key=lambda x: x[0])

    out = [f"📅 <b>Calendrier éco du {today:%d/%m/%Y}</b>"]
    if not lines:
        out.append("Aucun événement important aujourd'hui.")
    for dt, e in lines:
        extra = []
        if e.get("forecast"):
            extra.append(f"prév. {e['forecast']}")
        if e.get("previous"):
            extra.append(f"préc. {e['previous']}")
        extra_txt = f" ({', '.join(extra)})" if extra else ""
        out.append(
            f"{IMPACTS[e['impact']]} {dt:%H:%M} <b>{html.escape(e['country'])}</b> "
            f"– {html.escape(e['title'])}{html.escape(extra_txt)}"
        )
    return "\n".join(out)


def get_news() -> str:
    out = ["📰 <b>Actus financières</b>"]
    headers = {"User-Agent": "Mozilla/5.0"}
    for name, url in RSS_FEEDS.items():
        try:
            r = requests.get(url, headers=headers, timeout=15)
            root = ET.fromstring(r.content)
            items = root.findall(".//item")[:NEWS_PER_FEED]
        except Exception as ex:
            out.append(f"\n<i>{name} : indisponible ({ex})</i>")
            continue
        out.append(f"\n<b>{html.escape(name)}</b>")
        for it in items:
            title = html.escape((it.findtext("title") or "").strip())
            link = (it.findtext("link") or "").strip()
            out.append(f'• <a href="{html.escape(link)}">{title}</a>')
    return "\n".join(out)


def send(text: str) -> None:
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
    send(get_calendar() + "\n\n" + get_news())
