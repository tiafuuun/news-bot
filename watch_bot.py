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
# jaune = faible, gris = non économique
COLORS = {"High": "🔴", "Medium": "🟠", "
