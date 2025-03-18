import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import aiohttp
import sqlite3
import asyncio

# التوكن من المتغيرات البيئية
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
# عنوان URL بتاع Render
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://token-tracker-bot-worker.onrender.com/webhook")

# إعداد قاعدة بيانات SQLite
def init_db():
    conn = sqlite3.connect("tokens.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS tokens (user_id INTEGER, token_address TEXT)''')
    conn.commit()
    conn.close()

# جلب سعر ISLM من CoinGecko
async def get_token_price(token_address):
    async with aiohttp.ClientSession() as session:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=islamic-coin&vs_currencies=usd"
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                return data["islamic-coin"]["usd"]
            return "Error fetching price"

# أمر /start مع أزرار
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("إضافة توكن", callback_data="add_token")],
        [InlineKeyboardButton("عرض التوكنات", callback_data="list_tokens")],
        [InlineKeyboardButton("إيقاف الإشعارات", callback_data="stop_notifications")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "👋 مرحبًا بك في TokenTracker!\n⚠️ تنبيه: التداول في العملات الرقمية قد يحمل مخاطر شرعية. استشر عالم دين.",
        reply_markup=reply_markup
    )

# معالجة ضغط الأزرار
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if query.data == "add_token":
        await query.edit_message_text("أرسل أي نص لتتبع Islamic Coin (ISLM):")
        context.user_data["awaiting_token"] = True
    elif query.data == "list_tokens":
        conn = sqlite3.connect("tokens.db")
        c = conn.cursor()
        c.execute("SELECT token_address FROM tokens WHERE user_id=?", (user_id,))
        tokens = c.fetchall()
        conn.close()
        
        if not tokens:
            await query.edit_message_text("لم تقم بإضافة توكنات بعد!")
        else:
            msg = "التوكنات الخاصة بك:\n"
            for token in tokens:
                price = await get_token_price(token[0])
                msg += f"- Islamic Coin (ISLM): ${price}\n"
            await query.edit_message_text(msg)
    elif query.data == "stop_notifications":
        if context.job_queue and context.job_queue.scheduler:
            context.job_queue.scheduler.remove_all_jobs()
            await query.edit_message_text("تم إيقاف الإشعارات!")
        else:
            await query.edit_message_text("لا توجد إشعارات مفعلة!")

# إضافة توكن جديد
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("awaiting_token"):
        token_address = update.message.text
        user_id = update.message.from_user.id
        
        conn = sqlite3.connect("tokens.db")
        c = conn.cursor()
        c.execute("INSERT INTO tokens (user_id, token_address) VALUES (?, ?)", (user_id, token_address))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(f"تم تفعيل تتبع Islamic Coin (ISLM)")
        context.user_data["awaiting_token"] = False
        
        # بدء الإشعارات التلقائية
        scheduler = AsyncIOScheduler()
        scheduler.add_job(send_price_update, "interval", hours=1, args=(context, user_id, token_address))
        scheduler.start()
        context.job_queue.scheduler = scheduler

# إرسال تحديثات الأسعار
async def send_price_update(context: ContextTypes.DEFAULT_TYPE, user_id: int, token_address: str):
    price = await get_token_price(token_address)
    await context.bot.send_message(chat_id=user_id, text=f"تحديث سعر Islamic Coin (ISLM): ${price}")

# Webhook Handler
async def webhook(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.application.process_update(update)

# التشغيل
async def main():
    init_db()
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # إعداد Webhook
    await app.bot.set_webhook(url=WEBHOOK_URL)
    app.add_handler(webhook)
    
    # تشغيل الـ Webhook على Port 8000
    await app.run_webhook(
        listen="0.0.0.0",
        port=8000,
        url_path="/webhook",
        webhook_url=WEBHOOK_URL
    )

if __name__ == "__main__":
    asyncio.run(main())