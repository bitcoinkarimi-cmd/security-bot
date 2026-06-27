import os
import sqlite3
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

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
conn.commit()

# ---------------- DATA ----------------
stage_text = {
    1: "برای کجاست؟ خانه یا مغازه یا پروژه؟",
    2: "داخلی یا خارجی؟",
    3: "چند دوربین نیاز داری؟",
    4: "بودجه حدودی چقدره؟"
}

# ---------------- HELPERS ----------------
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

def update_customer(user_id, stage=None, score=None):
    if stage is not None:
        cursor.execute("UPDATE customers SET stage=? WHERE user_id=?", (stage, user_id))
    if score is not None:
        cursor.execute("UPDATE customers SET score=? WHERE user_id=?", (score, user_id))
    conn.commit()

def calc_score(text, stage):
    score = 0
    if any(w in text for w in ["قیمت", "میخوام", "خرید", "نصب"]):
        score += 30
    if any(w in text for w in ["بودجه", "چند", "هزینه"]):
        score += 20
    score += stage * 10
    return min(score, 100)

# ---------------- BOT HANDLERS ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["🏠 خانه", "🏪 مغازه"], ["🏢 پروژه"]]
    await update.message.reply_text(
        "سلام 👋 برای چه مکانی نیاز به دوربین داری؟",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    text = update.message.text

    # دکمه ثبت سفارش جداگانه بررسی شود
    if text == "📦 ثبت سفارش":
        # بررسی کنیم آیا مرحله مناسب رسیده (امتیاز بالا)
        stage, score = get_customer(user)
        if score >= 70:
            await update.message.reply_text("✅ سفارش شما ثبت شد. همکاران ما به زودی تماس می‌گیرند.")
        else:
            await update.message.reply_text("هنوز نیازسنجی کامل نشده. لطفاً به سوالات پاسخ بدهید.")
        return  # از ادامه پردازش جلوگیری شود

    # روال عادی مراحل
    stage, score = get_customer(user)

    # محاسبه امتیاز جدید
    new_score = calc_score(text, stage)
    new_stage = stage + 1
    update_customer(user.id, stage=new_stage, score=new_score)

    # اگر امتیاز بالا باشد، پیشنهاد نهایی
    if new_score >= 70:
        reply = "🔥 پکیج مناسب شما آماده است.\nبرای ثبت سفارش دکمه زیر را بزنید."
        keyboard = [["📦 ثبت سفارش"]]
    else:
        reply = stage_text.get(new_stage, "لطفاً بیشتر توضیح بدهید تا بهترین پیشنهاد را ارائه دهیم.")
        keyboard = [["📦 ثبت سفارش"]]  # همچنان دکمه وجود دارد ولی با اخطار کار می‌کند

    await update.message.reply_text(
        reply,
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

# ---------------- MAIN ----------------
def main():
    if not TELEGRAM_TOKEN:
        print("❌ TELEGRAM_TOKEN در متغیرهای محیطی تنظیم نشده است.")
        return

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("✅ Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
