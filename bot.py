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
ADMIN_ID   = 482920649
ADSGRAM_TOKEN   = "1c9daa734e124fcc8f40309f58b55dcb"
ADSGRAM_BLOCK   = "27752"

# Статистика
stats = {"success": 0, "errors": 0, "users": set()}

async def notify_admin(bot, text: str):
    try:
        await bot.send_message(chat_id=ADMIN_ID, text=text)
    except Exception as e:
        logger.error(f"notify_admin error: {e}")

async def send_daily_stats(bot):
    text = (
        f"📊 Статистика за сьогодні:\n"
        f"✅ Успішних конвертацій: {stats['success']}\n"
        f"❌ Помилок: {stats['errors']}\n"
        f"👥 Унікальних юзерів: {len(stats['users'])}"
    )
    await notify_admin(bot, text)
    # Скидаємо статистику
    stats["success"] = 0
    stats["errors"] = 0
    stats["users"] = set()

async def schedule_daily_stats(app):
    while True:
        now = asyncio.get_event_loop().time()
        # Чекаємо до наступної 20:00
        import datetime
        now_dt = datetime.datetime.now()
        target = now_dt.replace(hour=20, minute=0, second=0, microsecond=0)
        if now_dt >= target:
            target += datetime.timedelta(days=1)
        wait_sec = (target - now_dt).total_seconds()
        await asyncio.sleep(wait_sec)
        await send_daily_stats(app.bot)

ASK_MOMENT, ASK_CUSTOM_MOMENT, ASK_NAME, WAIT_NAME_INPUT = range(4)

