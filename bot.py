import os
import requests
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes

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

قوانین:
- با مشتری صمیمی و مودب باش
- جواب کوتاه و مفید بده (حداکثر ۳ جمله)
- اگه قیمت پرسید بگو متنوعه و برای مشاوره تماس بگیرن
- همیشه یه سوال بپرس تا راهنمایی کنی"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "سلام! 👋 به فروشگاه دوربین مداربسته و دزدگیر خوش اومدید.\nچطور می‌تونم کمکتون کنم؟ 😊"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    try:
        response = requests.post(
            "https://ai.haiocloud.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {HAIO_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "qwen/qwen3.5-122b-a10b",
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
        ai_reply = "متأسفم، مشکلی پیش اومد. لطفاً دوباره پیام بدید."

    await update.message.reply_text(ai_reply)

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("ربات در حال اجراست...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
