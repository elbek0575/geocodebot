import os
import logging
from fastapi import FastAPI, Request
from aiogram.types import Update
from bot import dp, bot, TOKEN

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="geo_codebot")

# Webhook URL: BASE + PATH (PATH’ни токеннинг биринчи қисми билан “сирли” қиламиз)
WEBHOOK_BASE = os.getenv("WEBHOOK_BASE", "").rstrip("/")
WEBHOOK_PATH = f"/webhook/{TOKEN.split(':')[0]}"

@app.on_event("startup")
async def on_startup():
    if not WEBHOOK_BASE:
        raise RuntimeError("WEBHOOK_BASE environment variable not set")
    # app.py: on_startup()
    await bot.set_webhook(url=WEBHOOK_BASE + WEBHOOK_PATH, drop_pending_updates=True)
    logging.info("✅ Webhook set to %s", WEBHOOK_BASE + WEBHOOK_PATH)

@app.on_event("shutdown")
async def on_shutdown():
    await bot.delete_webhook(drop_pending_updates=True)

@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.model_validate(data, context={"bot": bot})
    await dp.feed_update(bot, update)
    return {"ok": True}
