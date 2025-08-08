import asyncio
import logging
import os
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, Router, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from utils import (
    detect_link_type,
    load_link_data,
    save_link_data,
    get_date_from_url,
    get_date_from_html,
    get_links_for_period,
)

from parser import parse_link  # твоя асинхронная обёртка

BOT_TOKEN = "8294766394:AAEBnzx9T9tppaNYnVAjOIavu3M1eBlEkzk"

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
router = Router()
dp.include_router(router)


@router.message(Command("start"))
async def cmd_start(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 Обработать чеки", callback_data="process")],
    ])
    await message.answer("Привет! Отправь ссылку на чек или выбери действие:", reply_markup=kb)



@router.message()
async def handle_link(message: Message):
    url = message.text.strip()

    try:
        link_type = detect_link_type(url)
    except ValueError:
        return await message.answer("❌ Это не ссылка на чек.\nПоддерживаются: tax.gov.ua, Silpo, Fora.")

    data = load_link_data()

    if any(entry["url"] == url for entry in data):
        return await message.answer("⚠️ Эта ссылка уже есть в базе.")

    try:
        if link_type == 1:
            date_str = get_date_from_url(url)
        else:
            date_str = await get_date_from_html(url)
    except Exception as e:
        return await message.answer(f"⚠️ Не удалось определить дату чека: {e}")

    link_data = {
        "url": url,
        "type": link_type,
        "date_str": date_str,
        "status": "pending"
    }
   
    data.append(link_data)
    save_link_data(link_data)

    await message.answer(f"✅ Ссылка добавлена!\nТип: {link_type}\nДата: {date_str}")



@router.callback_query(F.data == "process")
async def handle_process_query(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Сегодня", callback_data="period_today")],
        [InlineKeyboardButton(text="📆 Вчера", callback_data="period_yesterday")],
        [InlineKeyboardButton(text="📈 Прошлая неделя", callback_data="period_last_week")],
        [InlineKeyboardButton(text="📊 Прошлый месяц", callback_data="period_last_month")]
    ])
    await callback.message.answer("Выбери период для обработки чеков:", reply_markup=kb)


@router.callback_query(F.data.startswith("period_"))
async def handle_period(callback: CallbackQuery):
    period = callback.data.replace("period_", "")
    now = datetime.now()

    if period == "today":
        start_date = now.date()
    elif period == "yesterday":
        start_date = (now - timedelta(days=1)).date()
    elif period == "last_week":
        start_date = (now - timedelta(days=7)).date()
    elif period == "last_month":
        start_date = (now - timedelta(days=30)).date()
    else:
        return await callback.message.answer("❌ Неверный период")

    await callback.message.answer("⏳ Начинаю обработку чеков...")

    link_data = load_link_data()
    selected_links = get_links_for_period(start_date, link_data)

    total = len(selected_links)
    success = 0
    pending = 0

    for url in selected_links:
        try:
            result = await parse_link(url)
            if result:
                link_data[url]["status"] = "done"
                success += 1
            else:
                link_data[url]["status"] = "pending"
                pending += 1
                await callback.message.answer(f"🕓 Ссылка ещё не сформирована: {url}\nДобавлена в отложенные")
        except Exception as e:
            link_data[url]["status"] = "pending"
            pending += 1
            await callback.message.answer(f"⚠️ Ошибка при обработке: {url}\n{e}")

    save_link_data(link_data)

    await callback.message.answer(
        f"✅ Обработано: {success} чеков\n🕓 Добавлено в отложенные: {pending}\n📦 Всего за период: {total}"
    )

    if os.path.exists("Result.xlsx"):
        await callback.message.answer_document(FSInputFile("Result.xlsx"))


async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
