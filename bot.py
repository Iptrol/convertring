import os
import time
import logging
import asyncio
import httpx
import json
import re

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
ASK_MOMENT, ASK_NAME = range(2)

TEXTS = {
    "uk": {
        "welcome": "🎶 *ConvertRing* — конвертер рингтонів для iPhone\n\nЩо можна надіслати:\n📹 Відео файл\n🔗 Посилання на YouTube / YouTube Music / TikTok / Instagram\n🎤 Голосове повідомлення\n\nЯ конвертую і надішлю рингтон! 🎵",
        "converting": "⏳ Отримую та конвертую...",
        "done": "✅ Готово! Натисни кнопку щоб отримати рингтон 👇",
        "get_btn": "🎵 Отримати рингтон",
        "error": "❌ Не вдалося обробити. Спробуй інше відео або посилання.",
        "unsupported": "❌ Надішли відео, голосове або посилання на YouTube/TikTok/Instagram",
        "sending": "📤 Надсилаю рингтон...",
        "ringtone_caption": "🎵 Ось твій рингтон!\n\nЯк встановити:\n1. Скачай файл на Mac/PC\n2. Підключи iPhone кабелем\n3. Finder → iPhone → Рингтони → перетягни файл",
        "ask_moment": "✂️ З якого моменту зробити рингтон?\nЯ відріжу 40 секунд від цього місця.\n\nВведи час у форматі `хв:сек`, наприклад:\n• `00:00` — з початку\n• `00:30` — через 30 секунд\n• `01:34` — через 1 хвилину 34 секунди",
        "invalid_moment": "❌ Не розумію формат. Спробуй ще раз.\n\nПриклади: `00:00` `00:30` `01:34`",
        "ask_name": "💾 Хочеш дати назву рингтону?\nЗ цією назвою він збережеться в тебе в телефоні.",
        "skip_btn": "⏭️ Пропустити",
        "name_btn": "✏️ Дати назву",
        "write_name": "Напиши назву рингтону:",
    },
    "ru": {
        "welcome": "🎶 *ConvertRing* — конвертер рингтонов для iPhone\n\nЧто можно отправить:\n📹 Видео файл\n🔗 Ссылку на YouTube / YouTube Music / TikTok / Instagram\n🎤 Голосовое сообщение\n\nЯ конвертирую и отправлю рингтон! 🎵",
        "converting": "⏳ Загружаю и конвертирую...",
        "done": "✅ Готово! Нажми кнопку чтобы получить рингтон 👇",
        "get_btn": "🎵 Получить рингтон",
        "error": "❌ Не удалось обработать. Попробуй другое видео или ссылку.",
        "unsupported": "❌ Отправь видео, голосовое или ссылку на YouTube/TikTok/Instagram",
        "sending": "📤 Отправляю рингтон...",
        "ringtone_caption": "🎵 Вот твой рингтон!\n\nКак установить:\n1. Скачай файл на Mac/PC\n2. Подключи iPhone кабелем\n3. Finder → iPhone → Рингтоны → перетащи файл",
        "ask_moment": "✂️ С какого момента сделать рингтон?\nЯ отрежу 40 секунд от этого места.\n\nВведи время в формате `мин:сек`, например:\n• `00:00` — с начала\n• `00:30` — через 30 секунд\n• `01:34` — через 1 минуту 34 секунды",
        "invalid_moment": "❌ Не понимаю формат. Попробуй ещё раз.\n\nПримеры: `00:00` `00:30` `01:34`",
        "ask_name": "💾 Хочешь дать название рингтону?\nС этим названием он сохранится у тебя в телефоне.",
        "skip_btn": "⏭️ Пропустить",
        "name_btn": "✏️ Дать название",
        "write_name": "Напиши название рингтона:",
    },
    "en": {
        "welcome": "🎶 *ConvertRing* — iPhone ringtone converter\n\nYou can send:\n📹 Video file\n🔗 YouTube / YouTube Music / TikTok / Instagram link\n🎤 Voice message\n\nI'll convert it to an iPhone ringtone! 🎵",
        "converting": "⏳ Downloading and converting...",
        "done": "✅ Done! Tap the button to get your ringtone 👇",
        "get_btn": "🎵 Get ringtone",
        "error": "❌ Failed to process. Try another video or link.",
        "unsupported": "❌ Send a video, voice message or YouTube/TikTok/Instagram link",
        "sending": "📤 Sending ringtone...",
        "ringtone_caption": "🎵 Here's your ringtone!\n\nHow to install:\n1. Download the file to Mac/PC\n2. Connect iPhone via cable\n3. Finder → iPhone → Tones → drag the file",
        "ask_moment": "✂️ From which moment to make the ringtone?\nI'll cut 40 seconds from this point.\n\nEnter time in `min:sec` format, for example:\n• `00:00` — from the beginning\n• `00:30` — after 30 seconds\n• `01:34` — after 1 minute 34 seconds",
        "invalid_moment": "❌ I don't understand the format. Try again.\n\nExamples: `00:00` `00:30` `01:34`",
        "ask_name": "💾 Want to name your ringtone?\nIt will be saved with this name on your phone.",
        "skip_btn": "⏭️ Skip",
        "name_btn": "✏️ Give a name",
        "write_name": "Write the ringtone name:",
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

def name_keyboard(lang: str):
    t = TEXTS[lang]
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(t["skip_btn"], callback_data="name_skip"),
        InlineKeyboardButton(t["name_btn"], callback_data="name_give"),
    ]])