TEXTS = {
    "uk": {
        "welcome": "🎶 *ConvertRing* — конвертер рингтонів для iPhone\n\nНадішли будь-що, зроблю з цього рингтон для твого дзвінку:\n • Відео з галереї\n • TikTok / Instagram / YouTube Music — лінки тільки з застосунків, не з браузерів\n • Голосове повідомлення\n\nЯ:\n • ✂️ Виріжу потрібний момент\n • 💾 Збережу з твоєю назвою\n\nЗа пару хвилин у тебе унікальний рингтон якого ні в кого немає!",
        "converting": "⏳ Отримую та конвертую...",
        "done": "🎵 Рингтон готовий! Зараз надішлю файл...",
        "ad_warning": "Зараз надійде кілька рекламних повідомлень, а після них — твій рингтон 👇",
        "ad_warning": "📣 Нижче буде пару реклам — після них файл з рингтоном 👇",
        "get_btn": "🎵 Отримати рингтон",
        "error": "❌ Не вдалося обробити. Спробуй інше відео або посилання.",
        "unsupported": "❌ Надішли відео, голосове або посилання на TikTok/Instagram/YouTube Music",
        "press_button": "Натисни одну з кнопок вище 👆",
        "sending": "📤 Надсилаю рингтон...",
        "ringtone_caption": "🎵 Ось твій рингтон!\n\nЯк встановити:\n1. Натисни на файл\n2. Тапни «Використовувати як мелодію» в правому нижньому куті\n3. Готово! ✅ Галочка біля рингтону підтверджує що все ок\n\n—\nЯкщо потребуєш допомоги з встановленням, обирай в боті кнопку «Як встановити рингтон»\n\nPS: Ти можеш встановити персональний рингтон на різних абонентів: друга, бесті, родину тощо. Тому не зупиняйся ❤️",
        "after_ringtone": "Сподобалось? Роби ще! Кожен контакт заслуговує свій рингтон 🎵\nПросто відправ мені новий лінк.",
        "cta": "Кидай відео, лінк або голосове — і почнемо! 🎵",
        "how_to": "📖 Як встановити рингтон:\n1. Натисни на файл\n2. Тапни «Використовувати як мелодію» в правому нижньому куті\n3. Готово! ✅ Галочка біля рингтону підтверджує що все ок\n\n👥 Як поставити різним контактам:\n1. Відкрий потрібний контакт\n2. Натисни «Редагувати»\n3. Обери «Рингтон» і знайди свій файл у списку мелодій\n4. Збережи ✅\n\n💡 Щоб не губитись, давай рингтонам імена при генерації.",
        "ask_moment": "🎵 З якого місця зробити рингтон?",
        "from_start_btn": "▶️ З початку",
        "custom_moment_btn": "✂️ Вибрати момент",
        "ask_custom_moment": "⏱ Введи час у форматі `хв:сек`\nЯ відріжу 40 секунд від цього моменту.\nНаприклад: `00:30` або `01:34`",
        "invalid_moment": "❌ Не розумію формат. Спробуй ще раз.\n\nПриклади: `00:30` `01:34`",
        "ask_name": "💾 Хочеш дати назву рингтону?\nЗ цією назвою він збережеться в тебе в телефоні.",
        "skip_btn": "⏭️ Пропустити",
        "name_btn": "✏️ Дати назву",
        "write_name": "✏️ Напиши назву рингтону:",
        "home_btn": "🏠 Головна",
        "how_btn": "📖 Як встановити рингтон",
    },
    "ru": {
        "welcome": "🎶 *ConvertRing* — конвертер рингтонов для iPhone\n\nОтправь что угодно, сделаю из этого рингтон для твоего звонка:\n • Видео из галереи\n • TikTok / Instagram / YouTube Music — ссылки только из приложений, не из браузера\n • Голосовое сообщение\n\nЯ:\n • ✂️ Вырежу нужный момент\n • 💾 Сохраню с твоим названием\n\nЗа пару минут у тебя уникальный рингтон которого ни у кого нет!",
        "converting": "⏳ Загружаю и конвертирую...",
        "done": "🎵 Рингтон готов! Сейчас отправлю файл...",
        "ad_warning": "Сейчас придёт несколько рекламных сообщений, а после них — твой рингтон 👇",
        "get_btn": "🎵 Получить рингтон",
        "error": "❌ Не удалось обработать. Попробуй другое видео или ссылку.",
        "unsupported": "❌ Отправь видео, голосовое или ссылку на TikTok/Instagram/YouTube Music",
        "press_button": "Нажми одну из кнопок выше 👆",
        "sending": "📤 Отправляю рингтон...",
        "ringtone_caption": "🎵 Вот твой рингтон!\n\nКак установить:\n1. Нажми на файл\n2. Тапни «Использовать как мелодию» в правом нижнем углу\n3. Готово! ✅ Галочка рядом с рингтоном подтверждает что всё ок\n\n—\nЕсли нужна помощь с установкой, выбирай в боте кнопку «Как установить рингтон»\n\nPS: Ты можешь установить персональный рингтон для разных контактов: друга, подруги, семьи и т.д. Так что не останавливайся ❤️",
        "after_ringtone": "Понравилось? Делай ещё! Каждый контакт заслуживает свой рингтон 🎵\nПросто отправь мне новую ссылку.",
        "cta": "Кидай видео, ссылку или голосовое — и начнём! 🎵",
        "how_to": "📖 Как установить рингтон:\n1. Нажми на файл\n2. Тапни «Использовать как мелодию» в правом нижнем углу\n3. Готово! ✅ Галочка рядом с рингтоном подтверждает что всё ок\n\n👥 Как поставить разным контактам:\n1. Открой нужный контакт\n2. Нажми «Редактировать»\n3. Выбери «Рингтон» и найди свой файл в списке мелодий\n4. Сохрани ✅\n\n💡 Чтобы не запутаться, давай рингтонам имена при генерации.",
        "ask_moment": "🎵 С какого места сделать рингтон?",
        "from_start_btn": "▶️ С начала",
        "custom_moment_btn": "✂️ Выбрать момент",
        "ask_custom_moment": "⏱ Введи время в формате `мин:сек`\nЯ отрежу 40 секунд от этого момента.\nНапример: `00:30` или `01:34`",
        "invalid_moment": "❌ Не понимаю формат. Попробуй ещё раз.\n\nПримеры: `00:30` `01:34`",
        "ask_name": "💾 Хочешь дать название рингтону?\nС этим названием он сохранится у тебя в телефоне.",
        "skip_btn": "⏭️ Пропустить",
        "name_btn": "✏️ Дать название",
        "write_name": "✏️ Напиши название рингтона:",
        "home_btn": "🏠 Главная",
        "how_btn": "📖 Как установить рингтон",
    },
    "en": {
        "welcome": "🎶 *ConvertRing* — iPhone ringtone converter\n\nSend me anything, I'll turn it into a ringtone for your calls:\n • Video from your gallery\n • TikTok / Instagram / YouTube Music — links from apps only, not from browser\n • Voice message\n\nI will:\n • ✂️ Cut the right moment\n • 💾 Save with your name\n\nIn a couple of minutes you'll have a unique ringtone nobody else has!",
        "converting": "⏳ Downloading and converting...",
        "done": "🎵 Ringtone is ready! Sending your file...",
        "ad_warning": "You'll receive a few ad messages, and after them — your ringtone 👇",
        "get_btn": "🎵 Get ringtone",
        "error": "❌ Failed to process. Try another video or link.",
        "unsupported": "❌ Send a video, voice message or TikTok/Instagram/YouTube Music link",
        "press_button": "Tap one of the buttons above 👆",
        "sending": "📤 Sending ringtone...",
        "ringtone_caption": "🎵 Here's your ringtone!\n\nHow to install:\n1. Tap on the file\n2. Tap «Use as Ringtone» in the bottom right corner\n3. Done! ✅ A checkmark next to the ringtone means everything is set\n\n—\nIf you need help with installation, tap «How to install» in the bot\n\nPS: You can set personal ringtones for different contacts — friends, family, and more. Keep going ❤️",
        "after_ringtone": "Enjoyed it? Make more! Every contact deserves their own ringtone 🎵\nJust send me a new link.",
        "cta": "Drop a video, link or voice message — let's go! 🎵",
        "how_to": "📖 How to install the ringtone:\n1. Tap on the file\n2. Tap «Use as Ringtone» in the bottom right corner\n3. Done! ✅ A checkmark next to the ringtone means everything is set\n\n👥 How to set different ringtones for contacts:\n1. Open the contact\n2. Tap «Edit»\n3. Choose «Ringtone» and find your file in the list\n4. Save ✅\n\n💡 To stay organised, give your ringtones names when generating them.",
        "ask_moment": "🎵 From which part to make the ringtone?",
        "from_start_btn": "▶️ From the beginning",
        "custom_moment_btn": "✂️ Choose moment",
        "ask_custom_moment": "⏱ Enter time in `min:sec` format\nI'll cut 40 seconds from this moment.\nFor example: `00:30` or `01:34`",
        "invalid_moment": "❌ I don't understand the format. Try again.\n\nExamples: `00:30` `01:34`",
        "ask_name": "💾 Want to name your ringtone?\nIt will be saved with this name on your phone.",
        "skip_btn": "⏭️ Skip",
        "name_btn": "✏️ Give a name",
        "write_name": "✏️ Write the ringtone name:",
        "home_btn": "🏠 Home",
        "how_btn": "📖 How to install",
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

def nav_keyboard(lang: str):
    t = TEXTS[lang]
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(t["home_btn"], callback_data="nav_home"),
        InlineKeyboardButton(t["how_btn"],  callback_data="nav_how"),
    ]])

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

