import os
import sqlite3
import httpx
import asyncio
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
HAIO_API_KEY = os.environ.get("HAIO_API_KEY")

# ---------------- DB ----------------
conn = sqlite3.connect("crm.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS customers (
    user_id INTEGER PRIMARY KEY,
    name TEXT,
    username TEXT,
    stage INTEGER DEFAULT 1,
    score INTEGER DEFAULT 0,
    status TEXT DEFAULT 'new',
    created_at TEXT
)
""")
conn.commit()

# ---------------- CONFIG ----------------
SYSTEM_PROMPT = "تو کارشناس فروش هستی. کوتاه و مرحله‌ای سوال بپرس."

stage_text = {
    1: "خانه، مغازه یا پروژه؟",
    2: "داخلی یا خارجی؟",
    3: "چند دوربین؟",
    4: "بودجه حدودی؟"
}

# ---------------- CORE ----------------
def get_customer(user):
    cursor.execute("SELECT stage, score, status FROM customers WHERE user_id=?", (user.id,))
    row = cursor.fetchone()

    if not row:
        cursor.execute("""
        INSERT INTO customers (user_id, name, username, stage, score, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user.id, user.full_name, user.username or "", 1, 0, "new", datetime.now().isoformat()))
        conn.commit()
        return 1, 0, "new"

    return row


def update_customer(user_id, **kwargs):
    for k, v in kwargs.items():
        cursor.execute(f"UPDATE customers SET {k}=? WHERE user_id=?", (v, user_id))
    conn.commit()


def calc_score(text, stage):
    score = 0
    if any(w in text for w in ["قیمت", "میخوام", "خرید", "نصب"]):
        score += 30
    if any(w in text for w in ["بودجه", "چند", "هزینه"]):
        score += 20
    score += stage * 10
    return min(score, 100)


# ---------------- FOLLOW UP ----------------
async def follow_up(context, user_id):
    await asyncio.sleep(60 * 60 * 2)

    cursor.execute("SELECT status FROM customers WHERE user_id=?", (user_id,))
    row = cursor.fetchone()

    if row and row[0] in ["hot"]:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="👋 هنوز تصمیم نگرفتی؟ اگر بخوای امروز برات بهترین پکیج رو پیشنهاد می‌دم."
            )
        except:
            pass


# ---------------- START ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["🏠 خانه", "🏪 مغازه"], ["🏢 پروژه"]]

    await update.message.reply_text(
        "سلام 👋 برای چه محیطی دوربین میخوای؟",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )


# ---------------- MAIN HANDLER ----------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    text = update.message.text

    stage, score, status = get_customer(user)

    score = calc_score(text, stage)
    stage += 1

    update_customer(user.id, stage=stage, score=score)

    # HOT LEAD
    if score >= 70:
        update_customer(user.id, status="hot")

        reply = f"""
🔥 پیشنهاد ویژه

📦 پکیج مناسب شما آماده است
💰 حدود قیمت: اقتصادی تا حرفه‌ای

برای ثبت سفارش دکمه زیر را بزن
"""

        context.application.create_task(follow_up(context, user.id))

    else:
        reply = stage_text.get(stage, "بیشتر توضیح بده 🙂")

    keyboard = [["📦 ثبت سفارش"]]

    await update.message.reply_text(
        reply,
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )


# ---------------- ORDER ----------------
async def order_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update
