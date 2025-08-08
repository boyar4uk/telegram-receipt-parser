import os
import re
import pandas as pd
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from utils import load_link_data

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

OUTPUT_FILE = "Result.xlsx"
all_items = []


def setup_driver():
    """Создаёт экземпляр Selenium Chrome"""
    options = Options()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(options=options)
    return driver
def get_fiscal_link_from_store(driver, store_url):
    """Открывает страницу Сильпо/Фора и берёт ссылку на фискальный чек"""
    print(f"[INFO] Открываю страницу магазина: {store_url}")
    driver.get(store_url)

    try:
        qr_div = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-code-type='QR']"))
        )
        fiscal_url = qr_div.get_attribute("data-render-data")
        if fiscal_url:
            print(f"[SUCCESS] Нашёл ссылку на фискальный чек: {fiscal_url}")
            return fiscal_url
        else:
            print("[ERROR] Не найден атрибут data-render-data")
            return None
    except Exception as e:
        print(f"[ERROR] Не удалось найти div с QR: {e}")
        return None


def parse_fiscal_receipt(driver, fiscal_url, check_num):
    """Открывает и парсит фискальный чек"""
    print(f"[INFO] Открываю фискальный чек: {fiscal_url}")
    driver.get(fiscal_url)

    # Дата из URL
    receipt_date = ""
    parsed_url = urlparse(fiscal_url)
    query_params = dict(qc.split("=") for qc in parsed_url.query.split("&") if "=" in qc)
    if "date" in query_params:
        raw_date = query_params["date"]
        receipt_date = f"{raw_date[6:8]}.{raw_date[4:6]}.{raw_date[0:4]}"

    # Ждём загрузки чека или капчи
    try:
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.TAG_NAME, "pre"))
        )
    except:
        print("[WARN] Блок <pre> не найден, пробую найти div с чеком")
        try:
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.XPATH, "//div[contains(text(), 'ЧЕК')]"))
            )
        except:
            print("[ERROR] Чек не загрузился. Возможно, проблема с капчей.")
            return []

    html_page = driver.page_source
    soup = BeautifulSoup(html_page, "html.parser")

    check_text_block = soup.find("pre")
    if not check_text_block:
        for div in soup.find_all("div"):
            if "ТОВ" in div.get_text() and "ЧЕК" in div.get_text():
                check_text_block = div
                break

    if not check_text_block:
        print("[ERROR] Не найден текст чека")
        return []

    lines = check_text_block.get_text("\n").split("\n")

    # Магазин
    shop_name = ""
    for line in lines:
        if line.strip().startswith("ТОВ "):
            shop_name = line.strip()
            break

    # Парсинг товаров
    items = []
    item_pattern = re.compile(r"^АРТ\.\№\s*(\d+)\s+(.+)$")
    qty_pattern = re.compile(r"(\d+[.,]?\d*)\s*x\s*(\d+[.,]?\d*)\s*=\s*(\d+[.,]?\d*)")

    current_item = None
    item_num_in_check = 0

    for line in lines:
        line = line.strip()
        if not line:
            continue

        m_item = item_pattern.match(line)
        if m_item:
            art_num = m_item.group(1)
            name = m_item.group(2).strip()
            item_num_in_check += 1
            current_item = {
                "Дата": receipt_date,
                "№": item_num_in_check,
                "Наименование товара": name,
                "Магазин": shop_name,
                "Штрих-код": art_num,
                "Источник": f'=HYPERLINK("{fiscal_url}", "чек{check_num}")'
            }
            continue

        m_qty = qty_pattern.search(line)
        if m_qty and current_item:
            qty_val = m_qty.group(1).replace(".", ",")
            current_item["Количество"] = qty_val
            current_item["Ед. изм."] = "шт"

            current_item["Ед. изм."] = "шт"
            current_item["Цена за ед. (грн)"] = m_qty.group(2).replace(".", ",")
            current_item["Сумма (грн)"] = m_qty.group(3).replace(".", ",")
            items.append(current_item)
            current_item = None

    print(f"[SUCCESS] Найдено {len(items)} товаров")
    return items


def main():
    link_entries = load_link_data()
    links = [entry["url"] for entry in link_entries]
    if not links:
        return

    # Нумерация чеков по уникальным ссылкам
    link_map = {link: i + 1 for i, link in enumerate(links)}

    driver = setup_driver()

    for link in links:
        try:
            if "cabinet.tax.gov.ua" in link:
                items = parse_fiscal_receipt(driver, link, link_map[link])
                all_items.extend(items)

            elif "receipt.silpo.elkasa.com.ua" in link or "receipt.fora.elkasa.com.ua" in link:
                fiscal_url = get_fiscal_link_from_store(driver, link)
                if fiscal_url:
                    items = parse_fiscal_receipt(driver, fiscal_url, link_map[link])
                    all_items.extend(items)
                else:
                    print("[ERROR] Не удалось получить ссылку на фискальный чек")

            else:
                print(f"[WARN] Неизвестный тип ссылки: {link}")

        except Exception as e:
            print(f"[ERROR] Ошибка при обработке {link}: {e}")

    driver.quit()

    if all_items:
        df = pd.DataFrame(all_items)
        # Порядок колонок
        df = df[["Дата", "№", "Наименование товара", "Количество", "Ед. изм.",
                 "Цена за ед. (грн)", "Сумма (грн)", "Штрих-код", "Магазин", "Источник"]]
        df.to_excel(OUTPUT_FILE, index=False)
        print(f"[SUCCESS] Данные сохранены в {OUTPUT_FILE}")
    else:
        print("[INFO] Не найдено ни одной позиции.")


if __name__ == "__main__":
    main()

def parse_and_save_one(url: str, check_number: int) -> bool:
    driver = setup_driver()
    try:
        if "cabinet.tax.gov.ua" in url:
            items = parse_fiscal_receipt(driver, url, check_number)
        elif "receipt.silpo.elkasa.com.ua" in url or "receipt.fora.elkasa.com.ua" in url:
            fiscal_url = get_fiscal_link_from_store(driver, url)
            if not fiscal_url:
                return False
            items = parse_fiscal_receipt(driver, fiscal_url, check_number)
        else:
            return False

        if not items:
            return False

        # Сохраняем в Excel
        if os.path.exists(OUTPUT_FILE):
            df_existing = pd.read_excel(OUTPUT_FILE)
            df_new = pd.DataFrame(items)
            df = pd.concat([df_existing, df_new], ignore_index=True)
        else:
            df = pd.DataFrame(items)

        df = df[["Дата", "№", "Наименование товара", "Количество", "Ед. изм.",
                 "Цена за ед. (грн)", "Сумма (грн)", "Штрих-код", "Магазин", "Источник"]]

        df.to_excel(OUTPUT_FILE, index=False)
        return True

    except Exception as e:
        print(f"[ERROR] Ошибка при обработке {url}: {e}")
        return False
    finally:
        driver.quit()

# 👇 вот это обязательно для Telegram-бота
async def parse_link(url: str) -> bool:
    try:
        data = load_link_data()
        links = [entry["url"] for entry in data]
        if url not in links:
            raise ValueError("Ссылка не найдена в link_data.json")
        check_number = links.index(url) + 1
        return parse_and_save_one(url, check_number)
    except Exception as e:
        print(f"[BOT ERROR] parse_link({url}): {e}")
        return False