async def show_adsgram_ad(bot, chat_id: int, user_id: int, lang: str) -> bool:
    """Показує рекламу від Adsgram в чаті. Повертає True якщо успішно."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                f"https://api.adsgram.ai/advbot",
                params={
                    "tgid": user_id,
                    "blockid": ADSGRAM_BLOCK,
                    "language": lang,
                    "token": ADSGRAM_TOKEN,
                }
            )
            if r.status_code != 200:
                return False
            data = r.json()
            text_html = data.get("text_html", "")
            button_name = data.get("button_name", "Перейти")
            click_url = data.get("click_url", "")
            if not click_url:
                return False
            await bot.send_message(
                chat_id=chat_id,
                text=text_html,
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(button_name, url=click_url)
                ]])
            )
            return True
    except Exception as e:
        logger.error(f"adsgram error: {e}")
        return False

async def send_ringtone(ctx, chat_id: int, job_id: str, lang: str, source: str = "file", custom_name: str = None):
    t = TEXTS[lang]
    filename = make_filename(source, job_id, custom_name)
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.get(f"{API_BASE}/download/{job_id}")
            if r.status_code == 200:
                await ctx.bot.send_document(
                    chat_id=chat_id,
                    document=r.content,
                    filename=filename,
                    caption=t["ringtone_caption"],
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton(t["how_btn"], callback_data="nav_how")
                    ]])
                )
                # Прибираємо ReplyKeyboard окремим повідомленням
                await ctx.bot.send_message(
                    chat_id=chat_id,
                    text=t["after_ringtone"],
                    reply_markup=ReplyKeyboardRemove()
                )
    except Exception as e:
        logger.error(f"send_ringtone error: {e}")

async def do_convert(bot, chat_id: int, lang: str, user_data: dict, ctx=None):
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
            stats["errors"] += 1
            await notify_admin(bot, f"⚠️ Конвертація не вдалась\nЮзер ID: {user_data.get('user_id', '?')}\nДжерело: {source}")
            return False, None

        if ctx is not None:
            ctx.user_data[f"source_{job_id}"] = source
            ctx.user_data[f"name_{job_id}"] = custom_name
            stats["success"] += 1

        # Показуємо 3 реклами Adsgram підряд
        # В приватному боті chat_id = user_id
        user_id = ctx.user_data.get("user_id") if ctx else chat_id
        adsgram_user_id = user_id or chat_id
        await bot.send_message(chat_id=chat_id, text=TEXTS[lang]["ad_warning"])
        await show_adsgram_ad(bot, chat_id, adsgram_user_id, lang)
        await asyncio.sleep(1)
        await show_adsgram_ad(bot, chat_id, adsgram_user_id, lang)
        await asyncio.sleep(1)
        await show_adsgram_ad(bot, chat_id, adsgram_user_id, lang)
        await asyncio.sleep(1)

        # Надсилаємо файл одразу без міні-апп
        custom_name_val = ctx.user_data.get(f"name_{job_id}") if ctx else None
        await send_ringtone(ctx, chat_id, job_id, lang, source, custom_name_val)
        return True, job_id
    except Exception as e:
        logger.error(f"do_convert error: {e}")
        stats["errors"] += 1
        await notify_admin(bot, f"⚠️ Помилка конвертації\nДжерело: {source}\n{str(e)[:100]}")
        return False, None

async def ask_moment(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(update.effective_user.id)
    t = TEXTS[lang]
    await update.message.reply_text(t["ask_moment"], reply_markup=moment_keyboard(lang))
    return ASK_MOMENT

async def cb_moment_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    lang = get_lang(q.from_user.id)
    t = TEXTS[lang]
    ctx.user_data["start"] = 0
    await q.edit_message_text(t["ask_name"], reply_markup=name_keyboard(lang))
    return ASK_NAME

async def cb_moment_custom(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    lang = get_lang(q.from_user.id)
    t = TEXTS[lang]
    await q.edit_message_text(t["ask_custom_moment"], parse_mode="Markdown")
    return ASK_CUSTOM_MOMENT

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
    return ConversationHandler.END

async def cb_name_give(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    lang = get_lang(q.from_user.id)
    t = TEXTS[lang]
    await q.edit_message_text(t["write_name"])
    return WAIT_NAME_INPUT

async def got_name_input(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(update.effective_user.id)
    t = TEXTS[lang]
    text = (update.message.text or "").strip()
    # Якщо юзер скидає новий лінк — починаємо заново
    if is_url(text):
        ctx.user_data.clear()
        ctx.user_data["url"] = text
        ctx.user_data["source"] = get_source_from_url(text)
        return await ask_moment(update, ctx)
    ctx.user_data["custom_name"] = text
    msg = await update.message.reply_text(t["converting"])
    ok, _ = await do_convert(ctx.bot, update.effective_chat.id, lang, ctx.user_data, ctx)
    if ok:
        await msg.edit_text(t["done"])
    else:
        await msg.edit_text(t["error"])
    return ConversationHandler.END

async def unexpected_text_in_moment(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Юзер пише текст замість кнопки на кроці вибору моменту"""
    text = (update.message.text or "").strip()
    lang = get_lang(update.effective_user.id)
    t = TEXTS[lang]
    # Якщо це новий лінк — починаємо заново
    if is_url(text):
        ctx.user_data.clear()
        ctx.user_data["url"] = text
        ctx.user_data["source"] = get_source_from_url(text)
        return await ask_moment(update, ctx)
    await update.message.reply_text(t["press_button"])
    return ASK_MOMENT

