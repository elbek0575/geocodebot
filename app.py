import os
import logging
import asyncio
from typing import Optional

from fastapi import FastAPI, Request
from aiogram.types import Update

from bot import dp, bot, TOKEN

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("geo_codebot")

app = FastAPI(title="geo_codebot")

# ====== Режимлар ======
# BOT_MODE=webhook  -> production (Heroku)
# BOT_MODE=polling  -> local dev
BOT_MODE = (os.getenv("BOT_MODE") or "").strip().lower()  # webhook|polling|""


# Webhook URL: BASE + PATH (PATH’ни токеннинг биринчи қисми билан “сирли” қиламиз)
WEBHOOK_BASE = (os.getenv("WEBHOOK_BASE") or "").strip().rstrip("/")
WEBHOOK_PATH = (os.getenv("WEBHOOK_PATH") or f"/webhook/{TOKEN.split(':')[0]}").strip()

_polling_task: Optional[asyncio.Task] = None


def _is_valid_webhook_base(url: str) -> bool:
    """Telegram webhook учун минимал текширув (public https бўлиши керак)."""
    if not url:
        return False
    url_l = url.lower()
    if not url_l.startswith("https://"):
        return False
    # local hostлар Telegram'га ўтмайди
    bad_hosts = ("127.0.0.1", "0.0.0.0", "localhost")
    return not any(h in url_l for h in bad_hosts)


def _resolve_mode() -> str:
    """
    Агар BOT_MODE берилган бўлса — шу.
    Акс ҳолда:
      - WEBHOOK_BASE valid бўлса -> webhook
      - акс ҳолда -> polling
    """
    if BOT_MODE in {"webhook", "polling"}:
        return BOT_MODE
    return "webhook" if _is_valid_webhook_base(WEBHOOK_BASE) else "polling"


@app.on_event("startup")
async def on_startup():
    global _polling_task

    mode = _resolve_mode()
    logger.info("🚀 Startup. mode=%s", mode)

    if mode == "webhook":
        if not _is_valid_webhook_base(WEBHOOK_BASE):
            raise RuntimeError(
                "WEBHOOK_BASE нотўғри. Telegram webhook учун public HTTPS URL керак.\n"
                "Мисол: WEBHOOK_BASE=https://<app>.herokuapp.com"
            )

        webhook_url = WEBHOOK_BASE + WEBHOOK_PATH
        await bot.set_webhook(url=webhook_url, drop_pending_updates=True)
        logger.info("✅ Webhook set: %s", webhook_url)

    else:
        # polling mode: webhook қўймаймиз
        try:
            await bot.delete_webhook(drop_pending_updates=True)
        except Exception:
            pass

        # polling’ни background task қилиб юбориш
        _polling_task = asyncio.create_task(dp.start_polling(bot))
        logger.info("✅ Polling started (background task).")


@app.on_event("shutdown")
async def on_shutdown():
    global _polling_task

    mode = _resolve_mode()
    logger.info("🛑 Shutdown. mode=%s", mode)

    # Polling’ни тўхтатиш
    if _polling_task and not _polling_task.done():
        _polling_task.cancel()
        try:
            await _polling_task
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning("Polling task stop error: %s", e)

    # Webhook cleanup
    if mode == "webhook":
        try:
            await bot.delete_webhook(drop_pending_updates=True)
        except Exception as e:
            logger.warning("delete_webhook error: %s", e)

    # Aiogram session’ни ёпиш
    try:
        await bot.session.close()
    except Exception:
        pass


@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    """
    Webhook режимида Telegram update қабул қилади.
    Polling режимида ҳам endpoint турса зарар қилмайди, лекин Telegram унга урмайди.
    """
    data = await request.json()
    update = Update.model_validate(data, context={"bot": bot})
    await dp.feed_update(bot, update)
    return {"ok": True}


@app.get("/health")
def health():
    return {
        "ok": True,
        "mode": _resolve_mode(),
        "webhook_base": WEBHOOK_BASE,
        "webhook_path": WEBHOOK_PATH,
    }
