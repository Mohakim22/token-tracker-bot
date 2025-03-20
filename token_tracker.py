import os
import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from aiohttp import web

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://token-tracker-bot-worker.onrender.com/webhook")
PORT = int(os.getenv("PORT", 10000))

logger.info("بدأ تشغيل السكربت!")
logger.info(f"التوكن: {TOKEN}")
logger.info(f"رابط الـ Webhook: {WEBHOOK_URL}")
logger.info(f"البورت: {PORT}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("وصل أمر /start من المستخدم!")
    logger.info(f"Update JSON: {update.to_json()}")
    keyboard = [
        [InlineKeyboardButton("إضافة توكن", callback_data="add_token")],
        [InlineKeyboardButton("عرض التوكنات", callback_data="list_tokens")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("مرحبًا بك في TokenTrackerBot!", reply_markup=reply_markup)

async def setup_application():
    logger.info("جاري إعداد تطبيق تيليجرام...")
    try:
        app = Application.builder().token(TOKEN).build()
        logger.info("جاري حذف الـ Webhook القديم...")
        await app.bot.delete_webhook(drop_pending_updates=True)
        logger.info("جاري إعداد الـ Webhook الجديد...")
        await app.bot.set_webhook(url=WEBHOOK_URL)
        logger.info("تم إعداد الـ Webhook بنجاح!")
        
        app.add_handler(CommandHandler("start", start))
        return app
    except Exception as e:
        logger.error(f"خطأ أثناء إعداد التطبيق: {str(e)}")
        raise

async def webhook_handler(request):
    logger.info("وصل طلب Webhook إلى المسار: %s", request.path)
    logger.info("طريقة الطلب: %s", request.method)
    app = request.app["telegram_app"]
    try:
        update = Update.de_json(await request.json(), app.bot)
        logger.info(f"Update JSON: {update.to_json()}")
        await app.process_update(update)
        return web.Response(text="OK")
    except Exception as e:
        logger.error(f"خطأ في معالجة الـ Webhook: {str(e)}")
        return web.Response(status=500)

async def test_handler(request):
    logger.info("وصل طلب إلى /test!")
    return web.Response(text="Test OK")

async def root_handler(request):
    logger.info("وصل طلب إلى المسار الجذر /")
    return web.Response(text="Root OK")

async def not_found_handler(request):
    logger.info(f"طلب غير موجود: {request.method} {request.path}")
    return web.Response(text="Not Found", status=404)

async def log_requests_middleware(app, handler):
    async def middleware_handler(request):
        logger.info(f"وصل طلب خارجي: {request.method} {request.path}")
        response = await handler(request)
        logger.info(f"رد السيرفر: {response.status}")
        return response
    return middleware_handler

async def main():
    logger.info("دخلنا الدالة الرئيسية...")
    try:
        telegram_app = await setup_application()
        
        web_app = web.Application(middlewares=[log_requests_middleware])
        web_app["telegram_app"] = telegram_app
        web_app.router.add_post("/webhook", webhook_handler)
        web_app.router.add_get("/test", test_handler)
        web_app.router.add_get("/", root_handler)
        web_app.router.add_route("*", "/{path:.*}", not_found_handler)  # لأي مسار غير معرف
        
        logger.info(f"جاري تشغيل السيرفر على بورت {PORT}...")
        runner = web.AppRunner(web_app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", PORT)
        await site.start()
        logger.info(f"سيرفر الـ Webhook شغال على بورت {PORT}")
        
        await asyncio.Event().wait()
    except Exception as e:
        logger.error(f"خطأ في الدالة الرئيسية: {str(e)}")
        raise

if __name__ == "__main__":
    logger.info("بدأ تشغيل السكربت الرئيسي!")
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"خطأ في تشغيل السكربت: {str(e)}")