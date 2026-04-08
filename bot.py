import os
import logging
logging.basicConfig(level=logging.INFO)

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ContextTypes
)

BOT_TOKEN  = os.getenv("BOT_TOKEN", "YOUR_TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://convertring-fkr7w16g2-lenas-projects-6797bf46.vercel.app")

TEXTS = {
    "uk": {
        "welcome": "🎶 *ConvertRing* — конвертер рингтонів для iPhone\n\nНатисни кнопку нижче щоб відкрити апп 👇",
        "open_btn": "✂️ Відкрити ConvertRing",
    },
    "ru": {
        "welcome": "🎶 *ConvertRing* — конвертер рингтонов для iPhone\n\nНажми кнопку ниже чтобы открыть приложение 👇",
        "open_btn": "✂️ Открыть ConvertRing",
    },
    "en": {
        "welcome": "🎶 *ConvertRing* — iPhone ringtone converter\n\nTap the button below to open the app 👇",
        "open_btn": "✂️ Open ConvertRing",
    },
}

user_lang: dict[int, str] = {}

def get_lang(user_id: int):
    return user_lang.get(user_id, None)

def lang_keyboard():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🇺🇦 Українська", callback_data="lang_uk"),
        InlineKeyboardButton("🇷🇺 Русский",    callback_data="lang_ru"),
        InlineKeyboardButton("🇬🇧 English",    callback_data="lang_en"),
    ]])

def app_keyboard(lang: str):
    t = TEXTS[lang]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t["open_btn"], web_app=WebAppInfo(url=f"{WEBAPP_URL}?lang={lang}"))],
        [InlineKeyboardButton("🌐 Змінити мову / Change language", callback_data="change_lang")],
    ])

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    if lang:
        await update.message.reply_text(
            TEXTS[lang]["welcome"],
            parse_mode="Markdown",
            reply_markup=app_keyboard(lang)
        )
    else:
        await update.message.reply_text(
            "👋 Привіт! / Привет! / Hello!\n\n"
            "Оберіть мову / Выберите язык / Choose language:",
            reply_markup=lang_keyboard()
        )

async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id
    if q.data.startswith("lang_"):
        lang = q.data.replace("lang_", "")
        user_lang[user_id] = lang
        await q.edit_message_text(
            TEXTS[lang]["welcome"],
            parse_mode="Markdown",
            reply_markup=app_keyboard(lang)
        )
    elif q.data == "change_lang":
        await q.edit_message_text(
            "Оберіть мову / Выберите язык / Choose language:",
            reply_markup=lang_keyboard()
        )

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CallbackQueryHandler(on_callback))
    print("✅ ConvertRing bot running...")
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
