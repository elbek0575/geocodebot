import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.filters import CommandStart, Command
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramBadRequest

load_dotenv()
TOKEN = os.getenv("GEOCODE_BOT_TOKEN") or os.getenv("BOT_TOKEN")
if not TOKEN:
    raise SystemExit("❌ BOT_TOKEN topilmadi (.env ichiga GEOCODE_BOT_TOKEN=...).")

bot = Bot(TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()


def fmt_coord(lat: float, lon: float) -> str:
    return f"{lat:.6f}, {lon:.6f}"


def now_tashkent_str() -> str:
    try:
        return datetime.now(ZoneInfo("Asia/Tashkent")).strftime("%H:%M")
    except Exception:
        return datetime.now().strftime("%H:%M")


@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "👋 Салом! Геокод-бот тайёр.\n"
        "📍 Локация юборинг — координатани матн қилиб қайтараман."
    )


@dp.message(Command("help"))
async def help_cmd(message: Message):
    await message.answer(
        "ℹ️ Оддий: чатга Location юборинг. Мен эса координатани матн кўринишида жўнатаман."
    )


# 5 дақиқалик оддий TTL-кеш
_SEEN: dict[str, float] = {}


def _seen_once(message: Message, ttl_sec: int = 300) -> bool:
    now = time.time()
    # эскиларни тозалаш
    for k, t in list(_SEEN.items()):
        if now - t > ttl_sec:
            del _SEEN[k]
    key = f"{message.chat.id}:{message.message_id}"
    if key in _SEEN:
        return True
    _SEEN[key] = now
    return False


@dp.message(F.text)
async def handle_suv_kerak_trigger(message: Message):
    # Фақат group/supergroup’да ишласин
    if message.chat.type not in ("group", "supergroup"):
        return

    txt = (message.text or "").strip().lower()
    if not txt:
        return

    # Триггер сўзлар (матннинг ичида учраса ҳам бўлади)
    triggers = ("сув керак", "suv kerak")

    if not any(t in txt for t in triggers):
        return

    user_id = message.from_user.id if message.from_user else message.chat.id

    reply_text = (
        "👤 <b>USER_ID:</b>\n"
        f"<code>{user_id}</code>"
    )

    try:
        await message.reply(reply_text)
    except TelegramBadRequest:
        await message.answer(reply_text)


@dp.message(F.location)
async def handle_location(message: Message):
    if _seen_once(message):
        return  # 🔒 дубликат келса — ингор қилиб қўямиз

    lat = message.location.latitude
    lon = message.location.longitude
    coords = fmt_coord(lat, lon)

    # ✅ USER_ID (Telegram user id)
    user_id = message.from_user.id if message.from_user else message.chat.id

    text = (
        "📍 <b>Мижоз координаталари:</b>\n\n"
        f"<code>{coords}</code>\n\n"
        "👤 <b>USER_ID:</b>\n"
        f"<code>{user_id}</code>\n"
    )

    try:
        await message.reply(text)
    except TelegramBadRequest:
        await message.answer(text)
