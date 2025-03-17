import os
import json
import aiohttp
import asyncio
import logging
from web3 import Web3
import aiosqlite
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from binance import AsyncClient as BinanceClient
from dotenv import load_dotenv
from datetime import datetime

# إعداد Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', filename='token_tracker.log')
logger = logging.getLogger(__name__)

# تحميل الـ .env
load_dotenv("C:/Users/Details Store/OneDrive/Desktop/TokenTracker/.env")

# إعدادات
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
BINANCE_API_KEY = os.getenv('BINANCE_API_KEY')
BINANCE_SECRET_KEY = os.getenv('BINANCE_SECRET_KEY')
INFURA_URL = os.getenv('INFURA_URL')
AUTHORIZED_USERS = [1128191066]  # الـ User ID بتاعك هنا

# التحقق من المتغيرات
if not all([TELEGRAM_TOKEN, BINANCE_API_KEY, BINANCE_SECRET_KEY, INFURA_URL]):
    logger.error("بعض المتغيرات البيئية مفقودة!")
    raise ValueError("يرجى التحقق من ملف .env")

# الاتصال بالخدمات
w3 = Web3(Web3.HTTPProvider(INFURA_URL))
binance_client = BinanceClient(BINANCE_API_KEY, BINANCE_SECRET_KEY)
with open('config.json', 'r') as f:
    config = json.load(f)

