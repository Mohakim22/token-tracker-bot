import os
import asyncio
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from aiohttp import web

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "7587320592:AAEE6LXgBjIhv7TsfAspZzI4U_RjY2jeaok")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://token-tracker-bot-worker.onrender.com/")
PORT = int(os.getenv("PORT", 10000))

logger.info(f"بدأ تشغيل السكربت! Token: {TOKEN}, Webhook: {WEBHOOK_URL}, Port: {PORT}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("وصل أمر /start!")
    await update.message.reply_text("مرحبًا بك في TokenTrackerBot!")

async def setup_application():
    logger.info("جاري إعداد تطبيق تيليجرام...")
    app = Application.builder().token(TOKEN).build()
    await app.bot.delete_webhook(drop_pending_updates=True)
    await app.bot.set_webhook(url=WEBHOOK_URL)
    logger.info("تم إعداد الـ Webhook!")
    app.add_handler(CommandHandler("start", start))
    return app

async def webhook_handler(request):
    logger.info(f"وصل طلب: {request.method} {request.path}")
    app = request.app["telegram_app"]
    if request.method == "POST":
        try:
            update = Update.de_json(await request.json(), app.bot)
            await app.process_update(update)
            return web.Response(text="OK")
        except Exception as e:
            logger.error(f"خطأ: {str(e)}")
            return web.Response(status=500)
    return web.Response(text="Hello from Root")

async def main():
    logger.info("دخلنا الدالة الرئيسية...")
    telegram_app = await setup_application()
    
    web_app = web.Application()
    web_app["telegram_app"] = telegram_app
    web_app.router.add_route("*", "/", webhook_handler)
    
    logger.info(f"جاري تشغيل السيرفر على بورت {PORT}...")
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"سيرفر شغال على بورت {PORT}")
    
    await asyncio.Event().wait()

if __name__ == "__main__":
    logger.info("بدأ تشغيل السكربت الرئيسي!")
    asyncio.run(main())