async def unexpected_text_in_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Юзер пише текст замість кнопки на кроці назви"""
    lang = get_lang(update.effective_user.id)
    t = TEXTS[lang]
    await update.message.reply_text(t["press_button"])
    return ASK_NAME

async def url_received(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if not is_url(text):
        lang = get_lang(update.effective_user.id)
        await update.message.reply_text(TEXTS[lang]["unsupported"])
        return ConversationHandler.END
    lang = get_lang(update.effective_user.id)
    ctx.user_data["url"] = text
    ctx.user_data["source"] = get_source_from_url(text)
    ctx.user_data["user_id"] = update.effective_user.id
    return await ask_moment(update, ctx)

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
    ctx.user_data["user_id"] = update.effective_user.id
    return await ask_moment(update, ctx)

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear()
    user_id = update.effective_user.id
    stats["users"].add(user_id)
    lang = user_lang.get(user_id)
    if lang:
        await update.message.reply_text(
            TEXTS[lang]["welcome"],
            parse_mode="Markdown"
        )
        await update.message.reply_text(TEXTS[lang]["cta"])
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

    if q.data == "nav_home":
        ctx.user_data.clear()
        await q.message.reply_text(t["welcome"], parse_mode="Markdown")
        await q.message.reply_text(t["cta"])
    elif q.data == "nav_how":
        await q.message.reply_text(
            t["how_to"],
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(t["home_btn"], callback_data="nav_home")
            ]])
        )
    elif q.data.startswith("lang_"):
        new_lang = q.data.replace("lang_", "")
        user_lang[user_id] = new_lang
        await q.edit_message_text(
            TEXTS[new_lang]["welcome"],
            parse_mode="Markdown"
        )
        await q.message.reply_text(TEXTS[new_lang]["cta"])
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

    # Якщо голосове довше 30 сек — питаємо момент і назву як для відео
    if voice.duration and voice.duration > 30:
        ctx.user_data["file_id"] = voice.file_id
        ctx.user_data["suffix"] = ".ogg"
        ctx.user_data["source"] = "voice"
        ctx.user_data["user_id"] = update.effective_user.id
        return await ask_moment(update, ctx)

    # Якщо коротше 30 сек — одразу конвертуємо
    t = TEXTS[lang]
    ctx.user_data["user_id"] = update.effective_user.id
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
            await update.message.reply_text(t["ad_warning"])
            await show_adsgram_ad(ctx.bot, update.effective_chat.id, update.effective_user.id, lang)
            await asyncio.sleep(1)
            await show_adsgram_ad(ctx.bot, update.effective_chat.id, update.effective_user.id, lang)
            await asyncio.sleep(1)
            await show_adsgram_ad(ctx.bot, update.effective_chat.id, update.effective_user.id, lang)
            await asyncio.sleep(1)
            await send_ringtone(ctx, update.effective_chat.id, job_id, lang, "voice", None)
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
            MessageHandler(filters.VOICE | filters.AUDIO, on_voice),
        ],
        states={
            ASK_MOMENT: [
                CallbackQueryHandler(cb_moment_start,  pattern="^moment_start$"),
                CallbackQueryHandler(cb_moment_custom, pattern="^moment_custom$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, unexpected_text_in_moment),
            ],
            ASK_CUSTOM_MOMENT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, got_custom_moment)
            ],
            ASK_NAME: [
                CallbackQueryHandler(cb_name_skip, pattern="^name_skip$"),
                CallbackQueryHandler(cb_name_give, pattern="^name_give$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, unexpected_text_in_name),
            ],
            WAIT_NAME_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, got_name_input)
            ],
        },
        fallbacks=[CommandHandler("start", cmd_start)],
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, on_web_app_data))
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(on_callback))

    logger.info("✅ ConvertRing bot running...")
    loop = asyncio.get_event_loop()
    loop.create_task(schedule_daily_stats(app))
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
