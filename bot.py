import os
import sqlite3
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
# 🆔 آیدی عددی تلگرام خودتان را اینجا بگذارید تا اعلان سفارش‌های جدید برایتان ارسال شود
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID", "123456789") 

# ---------------- DATABASE ----------------
conn = sqlite3.connect("crm.db", check_same_thread=False)
cursor = conn.cursor()
# اضافه کردن ستون‌هایی برای ذخیره دقیق پاسخ‌های مشتری و شماره تلفن
cursor.execute("""
CREATE TABLE IF NOT EXISTS customers (
    user_id INTEGER PRIMARY KEY,
    name TEXT,
    username TEXT,
    phone TEXT,
    place_type TEXT,      -- خانه/مغازه/پروژه
    location_type TEXT,   -- داخلی/خارجی
    cam_count TEXT,       -- تعداد دوربین
    budget TEXT,          -- میزان بودجه
    stage INTEGER DEFAULT 1,
    score INTEGER DEFAULT 0,
    status TEXT DEFAULT 'new',
    created_at TEXT
)
""")
conn.commit()

# نگاشت مراحل به ستون‌های دیتابیس برای ذخیره خودکار
STAGE_TO_COLUMN = {
    1: "place_type",
    2: "location_type",
    3: "cam_count",
    4: "budget"
}

# ---------------- DATA & KEYBOARDS ----------------
STAGE_CONFIG = {
    1: {
        "text": "سلام 👋 به سیستم نیازسنجی هوشمند خوش آمدید.\n\nدوربین مداربسته را برای چه مکانی نیاز دارید؟",
        "keyboard": [["🏠 خانه", "🏪 مغازه"], ["🏢 پروژه"]]
    },
    2: {
        "text": "برای فضای داخلی (In-door) می‌خواهید یا فضای باز و خارجی (Out-door)؟",
        "keyboard": [["内部 داخلی", "🌳 خارجی"], ["🔄 هر دو مورد"]]
    },
    3: {
        "text": "حدوداً به چه تعداد دوربین نیاز دارید؟",
        "keyboard": [["1️⃣ ۱ تا ۴ عدد", "2️⃣ ۵ تا ۸ عدد"], ["🔢 بیشتر از ۸ عدد"]]
    },
    4: {
        "text": "بودجه حدودی که در نظر گرفته‌اید چقدر است؟",
        "keyboard": [["💵 اقتصادی و ارزان", "⚖️ کیفیت و قیمت متوسط"], ["💎 حرفه‌ای و پیشرفته"]]
    }
}