def main_keyboard(lang: str):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🌐 Змінити мову / Change language", callback_data="change_lang")
    ]])

def is_url(text: str) -> bool:
    return text.startswith("http://") or text.startswith("https://")

def parse_moment(text: str):
    text = text.strip()
    match = re.fullmatch(r"(\d{1,2}):(\d{2})", text)
    if not match:
        return None
    minutes = int(match.group(1))
    seconds = int(match.group(2))
    if seconds >= 60:
        return None
    return minutes * 60 + seconds

def get_source_from_url(url: str) -> str:
    url_lower = url.lower()
    if "instagram.com" in url_lower:
        return "instagram"
    elif "tiktok.com" in url_lower:
        return "tiktok"
    elif "spotify.com" in url_lower:
        return "spotify"
    elif "youtube.com" in url_lower or "youtu.be" in url_lower:
        return "youtube"
    else:
        return "video"

def make_filename(source: str, job_id: str, custom_name: str = None) -> str:
    if custom_name:
        # Прибираємо символи які не можна у назві файлу
        safe = re.sub(r'[\\/*?:"<>|]', "", custom_name).strip()
        if safe:
            return f"{safe}.m4r"
    short_id = job_id.replace("-", "")[:4]
    return f"{source}_{short_id}.m4r"

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

async def send_ringtone(ctx, chat_id: int, job_id: str, lang: str, source: str = "file", custom_name: str = None):
    t = TEXTS[lang]
    filename = make_filename(source, job_id, custom_name)
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(f"{API_BASE}/download/{job_id}")
            if r.status_code == 200:
                await ctx.bot.send_document(
                    chat_id=chat_id,
                    document=r.content,
                    filename=filename,
                    caption=t["ringtone_caption"],
                    reply_markup=ReplyKeyboardRemove()
                )
    except Exception as e:
        logger.error(f"send_ringtone error: {e}")

async def start_conversion(update: Update, ctx: ContextTypes.DEFAULT_TYPE, start: int):
    """Запускає конвертацію і показує питання про назву"""
    lang = get_lang(update.effective_user.id)
    t = TEXTS[lang]
    end = start + 40
    msg = await update.message.reply_text(t["converting"])

    try:
        file_id = ctx.user_data.get("file_id")
        suffix  = ctx.user_data.get("suffix", ".mp4")
        url     = ctx.user_data.get("url")
        source  = ctx.user_data.get("source", "file")

        if file_id:
            tg_file = await ctx.bot.get_file(file_id)
            file_bytes = await tg_file.download_as_bytearray()
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    f"{API_BASE}/convert/file",
                    files={"file": (f"input{suffix}", bytes(file_bytes), "application/octet-stream")},
                    data={"start": start, "end": end}
                )
                data = resp.json()
        elif url:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    f"{API_BASE}/convert/url",
                    json={"url": url, "start": start, "end": end}
                )
                data = resp.json()
        else:
            await msg.edit_text(t["error"])
            return ConversationHandler.END

        job_id = data.get("job_id")
        if not job_id:
            await msg.edit_text(t["error"])
            return ConversationHandler.END

        # Зберігаємо job_id і source для наступних кроків
        ctx.user_data["job_id"] = job_id
        ctx.user_data["source"] = source
        ctx.user_data.pop("file_id", None)
        ctx.user_data.pop("url", None)

        ok = await poll_job(job_id)
        if not ok:
            await msg.edit_text(t["error"])
            return ConversationHandler.END

        await msg.delete()

        # Питаємо про назву
        await update.message.reply_text(t["ask_name"], reply_markup=name_keyboard(lang))
        return ASK_NAME

    except Exception as e:
        logger.error(f"start_conversion error: {e}")
        await msg.edit_text(t["error"])
        return ConversationHandler.END

