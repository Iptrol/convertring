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
ASK_MOMENT, ASK_CUSTOM_MOMENT, ASK_NAME, WAIT_NAME_INPUT = range(4)

TEXTS = {
    "uk": {
        "welcome": "🎶 *ConvertRing* — конвертер рингтонів для iPhone\n\nЩо можна надіслати:\n📹 Відео файл з твоєї галереї\n🔗 Посилання на YouTube / YouTube Music / TikTok / Instagram\n🎤 Голосове повідомлення\n\nЯ конвертую і надішлю рингтон! 🎵",
        "converting": "⏳ Отримую та конвертую...",
        "done": "✅ Готово! Натисни кнопку щоб отримати рингтон 👇",
        "get_btn": "🎵 Отримати рингтон",
        "error": "❌ Не вдалося обробити. Спробуй інше відео або посилання.",
        "unsupported": "❌ Надішли відео, голосове або посилання на YouTube/TikTok/Instagram",
        "sending": "📤 Надсилаю рингтон...",
        "ringtone_caption": "🎵 Ось твій рингтон!\n\nЯк встановити:\n1. Натисни на файл\n2. Тапни «Використовувати як мелодію» в правому нижньому куті\n3. Готово! ✅ Галочка біля рингтону підтверджує що все ок\n4. Якщо потребуєш допомоги з встановленням, обирай в боті кнопку «Як встановити рінгтон»\n\nPS: Ти можеш встановити персональний рінгтон на різних абонентів: друга, бесті, родину тощо. Тому не зупиняйся ❤️",
        "ask_moment": "🎵 З якого місця зробити рингтон?",
        "from_start_btn": "▶️ З початку",
        "custom_moment_btn": "✂️ Вибрати момент",
        "ask_custom_moment": "⏱ Введи час у форматі `хв:сек`\nЯ відріжу 40 секунд від цього моменту.\nНаприклад: `00:30` або `01:34`",
        "invalid_moment": "❌ Не розумію формат. Спробуй ще раз.\n\nПриклади: `00:30` `01:34`",
        "ask_name": "💾 Хочеш дати назву рингтону?\nЗ цією назвою він збережеться в тебе в телефоні.",
        "skip_btn": "⏭️ Пропустити",
        "name_btn": "✏️ Дати назву",
        "write_name": "✏️ Напиши назву рингтону:",
    },
    "ru": {
        "welcome": "🎶 *ConvertRing* — конвертер рингтонов для iPhone\n\nЧто можно отправить:\n📹 Видео файл из твоей галереи\n🔗 Ссылку на YouTube / YouTube Music / TikTok / Instagram\n🎤 Голосовое сообщение\n\nЯ конвертирую и отправлю рингтон! 🎵",
        "converting": "⏳ Загружаю и конвертирую...",
        "done": "✅ Готово! Нажми кнопку чтобы получить рингтон 👇",
        "get_btn": "🎵 Получить рингтон",
        "error": "❌ Не удалось обработать. Попробуй другое видео или ссылку.",
        "unsupported": "❌ Отправь видео, голосовое или ссылку на YouTube/TikTok/Instagram",
        "sending": "📤 Отправляю рингтон...",
        "ringtone_caption": "🎵 Вот твой рингтон!\n\nКак установить:\n1. Нажми на файл\n2. Тапни «Использовать как мелодию» в правом нижнем углу\n3. Готово! ✅ Галочка рядом с рингтоном подтверждает что всё ок\n4. Если нужна помощь с установкой, выбирай в боте кнопку «Как установить рингтон»\n\nPS: Ты можешь установить персональный рингтон для разных контактов: друга, подруги, семьи и т.д. Так что не останавливайся ❤️",
        "ask_moment": "🎵 С какого места сделать рингтон?",
        "from_start_btn": "▶️ С начала",
        "custom_moment_btn": "✂️ Выбрать момент",
        "ask_custom_moment": "⏱ Введи время в формате `мин:сек`\nЯ отрежу 40 секунд от этого момента.\nНапример: `00:30` или `01:34`",
        "invalid_moment": "❌ Не понимаю формат. Попробуй ещё раз.\n\nПримеры: `00:30` `01:34`",
        "ask_name": "💾 Хочешь дать название рингтону?\nС этим названием он сохранится у тебя в телефоне.",
        "skip_btn": "⏭️ Пропустить",
        "name_btn": "✏️ Дать название",
        "write_name": "✏️ Напиши название рингтона:",
    },
    "en": {
        "welcome": "🎶 *ConvertRing* — iPhone ringtone converter\n\nYou can send:\n📹 Video file from your gallery\n🔗 YouTube / YouTube Music / TikTok / Instagram link\n🎤 Voice message\n\nI'll convert it to an iPhone ringtone! 🎵",
        "converting": "⏳ Downloading and converting...",
        "done": "✅ Done! Tap the button to get your ringtone 👇",
        "get_btn": "🎵 Get ringtone",
        "error": "❌ Failed to process. Try another video or link.",
        "unsupported": "❌ Send a video, voice message or YouTube/TikTok/Instagram link",
        "sending": "📤 Sending ringtone...",
        "ringtone_caption": "🎵 Here's your ringtone!\n\nHow to install:\n1. Tap on the file\n2. Tap «Use as Ringtone» in the bottom right corner\n3. Done! ✅ A checkmark next to the ringtone means everything is set\n4. If you need help with installation, tap «How to install» in the bot\n\nPS: You can set personal ringtones for different contacts — friends, family, and more. Keep going ❤️",
        "ask_moment": "🎵 From which part to make the ringtone?",
        "from_start_btn": "▶️ From the beginning",
        "custom_moment_btn": "✂️ Choose moment",
        "ask_custom_moment": "⏱ Enter time in `min:sec` format\nI'll cut 40 seconds from this moment.\nFor example: `00:30` or `01:34`",
        "invalid_moment": "❌ I don't understand the format. Try again.\n\nExamples: `00:30` `01:34`",
        "ask_name": "💾 Want to name your ringtone?\nIt will be saved with this name on your phone.",
        "skip_btn": "⏭️ Skip",
        "name_btn": "✏️ Give a name",
        "write_name": "✏️ Write the ringtone name:",
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

def moment_keyboard(lang: str):
    t = TEXTS[lang]
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(t["from_start_btn"],    callback_data="moment_start"),
        InlineKeyboardButton(t["custom_moment_btn"], callback_data="moment_custom"),
    ]])

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

