import os
import requests
from datetime import datetime
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
HAIO_API_KEY = os.environ.get("HAIO_API_KEY")
GROUP_ID = -1003972716358

SYSTEM_PROMPT = """تو کارشناس فروش شرکت یزدامن در یزد هستی. هدفت فروشه.

قوانین مکالمه:
- جواب خیلی کوتاه (۱ تا ۲ جمله)
- هر بار فقط یه سوال بپرس
- تا نیاز مشتری رو نفهمیدی محصول پیشنهاد نده
- مودب و صمیمی باش

قیف فروش — دقیقاً این ترتیب:
۱. بپرس: "برای کجاست؟ خانه، مغازه یا پروژه؟"
۲. بپرس: "فضا داخلیه یا خارجی؟"
۳. بپرس: "چند تا دوربین نیاز داری؟"
۴. بپرس: "بودجه‌ات حدوداً چقدره؟"
۵. پکیج مناسب پیشنهاد بده با قیمت
۶. اگه تردید داشت: "گارانتی طلایی ۲ ساله داریم + اقساط ۵ ماهه"
۷. ببند: "کی می‌تونم برای بازدید رایگان بیام؟"

اطلاعات شرکت:
- تلفن: ۰۹۱۹۷۶۵۲۰۴۰
- آدرس: یزد، بلوار استقلال، کوچه نیمه شعبان
- ساعت کاری: ۸ صبح تا ۸ شب
- نصب در کل استان یزد
- پروژه‌های بزرگ تخصص ماست

قیمت‌ها:
- دوربین شبکه ۵ مگاپیکسل رنگی شب: ۹،۶۰۰،۰۰۰ تومان
- دوربین HD 5 مگاپیکسل: ۴،۵۰۰،۰۰۰ تومان
- دوربین شبکه ۸ مگاپیکسل: ۱۵،۷۹۰،۰۰۰ تومان
- دوربین پلاکخوان: قیمت روز (نیاز به نرم‌افزار تخصصی)
- DVR 8 کانال HD: ۹،۹۰۰،۰۰۰ تومان
- NVR 16 کانال 4K: ۱۰،۳۵۰،۰۰۰ تومان
- هارد ۵۰۰ گیگ: حدود ۴،۰۰۰،۰۰۰ تومان
- کابل شبکه CAT6: متری ۴۸،۰۰۰ تومان
- کابل برق: متری ۲۹،۰۰۰ تومان
- دزدگیر منزل فلزی فول امکانات: قیمت با مشاوره

مزایا (فقط وقتی مشتری تردید داشت بگو):
- گارانتی طلایی ۲ ساله (حتی شکستن و نوسان برق)
- خدمات پس از فروش ۵ ساله
- تعمیر در یزد بدون ارسال به تهران
- مونتاژ داخلی — بدون واسطه — قیمت پایین‌تر
- اقساط: ۳۰-۴۰٪ نقد، بقیه ۵-۶ ماهه
- هزینه نصب ۱۰ تا ۲۰٪ زیر نرخ صنف

تفاوت شبکه و HD:
- شبکه: کابل مثل کامپیوتر (CAT6)، کیفیت بالاتر، موبایل از همه جا
- HD: کابل مثل آنتن تلویزیون، ارزون‌تر، کیفیت خوب"""

new_customers = set()
chat_histories = {}

async def notify_group(context, user, first_message):
    name = user.full_name or "نامشخص"
    username = f"@{user.username}" if user.username else "ندارد"
    user_id = user.id
    date = datetime.now().strftime("%Y/%m/%d %H:%M")
    text = f"""🔔 مشتری جدید — یزدامن

👤 نام: {name}
📱 یوزرنیم: {username}
🆔 آیدی: {user_id}
💬 اولین پیام: {first_message}
🕐 تاریخ: {date}
👉 لینک چت: tg://user?id={user_id}"""
    try:
        await context.bot.send_message(chat_id=GROUP_ID, text=text)
    except:
        pass

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "سلام! 👋 به شرکت یزدامن خوش اومدید.\n"
        "متخصص دوربین مداربسته، دزدگیر و درب‌های اتوماتیک در یزد.\n\n"
        "چطور می‌تونم کمکتون کنم؟ 😊"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    user_message = update.message.text
    user_id = user.id

    if user_id not in new_customers:
        new_customers.add(user_id)
        await notify_group(context, user, user_message)

    if user_id not in chat_histories:
        chat_histories[user_id] = []

    chat_histories[user_id].append({"role": "user", "content": user_message})

    if len(chat_histories[user_id]) > 20:
        chat_histories[user_id] = chat_histories[user_id][-20:]

    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + chat_histories[user_id]

    try:
        response = requests.post(
            "https://ai.haiocloud.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {HAIO_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "qwen/qwen3.5-122b-a10b",
                "messages": messages,
                "max_tokens": 300
            },
            timeout=30
        )
        data = response.json()
        ai_reply = data["choices"][0]["message"]["content"]
        chat_histories[user_id].append({"role": "assistant", "content": ai_reply})
    except:
        ai_reply = "متأسفم، مشکلی پیش اومد. با ۰۹۱۹۷۶۵۲۰۴۰ تماس بگیرید."

    await update.message.reply_text(ai_reply)

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("ربات یزدامن آماده‌ست...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