async def got_moment(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(update.effective_user.id)
    t = TEXTS[lang]
    text = (update.message.text or "").strip()

    start = parse_moment(text)
    if start is None:
        await update.message.reply_text(t["invalid_moment"], parse_mode="Markdown")
        return ASK_MOMENT

    return await start_conversion(update, ctx, start)

async def got_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Юзер ввів назву вручну"""
    lang = get_lang(update.effective_user.id)
    t = TEXTS[lang]
    custom_name = (update.message.text or "").strip()
    job_id = ctx.user_data.get("job_id")
    source = ctx.user_data.get("source", "file")
    ctx.user_data.clear()

    msg = await update.message.reply_text(t["sending"])
    await send_ringtone(ctx, update.effective_chat.id, job_id, lang, source, custom_name)
    await msg.delete()
    ctx.user_data[f"source_{job_id}"] = source
    return ConversationHandler.END

# ── URL entry ──────────────────────────────────────────────────────────────
async def url_received(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if not is_url(text):
        lang = get_lang(update.effective_user.id)
        await update.message.reply_text(TEXTS[lang]["unsupported"])
        return ConversationHandler.END

    lang = get_lang(update.effective_user.id)
    ctx.user_data["url"] = text
    ctx.user_data["source"] = get_source_from_url(text)
    await update.message.reply_text(TEXTS[lang]["ask_moment"], parse_mode="Markdown")
    return ASK_MOMENT

# ── /start ─────────────────────────────────────────────────────────────────
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
    lang = get_lang(user_id)
    t = TEXTS[lang]

    if q.data == "name_skip":
        # Пропускаємо назву — надсилаємо з дефолтною
        job_id = ctx.user_data.get("job_id")
        source = ctx.user_data.get("source", "file")
        ctx.user_data.clear()
        await q.edit_message_text(t["sending"])
        await send_ringtone(ctx, q.message.chat_id, job_id, lang, source)
        await q.delete_message()

    elif q.data == "name_give":
        # Просимо ввести назву
        await q.edit_message_text(t["write_name"])

    elif q.data.startswith("lang_"):
        new_lang = q.data.replace("lang_", "")
        user_lang[user_id] = new_lang
        await q.edit_message_text(
            TEXTS[new_lang]["welcome"],
            parse_mode="Markdown",
            reply_markup=main_keyboard(new_lang)
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
            source = ctx.user_data.pop(f"source_{job_id}", "file")
            msg = await update.message.reply_text(t["sending"])
            await send_ringtone(ctx, update.effective_chat.id, job_id, lang, source)
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
    lang = get_lang(update.effective_user.id)
    ctx.user_data["file_id"] = file.file_id
    ctx.user_data["suffix"] = suffix
    ctx.user_data["source"] = "file"
    await update.message.reply_text(TEXTS[lang]["ask_moment"], parse_mode="Markdown")

async def on_voice(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    voice = update.message.voice or update.message.audio
    if not voice:
        return
    lang = get_lang(update.effective_user.id)
    t = TEXTS[lang]
    msg = await update.message.reply_text(t["converting"])
    try:
        tg_file = await ctx.bot.get_file(voice.file_id)
        file_bytes = await tg_file.download_as_bytearray()
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{API_BASE}/convert/file",
                files={"file": ("input.ogg", bytes(file_bytes), "application/octet-stream")},
                data={"start": 0, "end": 40}
            )
            data = resp.json()
        job_id = data.get("job_id")
        if not job_id:
            await msg.edit_text(t["error"])
            return
        ctx.user_data[f"source_{job_id}"] = "voice"
        ok = await poll_job(job_id)
        if ok:
            await msg.edit_text(t["done"])
            await update.message.reply_text("👇", reply_markup=app_keyboard(lang, job_id))
        else:
            await msg.edit_text(t["error"])
    except Exception as e:
        logger.error(f"on_voice error: {e}")
        await msg.edit_text(t["error"])

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.TEXT & ~filters.COMMAND, url_received),
            MessageHandler(filters.VIDEO | filters.Document.VIDEO, on_video),
        ],
        states={
            ASK_MOMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_moment)],
            ASK_NAME:   [MessageHandler(filters.TEXT & ~filters.COMMAND, got_name)],
        },
        fallbacks=[CommandHandler("start", cmd_start)],
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, on_web_app_data))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, on_voice))
    app.add_handler(conv)

    logger.info("✅ ConvertRing bot running...")
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
