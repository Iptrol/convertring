import os
import time
import logging
import asyncio
import httpx
import json

from telegram import (
    Update,
    InlineKeyboardButton, InlineKeyboardMarkup,
    KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove,
    WebAppInfo
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN  = os.getenv("BOT_TOKEN", "YOUR_TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://convertring-fkr7w16g2-lenas-projects-6797bf46.vercel.app")
API_BASE   = os.getenv("API_BASE", "https://convertring-production.up.railway.app")

TEXTS = {
    "uk": {
        "welcome": "🎶 *ConvertRing* — конвертер рингтонів для iPhone\n\nЩо можна надіслати:\n📹 Відео файл\n🔗 Посилання на YouTube / TikTok / Instagram\n🎤 Голосове повідомлення\n\nЯ конвертую і надішлю рингтон! 🎵",
        "converting": "⏳ Отримую та конвертую...",
        "done": "✅ Готово! Натисни кнопку щоб отримати рингтон 👇",
        "get_btn": "🎵 Отримати рингтон",
        "error": "❌ Не вдалося обробити. Спробуй інше відео або посилання.",
        "unsupported": "❌ Надішли відео, голосове або посилання на YouTube/TikTok/Instagram",
        "sending": "📤 Надсилаю рингтон...",
        "ringtone_caption": "🎵 Ось твій рингтон!\n\nЯк встановити:\n1. Скачай файл на Mac/PC\n2. Підключи iPhone кабелем\n3. Finder → iPhone → Рингтони → перетягни файл",
    },
    "ru": {
        "welcome": "🎶 *ConvertRing* — конвертер рингтонов для iPhone\n\nЧто можно отправить:\n📹 Видео файл\n🔗 Ссылку на YouTube / TikTok / Instagram\n🎤 Голосовое сообщение\n\nЯ конвертирую и отправлю рингтон! 🎵",
        "converting": "⏳ Загружаю и конвертирую...",
        "done": "✅ Готово! Нажми кнопку чтобы получить рингтон 👇",
        "get_btn": "🎵 Получить рингтон",
        "error": "❌ Не удалось обработать. Попробуй другое видео или ссылку.",
        "unsupported": "❌ Отправь видео, голосовое или ссылку на YouTube/TikTok/Instagram",
        "sending": "📤 Отправляю рингтон...",
        "ringtone_caption": "🎵 Вот твой рингтон!\n\nКак установить:\n1. Скачай файл на Mac/PC\n2. Подключи iPhone кабелем\n3. Finder → iPhone → Рингтоны → перетащи файл",
    },
    "en": {
        "welcome": "🎶 *ConvertRing* — iPhone ringtone converter\n\nYou can send:\n📹 Video file\n🔗 YouTube / TikTok / Instagram link\n🎤 Voice message\n\nI'll convert it to an iPhone ringtone! 🎵",
        "converting": "⏳ Downloading and converting...",
        "done": "✅ Done! Tap the button to get your ringtone 👇",
        "get_btn": "🎵 Get ringtone",
        "error": "❌ Failed to process. Try another video or link.",
        "unsupported": "❌ Send a video, voice message or YouTube/TikTok/Instagram link",
        "sending": "📤 Sending ringtone...",
        "ringtone_caption": "🎵 Here's your ringtone!\n\nHow to install:\n1. Download the file to Mac/PC\n2. Connect iPhone via cable\n3. Finder → iPhone → Tones → drag the file",
    },
}

user_lang: dict[int, str] = {}

def get_lang(user_id: int) -> str:
    return user_lang.get(user_id, "uk")

def lang_keyboard():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🇺🇦 Українська", callback_data="lang_uk"),
        InlineKeyboardButton("🇷🇺 Русский",    callback_data="lang_ru"),
        InlineKeyboardButton("🇬🇧 English",    callback_data="lang_en"),
    ]])

# ✅ ВИПРАВЛЕНО: ReplyKeyboardMarkup замість InlineKeyboardMarkup
def app_keyboard(lang: str, job_id: str):
    v = int(time.time())
    url = f"{WEBAPP_URL}?lang={lang}&job_id={job_id}&v={v}"
    return ReplyKeyboardMarkup(
        [[KeyboardButton(TEXTS[lang]["get_btn"], web_app=WebAppInfo(url=url))]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def main_keyboard(lang: str):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🌐 Змінити мову / Change language", callback_data="change_lang")
    ]])

def is_url(text: str) -> bool:
    return text.startswith("http://") or text.startswith("https://")

