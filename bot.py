import os
import sqlite3
import httpx
import asyncio
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
HAIO_API_KEY = os.environ.get("HAIO_API_KEY")
GROUP_ID = -1003972716358

# ---------------- DATABASE ----------------
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

cursor.execute("""
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    role TEXT,
    content TEXT,
    created_at TEXT
)
""")

conn.commit()

# ---------------- SYSTEM ----------------
SYSTEM_PROMPT = """تو کارشناس فروش شرکت یزدامن هستی.

قوانین:
- کوتاه (1-2 جمله)
- فقط یک سوال
- تا نیاز مشخص نشده پیشنهاد نده
"""

stage_text = {
    1: "بپرس: برای کجاست؟ خانه، مغازه یا پروژه؟",
    2: "بپرس: فضای داخلیه یا خارجی؟",
    3: "بپرس: چند دوربین نیاز داری؟",
    4: "بپرس: بودجه حدودی چقدره؟"
}

PACKAGES = {
    "small": ("📦 اقتصادی", "4 دوربین + DVR + نصب", "۹,۹۰۰,۰۰۰"),
    "medium": ("📦 حرفه‌ای", "6 دوربین + NVR + دید در شب", "۱۵,۵۰۰,۰۰۰"),
    "premium": ("📦 کامل", "8 دوربین + 4K + موبایل", "۲۲,۹۰۰,۰۰۰"),
}

# ---------------- HELPERS ----------------
def calculate_score(text, stage):
    score = 0

    if any(w in text for w in ["قیمت", "میخوام", "خرید", "بفرست", "نصب"]):
        score += 30

    if any(w in text for w in ["چند", "هزینه", "بودجه"]):
        score += 20

    score += stage * 10

    return min(score, 100)


def choose_package(score):
    if score < 50:
        return "small"
    elif score < 80:
        return "medium"
    else:
        return "premium"


def build_offer(score):
    key = choose_package(score)
    title, desc, price = PACKAGES[key]

    return f"""
🔥 پیشنهاد ویژه شما

{title}
📌 {desc}
💰 {price} تومان

✔ نصب در محل
✔ گارانتی ۲ ساله
✔ مشاوره رایگان

برای ثبت سفارش دکمه "📦 ثبت سفارش" را بزن
"""


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


def update_customer(user_id, stage=None, score=None, status=None):
    if stage is not None:
        cursor.execute("UPDATE customers SET stage=? WHERE user_id=?", (stage, user_id))
    if score is not None:
        cursor.execute("UPDATE customers SET score=? WHERE user_id=?", (score, user_id))
    if status is not None:
        cursor.execute("UPDATE customers SET status=? WHERE user_id=?", (status, user_id))
    conn.commit()


def save_message(user_id, role, content):
    cursor.execute("""
    INSERT INTO messages (user_id, role, content, created_at)
    VALUES (?, ?, ?, ?)
    """, (user_id, role, content, datetime.now().isoformat()))
    conn.commit()


# ---------------- FOLLOW UP ----------------
async def follow_up(context, user_id):
    await asyncio.sleep(60 * 60 * 2)

    cursor.execute("SELECT status FROM customers WHERE user_id=?", (user_id,))
    row = cursor.fetchone()

    if row and row[0] in ["hot", "offered"]:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="👋 هنوز تصمیم نگرفتی؟ می‌تونم امروز برات تخفیف ویژه فعال کنم."
            )
        except:
            pass


# ---------------- BOT ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["🏠 خانه", "🏪 مغازه"], ["🏢 پروژه"]]
    await update.message.reply_text(
        "سلام 👋 برای چه مکانی نیاز به دوربین داری؟",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    text = update.message.text

    stage, score, status = get_customer(user)

    save_message(user.id, "user", text)

    # score update
    new_score = calculate_score(text, stage)
    update_customer(user.id, score=new_score)

    # stage update
    stage += 1
    update_customer(user.id, stage=stage)

    # HOT LEAD
    if new_score >= 70:
        update_customer(user.id, status="hot")
        reply = build_offer(new_score)