# ---------------- HELPERS ----------------
def get_customer(user):
    cursor.execute("SELECT stage, score, phone FROM customers WHERE user_id=?", (user.id,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("""
        INSERT INTO customers (user_id, name, username, stage, score, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user.id, user.full_name, user.username or "", 1, 0, "new", datetime.now().isoformat()))
        conn.commit()
        return 1, 0, None
    return row

def update_customer_data(user_id, column_name, value):
    # جلوگیری از SQL Injection با اطمینان از نام ستون‌ها
    if column_name in ["place_type", "location_type", "cam_count", "budget", "phone", "status"]:
        cursor.execute(f"UPDATE customers SET {column_name}=? WHERE user_id=?", (value, user_id))
        conn.commit()

def update_customer_flow(user_id, stage=None, score=None):
    if stage is not None:
        cursor.execute("UPDATE customers SET stage=? WHERE user_id=?", (stage, user_id))
    if score is not None:
        cursor.execute("UPDATE customers SET score=? WHERE user_id=?", (score, user_id))
    conn.commit()

def calc_score(text, stage, current_score):
    added_score = 15  # امتیاز پایه برای پاسخ به هر سوال
    if any(w in text for w in ["قیمت", "میخوام", "خرید", "نصب", "فوری", "حرفه"]):
        added_score += 20
    return min(current_score + added_score, 100)

def get_all_customer_info(user_id):
    cursor.execute("SELECT name, username, phone, place_type, location_type, cam_count, budget, score FROM customers WHERE user_id=?", (user_id,))
    return cursor.fetchone()

# ---------------- BOT HANDLERS ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    # ریست کردن اطلاعات برای شروع مجدد تست
    cursor.execute("UPDATE customers SET stage=1, score=0, status='new' WHERE user_id=?", (user.id,))
    conn.commit()
    
    config = STAGE_CONFIG[1]
    await update.message.reply_text(
        config["text"],
        reply_markup=ReplyKeyboardMarkup(config["keyboard"], resize_keyboard=True)
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    text = update.message.text
    stage, score, phone = get_customer(user)

    # ۱. بررسی دکمه ثبت سفارش
    if text == "📦 ثبت سفارش":
        if not phone:
            # اگر شماره تلفن ندارد، اول دکمه ارسال شماره را می‌فرستیم
            contact_keyboard = [[KeyboardButton(text="📱 ارسال شماره موبایل", request_contact=True)]]
            await update.message.reply_text(
                "لطفاً جهت ثبت نهایی سفارش و تماس کارشناسان، روی دکمه زیر کلیک کنید تا شماره تماس شما ارسال شود👇",
                reply_markup=ReplyKeyboardMarkup(contact_contact, resize_keyboard=True, one_time_keyboard=True)
            )
        else:
            await process_final_order(update, context, user.id)
        return

    # اگر کاربر مراحل را تمام کرده ولی دوباره پیام متنی متفرقه می‌فرستد
    if stage > len(STAGE_CONFIG):
        await update.message.reply_text(
            "اطلاعات شما قبلاً ثبت شده است. لطفاً جهت نهایی‌سازی روی دکمه زیر کلیک کنید:",
            reply_markup=ReplyKeyboardMarkup([["📦 ثبت سفارش"]], resize_keyboard=True)
        )
        return

    # ۲. ذخیره پاسخ کاربر مربوط به مرحله فعلی
    col_name = STAGE_TO_COLUMN.get(stage)
    if col_name:
        update_customer_data(user.id, col_name, text)

    # ۳. محاسبه و بروزرسانی امتیاز و گام بعدی
    new_score = calc_score(text, stage, score)
    new_stage = stage + 1
    update_customer_flow(user.id, stage=new_stage, score=new_score)

    # ۴. هدایت به گام بعدی یا ارائه دکمه نهایی
    if new_stage <= len(STAGE_CONFIG):
        next_config = STAGE_CONFIG[new_stage]
        keyboard = next_config["keyboard"] + [["📦 ثبت سفارش"]]
        await update.message.reply_text(
            next_config["text"],
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
    else:
        # پایان پاسخ‌دهی به سوالات
        reply_text = f"🔥 نیازسنجی شما با موفقیت انجام شد (امتیاز اشتیاق خرید شما: {new_score}/100).\n\nبرای ثبت درخواست و تماس مشاوران ما، لطفاً دکمه زیر را بزنید:"
        await update.message.reply_text(
            reply_text,
            reply_markup=ReplyKeyboardMarkup([["📦 ثبت سفارش"]], resize_keyboard=True)
        )

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ هندلر مخصوص دریافت شماره تلفن مشتری """
    user = update.message.from_user
    contact = update.message.contact
    
    # مطمئن شویم شماره ارسالی متعلق به خود کاربر است (امنیت)
    if contact.user_id == user.id:
        phone_number = contact.phone_number
        update_customer_data(user.id, "phone", phone_number)
        
        # بعد از گرفتن شماره، بلافاصله فرآیند ثبت نهایی را اجرا می‌کنیم
        await process_final_order(update, context, user.id)
    else:
        await update.message.reply_text("⚠️ لطفا شماره تلفن خودتان را از طریق دکمه قرار داده شده ارسال کنید.")

async def process_final_order(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id):
    """ پردازش نهایی سفارش و ارسال گزارش به مدیر """
    info = get_all_customer_info(user_id)
    name, username, phone, place, location, cams, budget, score = info
    
    # آپدیت وضعیت در دیتابیس
    update_customer_data(user_id, "status", "lead")
    
    # پیام موفقیت به مشتری
    await update.message.reply_text(
        "✅ سفارش شما با موفقیت در سیستم CRM ثبت شد.\nکارشناسان ما به زودی با شماره شما تماس خواهند گرفت. از اعتماد شما سپاسگزاریم!",
        reply_markup=ReplyKeyboardRemove() # حذف کیبورد برای تمیزی چت
    )
    
    # 🔔 ارسال اعلان فوری به مدیر سیستم
    admin_msg = (
        f"🚨 **لید جدید در سیستم ثبت شد!**\n\n"
        f"👤 **مشتری:** {name} ( @{username if username else 'بدون آیدی'} )\n"
        f"📞 **تلفن:** `{phone}`\n"
        f"📊 **امتیاز خرید:** {score}/100\n\n"
        f"📝 **جزئیات نیازسنجی:**\n"
        f"🔹 مکان: {place or 'ثبت نشده'}\n"
        f"🔹 محیط: {location or 'ثبت نشده'}\n"
        f"🔹 تعداد دوربین: {cams or 'ثبت نشده'}\n"
        f"🔹 بودجه: {budget or 'ثبت نشده'}"
    )
    
    try:
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=admin_msg, parse_mode="Markdown")
    except Exception as e:
        print(f"خطا در ارسال پیام به مدیر: {e}")

# ---------------- MAIN ----------------
def main():
    if not TELEGRAM_TOKEN:
        print("❌ TELEGRAM_TOKEN تنظیم نشده است.")
        return

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    # اضافه کردن هندلر مخصوص دکمه Contact (شماره تلفن)
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🚀 CRM & Lead Bot is running with Admin Notification active...")
    app.run_polling()

if __name__ == "__main__":
    main()