async def do_convert(bot, chat_id: int, lang: str, user_data: dict, ctx=None):
    """Конвертує і показує кнопку міні-апп."""
    start       = user_data.get("start", 0)
    end         = start + 40
    file_id     = user_data.get("file_id")
    suffix      = user_data.get("suffix", ".mp4")
    url         = user_data.get("url")
    source      = user_data.get("source", "file")
    custom_name = user_data.get("custom_name")
    t           = TEXTS[lang]

    try:
        if file_id:
            tg_file = await bot.get_file(file_id)
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
            return False, None

        job_id = data.get("job_id")
        if not job_id:
            return False, None

        ok = await poll_job(job_id)
        if not ok:
            return False, None

        if ctx is not None:
            ctx.user_data[f"source_{job_id}"] = source
            ctx.user_data[f"name_{job_id}"] = custom_name

        await bot.send_message(
            chat_id=chat_id,
            text="👇",
            reply_markup=app_keyboard(lang, job_id)
        )
        return True, job_id
    except Exception as e:
        logger.error(f"do_convert error: {e}")
        return False, None

# ── Після отримання файлу/URL — питаємо момент ─────────────────────────────
async def ask_moment(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(update.effective_user.id)
    t = TEXTS[lang]
    await update.message.reply_text(t["ask_moment"], reply_markup=moment_keyboard(lang))
    return ASK_MOMENT

# ── Кнопка "З початку" ─────────────────────────────────────────────────────
async def cb_moment_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    lang = get_lang(q.from_user.id)
    t = TEXTS[lang]
    ctx.user_data["start"] = 0
    await q.edit_message_text(t["ask_name"], reply_markup=name_keyboard(lang))
    return ASK_NAME

# ── Кнопка "Вибрати момент" ────────────────────────────────────────────────
async def cb_moment_custom(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    lang = get_lang(q.from_user.id)
    t = TEXTS[lang]
    await q.edit_message_text(t["ask_custom_moment"], parse_mode="Markdown")
    return ASK_CUSTOM_MOMENT

# ── Юзер ввів час вручну ──────────────────────────────────────────────────
async def got_custom_moment(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(update.effective_user.id)
    t = TEXTS[lang]
    text = (update.message.text or "").strip()

    start = parse_moment(text)
    if start is None:
        await update.message.reply_text(t["invalid_moment"], parse_mode="Markdown")
        return ASK_CUSTOM_MOMENT

    ctx.user_data["start"] = start
    await update.message.reply_text(t["ask_name"], reply_markup=name_keyboard(lang))
    return ASK_NAME

# ── Кнопка "Пропустити" назву ─────────────────────────────────────────────
async def cb_name_skip(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    lang = get_lang(q.from_user.id)
    t = TEXTS[lang]
    ctx.user_data["custom_name"] = None
    await q.edit_message_text(t["converting"])
    ok, _ = await do_convert(ctx.bot, q.message.chat_id, lang, ctx.user_data, ctx)
    if ok:
        await q.edit_message_text(t["done"])
    else:
        await q.edit_message_text(t["error"])
    # НЕ чистимо user_data тут — on_web_app_data ще потребує name_{job_id}
    return ConversationHandler.END

# ── Кнопка "Дати назву" ───────────────────────────────────────────────────
async def cb_name_give(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    lang = get_lang(q.from_user.id)
    t = TEXTS[lang]
    await q.edit_message_text(t["write_name"])
    return WAIT_NAME_INPUT

# ── Юзер ввів назву ───────────────────────────────────────────────────────
async def got_name_input(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(update.effective_user.id)
    t = TEXTS[lang]
    custom_name = (update.message.text or "").strip()
    ctx.user_data["custom_name"] = custom_name
    msg = await update.message.reply_text(t["converting"])
    ok, _ = await do_convert(ctx.bot, update.effective_chat.id, lang, ctx.user_data, ctx)
    if ok:
        await msg.edit_text(t["done"])
    else:
        await msg.edit_text(t["error"])
    # НЕ чистимо user_data тут — on_web_app_data ще потребує name_{job_id}
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
    return await ask_moment(update, ctx)

# ── Відео файл ────────────────────────────────────────────────────────────
async def on_video(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    file = update.message.video or update.message.document
    if not file:
        return
    suffix = ".mp4"
    if hasattr(file, "file_name") and file.file_name:
        suffix = os.path.splitext(file.file_name)[1] or ".mp4"
    ctx.user_data["file_id"] = file.file_id
    ctx.user_data["suffix"] = suffix
    ctx.user_data["source"] = "file"
    return await ask_moment(update, ctx)

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

# ── Глобальні callbacks (мова) ─────────────────────────────────────────────
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
            source = ctx.user_data.pop(f"source_{job_id}", "file")
            custom_name = ctx.user_data.pop(f"name_{job_id}", None)
            msg = await update.message.reply_text(t["sending"])
            await send_ringtone(ctx, update.effective_chat.id, job_id, lang, source, custom_name)
            await msg.delete()
    except Exception as e:
        logger.error(f"web_app_data error: {e}")

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
            ASK_MOMENT: [
                CallbackQueryHandler(cb_moment_start,  pattern="^moment_start$"),
                CallbackQueryHandler(cb_moment_custom, pattern="^moment_custom$"),
            ],
            ASK_CUSTOM_MOMENT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, got_custom_moment)
            ],
            ASK_NAME: [
                CallbackQueryHandler(cb_name_skip, pattern="^name_skip$"),
                CallbackQueryHandler(cb_name_give, pattern="^name_give$"),
            ],
            WAIT_NAME_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, got_name_input)
            ],
        },
        fallbacks=[CommandHandler("start", cmd_start)],
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, on_web_app_data))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, on_voice))
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(on_callback))

    logger.info("✅ ConvertRing bot running...")
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