async def poll_job(job_id: str, timeout: int = 120) -> bool:
    async with httpx.AsyncClient() as client:
        for _ in range(timeout // 3):
            try:
                r = await client.get(f"{API_BASE}/status/{job_id}", timeout=10)
                d = r.json()
                if d["status"] == "done":
                    return True
                if d["status"] == "error":
                    return False
            except:
                pass
            await asyncio.sleep(3)
    return False

async def send_ringtone(ctx, chat_id: int, job_id: str, lang: str):
    t = TEXTS[lang]
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(f"{API_BASE}/download/{job_id}")
            if r.status_code == 200:
                # ✅ ВИПРАВЛЕНО: після надсилання файлу прибираємо ReplyKeyboard
                await ctx.bot.send_document(
                    chat_id=chat_id,
                    document=r.content,
                    filename="ringtone.m4r",
                    caption=t["ringtone_caption"],
                    reply_markup=ReplyKeyboardRemove()
                )
    except Exception as e:
        logger.error(f"send_ringtone error: {e}")

async def process_file(update: Update, ctx: ContextTypes.DEFAULT_TYPE, file_id: str, suffix: str):
    lang = get_lang(update.effective_user.id)
    t = TEXTS[lang]
    msg = await update.message.reply_text(t["converting"])
    try:
        tg_file = await ctx.bot.get_file(file_id)
        file_bytes = await tg_file.download_as_bytearray()
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{API_BASE}/convert/file",
                files={"file": (f"input{suffix}", bytes(file_bytes), "application/octet-stream")},
                data={"start": 0, "end": 30}
            )
            data = resp.json()
        job_id = data.get("job_id")
        if not job_id:
            await msg.edit_text(t["error"])
            return
        ok = await poll_job(job_id)
        if ok:
            await msg.edit_text(t["done"])
            # ✅ ВИПРАВЛЕНО: ReplyKeyboard надсилається окремим повідомленням
            await update.message.reply_text("👇", reply_markup=app_keyboard(lang, job_id))
        else:
            await msg.edit_text(t["error"])
    except Exception as e:
        logger.error(f"process_file error: {e}")
        await msg.edit_text(t["error"])

async def process_url_msg(update: Update, ctx: ContextTypes.DEFAULT_TYPE, url: str):
    lang = get_lang(update.effective_user.id)
    t = TEXTS[lang]
    msg = await update.message.reply_text(t["converting"])
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{API_BASE}/convert/url",
                json={"url": url, "start": 0, "end": 30}
            )
            data = resp.json()
        job_id = data.get("job_id")
        if not job_id:
            await msg.edit_text(t["error"])
            return
        ok = await poll_job(job_id)
        if ok:
            await msg.edit_text(t["done"])
            # ✅ ВИПРАВЛЕНО: ReplyKeyboard надсилається окремим повідомленням
            await update.message.reply_text("👇", reply_markup=app_keyboard(lang, job_id))
        else:
            await msg.edit_text(t["error"])
    except Exception as e:
        logger.error(f"process_url error: {e}")
        await msg.edit_text(t["error"])

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = user_lang.get(user_id)
    if lang:
        await update.message.reply_text(
            TEXTS[lang]["welcome"],
            parse_mode="Markdown",
            reply_markup=main_keyboard(lang)
        )
    else:
        await update.message.reply_text(
            "👋 Привіт! / Привет! / Hello!\n\nОберіть мову / Выберите язык / Choose language:",
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
            reply_markup=main_keyboard(lang)
        )
    elif q.data == "change_lang":
        await q.edit_message_text(
            "Оберіть мову / Выберите язык / Choose language:",
            reply_markup=lang_keyboard()
        )

async def on_web_app_data(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        data = json.loads(update.message.web_app_data.data)
        if data.get("action") == "send_file":
            job_id = data.get("job_id")
            user_id = update.effective_user.id
            lang = get_lang(user_id)
            t = TEXTS[lang]
            msg = await update.message.reply_text(t["sending"])
            await send_ringtone(ctx, update.effective_chat.id, job_id, lang)
            await msg.delete()
    except Exception as e:
        logger.error(f"web_app_data error: {e}")

async def on_video(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    file = update.message.video or update.message.document
    if not file:
        return
    suffix = ".mp4"
    if hasattr(file, "file_name") and file.file_name:
        suffix = os.path.splitext(file.file_name)[1] or ".mp4"
    await process_file(update, ctx, file.file_id, suffix)

async def on_voice(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    voice = update.message.voice or update.message.audio
    if not voice:
        return
    await process_file(update, ctx, voice.file_id, ".ogg")

async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message.web_app_data:
        return
    text = (update.message.text or "").strip()
    lang = get_lang(update.effective_user.id)
    if is_url(text):
        await process_url_msg(update, ctx, text)
    else:
        await update.message.reply_text(TEXTS[lang]["unsupported"])

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, on_web_app_data))
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, on_video))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, on_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    logger.info("✅ ConvertRing bot running...")
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