ERC20_ABI = [
    {"constant": True, "inputs": [], "name": "name", "outputs": [{"name": "", "type": "string"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "symbol", "outputs": [{"name": "", "type": "string"}], "type": "function"}
]

# إعداد قاعدة البيانات
async def init_db():
    async with aiosqlite.connect('token_tracker.db') as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS tokens (
            token_address TEXT PRIMARY KEY, name TEXT, symbol TEXT,
            price REAL, liquidity REAL, volume_24h REAL, last_updated TIMESTAMP)''')
        await db.commit()
    logger.info("تم تهيئة قاعدة البيانات بنجاح")

# فحص التوافق الشرعي
async def is_sharia_compliant(token_address):
    try:
        contract = w3.eth.contract(address=w3.to_checksum_address(token_address), abi=ERC20_ABI)
        name = contract.functions.name().call().lower()
        forbidden_keywords = ['casino', 'gambling', 'alcohol', 'porn']
        return not any(keyword in name for keyword in forbidden_keywords)
    except Exception as e:
        logger.error(f"خطأ في فحص التوافق الشرعي لـ {token_address}: {e}")
        return False

# جلب بيانات التوكن من DexScreener
async def fetch_token_data(token_address):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{config['dexscreener_api']}{token_address}") as resp:
                if resp.status == 200:
                    return await resp.json()
                logger.warning(f"فشل جلب بيانات {token_address}: {resp.status}")
                return {}
    except Exception as e:
        logger.error(f"خطأ في جلب بيانات {token_address}: {e}")
        return {}

# تطبيق الفلاتر
def meets_criteria(data):
    filters = config['filters']
    price = data.get('price', 0)
    liquidity = data.get('liquidity', 0)
    volume_24h = data.get('volume_24h', 0)
    marketcap = data.get('marketcap', 0)
    return (filters['min_price'] <= price <= filters['max_price'] and
            liquidity >= filters['min_liquidity'] and
            volume_24h >= filters['min_volume_24h'] and
            (marketcap > 0 and liquidity / marketcap >= filters['min_liquidity_to_marketcap_ratio']))

# Telegram Bot
app = Application.builder().token(TELEGRAM_TOKEN).build()

# واجهة البداية
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in AUTHORIZED_USERS:
        await update.message.reply_text("🚫 غير مصرح لك باستخدام هذا البوت!")
        return
    keyboard = [
        [InlineKeyboardButton("➕ إضافة توكن", callback_data='add_token')],
        [InlineKeyboardButton("📋 عرض التوكنات", callback_data='show_tokens')],
        [InlineKeyboardButton("⚙️ الإعدادات", callback_data='settings')],
        [InlineKeyboardButton("📊 تداول يدوي", callback_data='trade')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "👋 مرحبًا بك في TokenTracker!\n"
        "⚠️ تنبيه: التداول في العملات الرقمية قد يحمل مخاطر شرعية. استشر عالم دين.\n"
        "اختر خيارًا من القائمة:",
        reply_markup=reply_markup
    )
    logger.info(f"مستخدم {user_id} بدأ البوت")

# معالجة الأزرار
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == 'add_token':
        await query.edit_message_text("📝 أرسل عنوان التوكن باستخدام: /track <token_address>")
    elif query.data == 'show_tokens':
        async with aiosqlite.connect('token_tracker.db') as db:
            async with db.execute("SELECT token_address, price, symbol FROM tokens") as cursor:
                tokens = await cursor.fetchall()
        if tokens:
            token_list = "\n".join([f"🔹 {t[2]} ({t[0][:10]}...) - ${t[1]:.6f}" for t in tokens])
            await query.edit_message_text(f"📋 التوكنات المتبعة:\n{token_list}")
        else:
            await query.edit_message_text("❌ لا توجد توكنات متبعة حاليًا.")
    elif query.data == 'settings':
        keyboard = [
            [InlineKeyboardButton("تغيير اللغة", callback_data='lang')],
            [InlineKeyboardButton("تحديث الفلاتر", callback_data='filters')]
        ]
        await query.edit_message_text("⚙️ اختر إعدادًا:", reply_markup=InlineKeyboardMarkup(keyboard))
    elif query.data == 'trade':
        await query.edit_message_text("📊 أرسل أمر التداول: /trade <symbol> <side> <quantity>\nمثال: /trade BTCUSDT BUY 0.01")

# تتبع توكن
async def track(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in AUTHORIZED_USERS:
        await update.message.reply_text("🚫 غير مصرح لك!")
        return
    try:
        token_address = context.args[0]
        if not w3.is_address(token_address):
            await update.message.reply_text("❌ عنوان توكن غير صالح!")
            return
        if not await is_sharia_compliant(token_address):
            await update.message.reply_text("⚠️ هذا التوكن غير متوافق مع الشريعة!")
            return
        await update_token_data(token_address)
        await update.message.reply_text(f"✅ تمت إضافة {token_address} بنجاح!")
        logger.info(f"تمت إضافة {token_address} بواسطة {user_id}")
    except IndexError:
        await update.message.reply_text("📝 استخدام خاطئ! اكتب: /track <token_address>")

# تحديث بيانات التوكن
async def update_token_data(token_address):
    data = await fetch_token_data(token_address)
    if meets_criteria(data):
        async with aiosqlite.connect('token_tracker.db') as db:
            contract = w3.eth.contract(address=w3.to_checksum_address(token_address), abi=ERC20_ABI)
            name = contract.functions.name().call()
            symbol = contract.functions.symbol().call()
            await db.execute("""
                INSERT OR REPLACE INTO tokens (token_address, name, symbol, price, liquidity, volume_24h, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (token_address, name, symbol, data.get('price', 0), data.get('liquidity', 0), data.get('volume_24h', 0), datetime.now().isoformat()))
            await db.commit()

# تداول يدوي
async def trade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in AUTHORIZED_USERS:
        await update.message.reply_text("🚫 غير مصرح لك!")
        return
    try:
        symbol, side, quantity = context.args[0].upper(), context.args[1].upper(), float(context.args[2])
        order = await binance_client.create_order(symbol=symbol, side=side, type='MARKET', quantity=quantity)
        await update.message.reply_text(f"📊 تم تنفيذ الأمر: {order['side']} {order['executedQty']} {symbol}")
        logger.info(f"تم تنفيذ أمر تداول: {symbol} {side} {quantity} بواسطة {user_id}")
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ في التداول: {str(e)}")
        logger.error(f"خطأ في التداول: {e}")

# تتبع التوكنات دوريًا
async def track_tokens(application):
    while True:
        try:
            async with aiosqlite.connect('token_tracker.db') as db:
                async with db.execute("SELECT token_address FROM tokens") as cursor:
                    tokens = await cursor.fetchall()
                for (token_address,) in tokens:
                    await update_token_data(token_address)
            logger.info("تم تحديث بيانات التوكنات")
        except Exception as e:
            logger.error(f"خطأ في تتبع التوكنات: {e}")
        await asyncio.sleep(config['check_interval_seconds'])

# التشغيل الرئيسي
def main():
    # تهيئة قاعدة البيانات
    asyncio.get_event_loop().run_until_complete(init_db())

    # إضافة المعالجات
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("track", track))
    app.add_handler(CommandHandler("trade", trade))
    app.add_handler(CallbackQueryHandler(button_handler))

    # بدء تتبع التوكنات في الخلفية
    app.job_queue.run_repeating(track_tokens, interval=config['check_interval_seconds'], first=0)

    # تشغيل البوت
    logger.info("البوت بدأ يعمل!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()