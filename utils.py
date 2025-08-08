import re
import ssl
import certifi
import aiohttp
import json
from urllib.parse import urlparse, parse_qs
from datetime import datetime, date
from pathlib import Path

LINK_DATA_FILE = Path("link_data.json")

# -----------------------------
# Проверка типа ссылки
# -----------------------------
def detect_link_type(url: str) -> int:
    if "cabinet.tax.gov.ua" in url:
        return 1
    elif "receipt.silpo.elkasa.com.ua" in url:
        return 2
    elif "receipt.fora.elkasa.com.ua" in url:
        return 3
    return 0

# -----------------------------
# Проверка на дубликаты
# -----------------------------
def is_duplicate(url: str) -> bool:
    if not LINK_DATA_FILE.exists():
        return False
    with open(LINK_DATA_FILE, "r") as f:
        data = json.load(f)
    return any(link["url"] == url for link in data)

# -----------------------------
# Сохранить ссылку с данными
# -----------------------------
def save_link_data(new_link: dict):
    all_data = []
    if LINK_DATA_FILE.exists():
        with open(LINK_DATA_FILE, "r") as f:
            all_data = json.load(f)
    all_data.append(new_link)
    with open(LINK_DATA_FILE, "w") as f:
        json.dump(all_data, f, indent=2, ensure_ascii=False)


# -----------------------------
# Загрузить все сохранённые ссылки
# -----------------------------
def load_link_data() -> list:
    if LINK_DATA_FILE.exists():
        with open(LINK_DATA_FILE, "r") as f:
            return json.load(f)
    return []

# -----------------------------
# Извлечение даты из ссылки tax.gov.ua
# -----------------------------
def get_date_from_url(url: str) -> str:
    parsed_url = urlparse(url)
    query = parse_qs(parsed_url.query)
    if "date" in query:
        date_str = query["date"][0]
        return datetime.strptime(date_str, "%Y%m%d").strftime("%d.%m.%Y")
    return None

# -----------------------------
# Парсинг строки даты в объект
# -----------------------------
def parse_date_from_string(date_str: str) -> datetime:
    return datetime.strptime(date_str, "%d.%m.%Y")

# -----------------------------
# Получить дату из HTML страницы (Silpo, Fora)
# -----------------------------
from bs4 import BeautifulSoup  # если ещё не импортирован вверху

async def get_date_from_html(url: str) -> str:
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, ssl=ssl_context) as response:
                html = await response.text()
    except Exception as e:
        raise ValueError(f"Ошибка при запросе: {e}")

    soup = BeautifulSoup(html, "html.parser")
    all_tds = soup.find_all("td", class_="device-info-line-item")

    for i, td in enumerate(all_tds):
        if "ЧАС" in td.get_text(strip=True):
            if i + 1 < len(all_tds):
                time_str = all_tds[i + 1].get_text(strip=True)
                return time_str  # формат: '22:51:16 30.07.2025'

    raise ValueError("Дата не найдена в HTML")


# -----------------------------
# Отфильтровать ссылки по дате
# -----------------------------
def get_links_for_period(start_date: date, links: list) -> list:
    """
    Отбирает ссылки из ``links`` с датой не раньше ``start_date``.

    Parameters
    ----------
    start_date: date
        Дата, начиная с которой нужно включать ссылки.
    links: list
        Список словарей со ссылками и полем ``date_str``.

    Returns
    -------
    list
        Список URL, удовлетворяющих условию.
    """

    result = []

    for link in links:
        try:
            date_str = link.get("date_str", "")
            # В строке может присутствовать время, поэтому берём последнюю часть
            date_part = date_str.split()[-1]
            link_date = datetime.strptime(date_part, "%d.%m.%Y").date()

            if link_date >= start_date:
                result.append(link["url"])
        except Exception as e:
            print(f"Ошибка при обработке даты ссылки: {e}")

    return result
