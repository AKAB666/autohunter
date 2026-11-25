import asyncio
import os
import random
from urllib.parse import urlparse

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message
from dotenv import load_dotenv

from .db import init_db, add_watch, list_watches, remove_watch, get_all_watches, update_watch_price
from .feed import fetch_listings

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
POLL_SECONDS = max(60, int(os.getenv("POLL_SECONDS", "180")))

dp = Dispatcher()

def valid_http_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)

def rub(value):
    return f"{int(value):,}".replace(",", " ") + " ₽"

@dp.message(Command("start"))
async def start(message: Message):
    await message.answer(
        "🚗 <b>AutoHunter Russia</b>\n\n"
        "Слежение за объявлениями и уведомления об изменении цены.\n\n"
        "<b>Команды:</b>\n"
        "/watch Ссылка | Название | Цена\n"
        "/list — мои отслеживаемые машины\n"
        "/unwatch ID — убрать из отслеживания\n"
        "/game — мини-игра «Угадай стоимость»\n"
        "/help — помощь\n\n"
        "Пример:\n"
        "/watch https://example.ru/car/123 | Kia Rio | 850000",
        parse_mode="HTML"
    )

@dp.message(Command("help"))
async def help_cmd(message: Message):
    await start(message)

@dp.message(Command("watch"))
async def watch(message: Message):
    raw = message.text.partition(" ")[2].strip()
    parts = [p.strip() for p in raw.split("|")]
    if len(parts) < 2 or not valid_http_url(parts[0]):
        await message.answer("Формат: /watch Ссылка | Название | Цена\nЦена необязательна.")
        return
    price = None
    if len(parts) >= 3 and parts[2].isdigit():
        price = int(parts[2])
    await add_watch(message.from_user.id, parts[0], parts[1], price)
    await message.answer("⭐ Добавлено в отслеживание. Я сообщу, если источник передаст изменение цены.")

@dp.message(Command("list"))
async def list_cmd(message: Message):
    rows = await list_watches(message.from_user.id)
    if not rows:
        await message.answer("Пока нет отслеживаемых объявлений. Добавь через /watch.")
        return
    lines = ["⭐ <b>Твои объявления:</b>"]
    for wid, title, price, url in rows:
        p = rub(price) if price is not None else "цена не указана"
        lines.append(f"\n<b>#{wid} — {title}</b>\n{p}\n{url}")
    await message.answer("\n".join(lines), parse_mode="HTML", disable_web_page_preview=True)

@dp.message(Command("unwatch"))
async def unwatch(message: Message):
    raw = message.text.partition(" ")[2].strip()
    if not raw.isdigit():
        await message.answer("Укажи ID: /unwatch 3")
        return
    ok = await remove_watch(message.from_user.id, int(raw))
    await message.answer("Убрано из отслеживания." if ok else "Не нашёл объявление с таким ID.")


# Учебные примеры для мини-игры. Это демонстрационные оценки, не текущие рыночные котировки.
GAME_CARS = [
    {"title": "Lada Vesta", "year": 2020, "mileage": "85 000 км", "condition": "Хорошее",
     "estimate": 950000, "note": "Оценка зависит от комплектации, истории и региона."},
    {"title": "Kia Rio", "year": 2019, "mileage": "92 000 км", "condition": "Хорошее",
     "estimate": 1150000, "note": "Проверьте историю ДТП, обслуживание и юридическую чистоту."},
    {"title": "Toyota Camry", "year": 2017, "mileage": "130 000 км", "condition": "Удовлетворительное",
     "estimate": 1850000, "note": "Состояние и комплектация могут заметно изменить оценку."},
    {"title": "Hyundai Solaris", "year": 2021, "mileage": "70 000 км", "condition": "Хорошее",
     "estimate": 1250000, "note": "Проверьте кузов, обслуживание и работу коробки передач."},
    {"title": "Volkswagen Polo", "year": 2018, "mileage": "110 000 км", "condition": "Хорошее",
     "estimate": 1050000, "note": "Оценка учебная; регион и комплектация важны."},
]

