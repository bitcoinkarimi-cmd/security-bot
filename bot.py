import os
import requests
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

# تنظیمات
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
HAIO_API_KEY = os.environ.get("HAIO_API_KEY")

SYSTEM_PROMPT = """تو دستیار فروش یه فروشگاه تخصصی دوربین مداربسته و دزدگیر اماکن هستی.

محصولات ما:
- دوربین مداربسته (داخلی، خارجی، بی‌سیم، با سیم)
- دزدگیر اماکن (خانگی، تجاری، اداری)
- DVR و NVR ضبط تصویر
- لوازم جانبی (کابل، منبع تغذیه، هارد)
- نصب و راه‌اندازی در محل

مزایای ما:
- مشاوره رایگان
- نصب حرفه‌ای در محل
- گارانتی معتبر
- قیمت مناسب

قوانین پاسخ‌دهی:
- با مشتری صمیمی و مودب باش
- جواب کوتاه و مفید بده (حداکثر ۳ جمله)
- اگه قیمت پرسید بگو قیمت‌ها متنوعه و برای مشاوره دقیق با ما تماس بگیرن
- همیشه در آخر یه سوال بپرس تا مشتری رو راهنمایی کنی
- اگه مشتری جدی بود بگو با شماره ما تماس بگیره"""

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    
    # ارسال به هوش مصنوعی هایو
    try:
        response = requests.post(
            "https://api.haio.ir/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {HAIO_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message}
                ],
                "max_tokens": 300
            },
            timeout=30
        )
        
        data = response.json()
        ai_reply = data["choices"][0]["message"]["content"]
        
    except Exception as e:
        ai_reply = "متأسفم، مشکلی پیش اومد. لطفاً دوباره پیام بدید یا با ما تماس بگیرید."
    
    await update.message.reply_text(ai_reply)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "سلام! 👋 به فروشگاه دوربین مداربسته و دزدگیر خوش اومدید.\n\n"
        "چطور می‌تونم کمکتون کنم؟ 😊"
    )

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'^/start$'), start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("ربات در حال اجراست...")
    app.run_polling()

if __name__ == "__main__":
    main()
