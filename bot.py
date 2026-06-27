import os
import sqlite3
from datetime import datetime
import asyncio
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

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

# ---------------- DATA ----------------
stage_text = {
    1: "برای کجاست؟ خانه یا مغازه یا پروژه؟",
    2: "داخلی یا خارجی؟",
    3: "چند دوربین؟",
    4: "بودجه حدودی؟"
}

# ---------------- HELP ----------------
def get_customer(user):
    cursor.execute("SELECT stage, score FROM customers WHERE user_id=?", (user.id,))
    row = cursor.fetchone()

    if not row:
        cursor.execute("""
        INSERT INTO customers (user_id, name, username, stage, score, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user.id, user.full_name, user.username or "", 1, 0, "new", datetime.now().isoformat()))
        conn.commit()
        return 1, 0

    return row


def update(user_id, stage=None, score=None):
    if stage is not None:
        cursor.execute("UPDATE customers SET stage=? WHERE user_id=?", (stage, user_id))
    if score is not None:
        cursor.execute("UPDATE customers SET score=? WHERE user_id=?", (score, user_id))
    conn.commit()


def calc_score(text, stage):
    score = 0
    if "قیمت" in text or "میخوام" in text:
        score += 30
    if "بودجه" in text or "چند" in text:
        score += 20
    score += stage * 10
    return min(score, 100)

# ---------------- BOT ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["🏠 خانه", "🏪 مغازه"], ["🏢 پروژه"]]

    await update.message.reply_text(
        "سلام 👋 چی نیاز داری؟",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    text = update.message.text

    stage, score = get_customer(user)

    score = calc_score(text, stage)
    stage += 1

    update(user.id, stage=stage, score=score)

    if score >= 70:
        reply = "🔥 پکیج مناسب شما آماده است\nبرای ثبت سفارش دکمه زیر را بزن"
    else:
        reply = stage_text.get(stage, "بیشتر توضیح بده 🙂")

    keyboard = [["📦 ثبت سفارش"]]

    await update.message.reply_text(
        reply,
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )


async def order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "📦 ثبت سفارش":
        await update.message.reply_text("✅ سفارش ثبت شد")


def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, order))

    print("Bot running...")
    app.run_polling()


if __name__ == "__main__":
    main()