@dp.message(Command("game"))
async def game(message: Message):
    car = random.choice(GAME_CARS)
    # Храним раунд в памяти процесса; для постоянной игры между перезапусками понадобится таблица БД.
    if not hasattr(dp, "game_rounds"):
        dp.game_rounds = {}
    dp.game_rounds[message.from_user.id] = car
    await message.answer(
        "🎮 <b>AutoHunter: Угадай стоимость!</b>\n\n"
        f"🚘 <b>{car['title']}</b>\n"
        f"Год: {car['year']}\nПробег: {car['mileage']}\n"
        f"Состояние: {car['condition']}\n\n"
        "Как думаешь, сколько стоит этот автомобиль в рублях?\n"
        "Отправь число, например: <code>1200000</code>.",
        parse_mode="HTML"
    )

@dp.message(F.text)
async def game_guess(message: Message):
    rounds = getattr(dp, "game_rounds", {})
    car = rounds.get(message.from_user.id)
    if not car:
        return
    raw = message.text.replace(" ", "").replace("₽", "").replace(",", "")
    if not raw.isdigit():
        return
    guess = int(raw)
    if guess <= 0:
        await message.answer("Введи положительную цену в рублях или начни игру командой /game.")
        return
    estimate = car["estimate"]
    diff = abs(guess - estimate)
    pct = diff / estimate * 100
    if pct <= 5:
        result = "🏆 Почти идеально! Ты отлично оценил автомобиль."
    elif pct <= 15:
        result = "👏 Хорошая оценка! Ты близко к ориентиру."
    elif pct <= 30:
        result = "🙂 Есть небольшая разница — учитывай комплектацию и состояние."
    else:
        result = "🔎 Большой разброс. Сравнивай несколько похожих объявлений."
    rounds.pop(message.from_user.id, None)
    await message.answer(
        f"{result}\n\n"
        f"🚘 {car['title']} ({car['year']})\n"
        f"Твоя оценка: <b>{rub(guess)}</b>\n"
        f"Ориентир AutoHunter: <b>{rub(estimate)}</b>\n"
        f"Разница: <b>{rub(diff)} ({pct:.1f}%)</b>\n\n"
        f"ℹ️ {car['note']}\n"
        "Это учебный пример, не оценка реального объявления. "
        "Для реальной оценки нужны актуальные сопоставимые предложения.\n\n"
        "Сыграть ещё раз: /game",
        parse_mode="HTML"
    )

async def monitor(bot: Bot):
    while True:
        try:
            listings = await fetch_listings()
            by_url = {x.get("url"): x for x in listings if x.get("url")}
            for user_id, url, title, old_price, last_notified in await get_all_watches():
                item = by_url.get(url)
                if not item or not isinstance(item.get("price"), (int, float)):
                    continue
                new_price = int(item["price"])
                if last_notified is not None and new_price != int(last_notified):
                    if new_price < int(last_notified):
                        delta = int(last_notified) - new_price
                        text = (f"📉 <b>Цена снижена!</b>\n{title}\n"
                                f"Было: {rub(last_notified)}\nСтало: {rub(new_price)}\n"
                                f"Экономия: {rub(delta)}\n{url}")
                    else:
                        text = (f"📈 <b>Цена изменилась</b>\n{title}\n"
                                f"Было: {rub(last_notified)}\nСтало: {rub(new_price)}\n{url}")
                    try:
                        await bot.send_message(user_id, text, parse_mode="HTML", disable_web_page_preview=False)
                    except Exception:
                        pass
                    await update_watch_price(user_id, url, new_price)
        except Exception as exc:
            print("Monitor error:", repr(exc))
        await asyncio.sleep(POLL_SECONDS)

async def main():
    if not TOKEN:
        raise RuntimeError("Set BOT_TOKEN in .env")
    await init_db()
    bot = Bot(TOKEN)
    asyncio.create_task(monitor(bot))
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
