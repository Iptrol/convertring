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
    MessageHandler, ContextTypes, filters,
    ConversationHandler
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN  = os.getenv("BOT_TOKEN", "YOUR_TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://convertring-fkr7w16g2-lenas-projects-6797bf46.vercel.app")
API_BASE   = os.getenv("API_BASE", "https://convertring-production.up.railway.app")

# Стани ConversationHandler
ASK_START, ASK_END = range(2)

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
        "ask_start": "З якої секунди починати? ⏱\n\nНаприклад: `30` — це 0:30 у відео\n_(введи 0 якщо з початку)_",
        "ask_end": "До якої секунди? ⏱\n\nНаприклад: `60` — це 1:00 у відео\n_(максимум 40 секунд від старту)_",
        "invalid_number": "❌ Введи ціле число, наприклад: `30`",
        "invalid_range": "❌ Кінець має бути більше початку. Введи знову:",
        "too_long": "❌ Максимальна тривалість рингтону — 40 секунд. Введи менше значення:",
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
        "ask_start": "С какой секунды начинать? ⏱\n\nНапример: `30` — это 0:30 в видео\n_(введи 0 если с начала)_",
        "ask_end": "До какой секунды? ⏱\n\nНапример: `60` — это 1:00 в видео\n_(максимум 40 секунд от старта)_",
        "invalid_number": "❌ Введи целое число, например: `30`",
        "invalid_range": "❌ Конец должен быть больше начала. Введи снова:",
        "too_long": "❌ Максимальная длительность рингтона — 40 секунд. Введи меньшее значение:",
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
        "ask_start": "From which second to start? ⏱\n\nExample: `30` means 0:30 in the video\n_(enter 0 to start from the beginning)_",
        "ask_end": "Until which second? ⏱\n\nExample: `60` means 1:00 in the video\n_(max 40 seconds from start)_",
        "invalid_number": "❌ Enter a whole number, e.g.: `30`",
        "invalid_range": "❌ End must be greater than start. Try again:",
        "too_long": "❌ Max ringtone duration is 40 seconds. Enter a smaller value:",
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
            await update.message.reply_text("👇", reply_markup=app_keyboard(lang, job_id))
        else:
            await msg.edit_text(t["error"])
    except Exception as e:
        logger.error(f"process_file error: {e}")
        await msg.edit_text(t["error"])

async def process_url_with_range(update: Update, ctx: ContextTypes.DEFAULT_TYPE, url: str, start: int, end: int):
    lang = get_lang(update.effective_user.id)
    t = TEXTS[lang]
    msg = await update.message.reply_text(t["converting"])
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{API_BASE}/convert/url",
                json={"url": url, "start": start, "end": end}
            )
            data = resp.json()
        job_id = data.get("job_id")
        if not job_id:
            await msg.edit_text(t["error"])
            return
        ok = await poll_job(job_id)
        if ok:
            await msg.edit_text(t["done"])
            await update.message.reply_text("👇", reply_markup=app_keyboard(lang, job_id))
        else:
            await msg.edit_text(t["error"])
    except Exception as e:
        logger.error(f"process_url error: {e}")
        await msg.edit_text(t["error"])

# ── ConversationHandler: крок 1 — отримали URL, питаємо старт ──────────────
async def url_received(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if not is_url(text):
        lang = get_lang(update.effective_user.id)
        await update.message.reply_text(TEXTS[lang]["unsupported"])
        return ConversationHandler.END

    lang = get_lang(update.effective_user.id)
    ctx.user_data["url"] = text
    await update.message.reply_text(TEXTS[lang]["ask_start"], parse_mode="Markdown")
    return ASK_START

# ── ConversationHandler: крок 2 — отримали старт, питаємо кінець ───────────
async def got_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(update.effective_user.id)
    t = TEXTS[lang]
    text = (update.message.text or "").strip()
    try:
        start = int(text)
        if start < 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text(t["invalid_number"], parse_mode="Markdown")
        return ASK_START

    ctx.user_data["start"] = start
    await update.message.reply_text(t["ask_end"], parse_mode="Markdown")
    return ASK_END

# ── ConversationHandler: крок 3 — отримали кінець, конвертуємо ─────────────
async def got_end(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(update.effective_user.id)
    t = TEXTS[lang]
    text = (update.message.text or "").strip()
    start = ctx.user_data.get("start", 0)

    try:
        end = int(text)
        if end < 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text(t["invalid_number"], parse_mode="Markdown")
        return ASK_END

    if end <= start:
        await update.message.reply_text(t["invalid_range"], parse_mode="Markdown")
        return ASK_END

    if end - start > 40:
        await update.message.reply_text(t["too_long"], parse_mode="Markdown")
        return ASK_END

    url = ctx.user_data.get("url")
    ctx.user_data.clear()

    await process_url_with_range(update, ctx, url, start, end)
    return ConversationHandler.END

# ── /start скасовує будь-який поточний діалог ──────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear()
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
    return ConversationHandler.END

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

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # ConversationHandler для URL → старт → кінець
    url_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.TEXT & ~filters.COMMAND, url_received)
        ],
        states={
            ASK_START: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_start)],
            ASK_END:   [MessageHandler(filters.TEXT & ~filters.COMMAND, got_end)],
        },
        fallbacks=[CommandHandler("start", cmd_start)],
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, on_web_app_data))
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, on_video))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, on_voice))
    app.add_handler(url_conv)

    logger.info("✅ ConvertRing bot running...")
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
