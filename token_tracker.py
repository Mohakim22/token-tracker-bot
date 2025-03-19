import os
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from aiohttp import web

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://token-tracker-bot-worker.onrender.com/webhook")
PORT = int(os.getenv("PORT", 8000))

print("بدأ تشغيل السكربت!")
print(f"التوكن: {TOKEN}")
print(f"رابط الـ Webhook: {WEBHOOK_URL}")
print(f"البورت: {PORT}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("وصل أمر /start من المستخدم!")
    keyboard = [
        [InlineKeyboardButton("إضافة توكن", callback_data="add_token")],
        [InlineKeyboardButton("عرض التوكنات", callback_data="list_tokens")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("مرحبًا بك في TokenTrackerBot!", reply_markup=reply_markup)

async def setup_application():
    print("جاري إعداد تطبيق تيليجرام...")
    app = Application.builder().token(TOKEN).build()
    print("جاري حذف الـ Webhook القديم...")
    await app.bot.delete_webhook(drop_pending_updates=True)
    print("جاري إعداد الـ Webhook الجديد...")
    await app.bot.set_webhook(url=WEBHOOK_URL)
    print("تم إعداد الـ Webhook بنجاح!")
    
    app.add_handler(CommandHandler("start", start))
    return app

async def webhook_handler(request):
    print("وصل طلب Webhook!")
    app = request.app["telegram_app"]
    update = Update.de_json(await request.json(), app.bot)
    await app.process_update(update)
    return web.Response(text="OK")

async def main():
    print("دخلنا الدالة الرئيسية...")
    telegram_app = await setup_application()
    
    web_app = web.Application()
    web_app["telegram_app"] = telegram_app
    web_app.router.add_post("/webhook", webhook_handler)
    
    print(f"جاري تشغيل السيرفر على بورت {PORT}...")
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    print(f"سيرفر الـ Webhook شغال على بورت {PORT}")
    
    await asyncio.Event().wait()

if __name__ == "__main__":
    print("بدأ تشغيل السكربت الرئيسي!")
    asyncio.run(main())