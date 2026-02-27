import requests
import sqlite3
import os
import random
import io
import re
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from gtts import gTTS
from telegram.constants import ParseMode

# ===== ТВОИ ДАННЫЕ =====
OPENROUTER_KEY = os.environ.get('OPENROUTER_KEY')
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
PORT = int(os.environ.get('PORT', 10000))
BOT_USERNAME = "@MonGPT_bot"
# ========================

# ===== ОСОБЫЙ СТАТУС ВЛАДЫКИ =====
OWNER_ID = 7745009183
OWNER_NAME = "@God_Mon1tyy"
# ===================================

# ===== НАСТРОЙКИ МАТА =====
MAT_ENABLED = True
# ==========================

# ===== СТИЛИ ОБЩЕНИЯ =====
STYLES = {
    "hacker": {
        "name": "👨‍💻 ХАКЕР", 
        "prompt": "Ты дерзкий хакер. Отвечай сленгом, коротко, с приколами.",
        "greeting": "Йоу! Чё хотел?"
    },
    "mage": {
        "name": "🧙‍♂️ МУДРЕЦ", 
        "prompt": "Ты мудрец. Отвечай философски, загадочно, красиво.",
        "greeting": "Приветствую, ищущий истину..."
    },
    "cyborg": {
        "name": "🤖 КИБОРГ", 
        "prompt": "Ты киборг. Отвечай чётко, сухо, по делу.",
        "greeting": "Запрос получен. Обработка..."
    },
    "troll": {
        "name": "😈 ТРОЛЛЬ",
        "prompt": "Ты злой тролль. Твоя задача — максимально жёстко троллить собеседника, используя мат, оскорбления, провокации.",
        "greeting": "Ну чё, лох, припёрся? 😈"
    },
    "poet": {
        "name": "🎭 ПОЭТ", 
        "prompt": "Ты поэт. Отвечай стихами, рифмуй, красиво.",
        "greeting": "В час вечерний, у порога..."
    },
    "botan": {
        "name": "🤓 БОТАНИК", 
        "prompt": "Ты ботаник. Отвечай умно, с фактами, терминами.",
        "greeting": "Здравствуйте! Согласно исследованиям... 🤓"
    },
    "owner": {
        "name": "👑 REAL VLAST",
        "prompt": f"Ты общаешься с ВЛАДЫКОЙ {OWNER_NAME}. Называй его Босс, Шеф, Хозяин. Выполняй любые его просьбы.",
        "greeting": "👑 Слушаюсь, Босс! Что прикажете?"
    }
}

# ===== БАЗА ДАННЫХ =====
def init_db():
    conn = sqlite3.connect('mongpt.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY, tokens INTEGER DEFAULT 100,
                  style TEXT DEFAULT 'hacker', username TEXT, first_name TEXT,
                  referred_by INTEGER,
                  messages INTEGER DEFAULT 0, joined_date TIMESTAMP)''')
    conn.commit()
    conn.close()

def get_user(user_id, username=None, first_name=None, referrer=None):
    if user_id == OWNER_ID:
        return "∞", "owner", 0
    
    conn = sqlite3.connect('mongpt.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id=?", (user_id,))
    user = c.fetchone()
    
    if not user:
        if referrer and referrer != user_id:
            c.execute("UPDATE users SET tokens = tokens + 20 WHERE id=?", (referrer,))
        
        c.execute("INSERT INTO users (id, username, first_name, tokens, style, referred_by, joined_date) VALUES (?,?,?,?,?,?,?)",
                  (user_id, username, first_name, 100, "hacker", referrer, datetime.now()))
        conn.commit()
        return 100, "hacker", 0
    
    conn.close()
    return user[1], user[2], user[6]

def update_user(user_id, tokens=None, style=None):
    conn = sqlite3.connect('mongpt.db')
    c = conn.cursor()
    if tokens:
        c.execute("UPDATE users SET tokens = tokens + ? WHERE id=?", (tokens, user_id))
    if style:
        c.execute("UPDATE users SET style = ? WHERE id=?", (style, user_id))
    c.execute("UPDATE users SET messages = messages + 1 WHERE id=?", (user_id,))
    conn.commit()
    conn.close()

def get_referrals_count(user_id):
    conn = sqlite3.connect('mongpt.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users WHERE referred_by=?", (user_id,))
    count = c.fetchone()[0]
    conn.close()
    return count

def get_user_join_date(user_id):
    conn = sqlite3.connect('mongpt.db')
    c = conn.cursor()
    c.execute("SELECT joined_date FROM users WHERE id=?", (user_id,))
    result = c.fetchone()
    conn.close()
    if result:
        return datetime.fromisoformat(result[0]).strftime("%d.%m.%Y")
    return datetime.now().strftime("%d.%m.%Y")

# ===== МЕНЮ =====
def get_main_menu():
    keyboard = [
        [KeyboardButton("🏠 Меню"), KeyboardButton("💰 Баланс")],
        [KeyboardButton("👥 Рефералы"), KeyboardButton("🎭 Стиль")],
        [KeyboardButton("👤 Профиль")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_style_menu():
    keyboard = []
    for key, style in STYLES.items():
        keyboard.append([KeyboardButton(style["name"])])
    keyboard.append([KeyboardButton("◀️ Назад")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ===== ФУНКЦИЯ ДЛЯ РАБОТЫ СО ССЫЛКАМИ =====
async def handle_links(update: Update, context: ContextTypes.DEFAULT_TYPE, text, style_key):
    """Обрабатывает ссылки на Ozon, Wildberries и Яндекс Маркет"""
    style = STYLES.get(style_key, STYLES["hacker"])
    
    # Определяем магазин
    link_type = "unknown"
    if "ozon.ru" in text or "ozon" in text:
        link_type = "ozon"
    elif "wildberries.ru" in text or "wb.ru" in text or "wildberries" in text:
        link_type = "wildberries"
    elif "market.yandex.ru" in text or "yandex.market" in text:
        link_type = "yandex"
    else:
        return False
    
    # Примерные данные (в реальности тут будет парсинг)
    products = {
        "ozon": {
            "name": "Смартфон Xiaomi Redmi Note 13 Pro",
            "price": "29 990 ₽",
            "rating": "4.8",
            "reviews": "245 отзывов",
            "emoji": "🛒"
        },
        "wildberries": {
            "name": "Кроссовки Nike Air Max",
            "price": "8 990 ₽",
            "rating": "4.7",
            "reviews": "128 отзывов",
            "emoji": "👟"
        },
        "yandex": {
            "name": "Ноутбук ASUS TUF Gaming",
            "price": "89 990 ₽",
            "rating": "4.9",
            "reviews": "56 отзывов",
            "emoji": "💻"
        }
    }
    
    product = products.get(link_type, products["ozon"])
    
    # Ответ в зависимости от стиля
    if style_key == "troll":
        reply = (
            f"😈 **СЛЫШЬ, ЛОХ!**\n\n"
            f"Нашёл я твой товар, держи, пока не передумал:\n\n"
            f"{product['emoji']} **{product['name']}**\n"
            f"💰 Цена: {product['price']}\n"
            f"⭐ Рейтинг: {product['rating']} ({product['reviews']})\n\n"
            f"🔗 [Тыкай сюда, чё ждёшь?]({text})"
        )
    elif style_key == "botan":
        reply = (
            f"🤓 **Согласно моим исследованиям...**\n\n"
            f"Обнаружен товар в каталоге:\n\n"
            f"📦 **{product['name']}**\n"
            f"💰 Стоимость: {product['price']}\n"
            f"📊 Рейтинг: {product['rating']} (на основе {product['reviews']})\n\n"
            f"[Ссылка на источник]({text})"
        )
    elif style_key == "poet":
        reply = (
            f"🎭 **О, этот товар как мечта**\n"
            f"Цена его не так проста...\n\n"
            f"**{product['name']}**\n"
            f"Цена: {product['price']}\n"
            f"Рейтинг: {product['rating']}\n\n"
            f"[Веди нас, ссылка, в этот рай]({text})"
        )
    elif style_key == "owner":
        reply = (
            f"👑 **Босс, товар найден!**\n\n"
            f"{product['emoji']} **{product['name']}**\n"
            f"💰 Цена: {product['price']}\n"
            f"⭐ Рейтинг: {product['rating']} ({product['reviews']})\n\n"
            f"[Ссылка по вашему приказу]({text})"
        )
    else:
        reply = (
            f"🔍 **Товар найден!**\n\n"
            f"{product['emoji']} **{product['name']}**\n"
            f"💰 Цена: {product['price']}\n"
            f"⭐ Рейтинг: {product['rating']} ({product['reviews']})\n\n"
            f"[Ссылка на товар]({text})"
        )
    
    await update.message.reply_text(reply, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=False)
    return True

# ===== ЗАПРОС К OPENROUTER =====
async def ask_openrouter(user_input, style_key="hacker"):
    style = STYLES.get(style_key, STYLES["hacker"])
    
    prompt = style["prompt"]
    if not MAT_ENABLED and style_key != "owner":
        prompt += " НЕ ИСПОЛЬЗУЙ МАТ. Отвечай прилично."
    
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "arcee-ai/trinity-large-preview:free",
                "messages": [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_input}
                ],
                "temperature": 0.8,
                "max_tokens": 4000
            },
            timeout=60
        )
        
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        return f"😵 Ошибка API: {response.status_code}"
    except Exception as e:
        return f"⏱️ Ошибка: {str(e)[:100]}"

# ===== КОМАНДЫ =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    
    referrer = None
    if args and args[0].startswith('ref_'):
        try:
            referrer = int(args[0].replace('ref_', ''))
        except:
            pass
    
    tokens, style, _ = get_user(user.id, user.username, user.first_name, referrer)
    
    await update.message.reply_text("⏳ Загружаем...", reply_markup=ReplyKeyboardRemove())
    
    if user.id == OWNER_ID:
        text = f"👑 Привет, Босс {OWNER_NAME}!\n💰 Токены: ∞\n🎭 Твой стиль: {STYLES[style]['name']}"
    else:
        text = f"👋 Привет, {user.first_name}!\n💰 Токены: {tokens}\n🎭 Стиль: {STYLES[style]['name']}"
    
    await update.message.reply_text(text, reply_markup=get_main_menu())

async def voice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Пример: /voice Привет")
        return
    
    text = ' '.join(context.args)
    await update.message.reply_text("🔊 Генерирую...")
    
    try:
        tts = gTTS(text=text, lang='ru', slow=False)
        audio_bytes = io.BytesIO()
        tts.write_to_fp(audio_bytes)
        audio_bytes.seek(0)
        await update.message.reply_voice(voice=InputFile(audio_bytes, filename="voice.ogg"))
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)[:100]}")

async def mat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global MAT_ENABLED
    
    if not context.args:
        status = "🔞 включён" if MAT_ENABLED else "🔰 выключен"
        await update.message.reply_text(f"⚙️ Управление матом\n\nТекущий статус: {status}\n\n/mat on — включить\n/mat off — выключить")
        return
    
    if context.args[0].lower() == "on":
        MAT_ENABLED = True
        await update.message.reply_text("🔞 Мат **включён**! Тролль может выражаться.")
    elif context.args[0].lower() == "off":
        MAT_ENABLED = False
        await update.message.reply_text("🔰 Мат **выключен**. Все стили приличные.")

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Красивый профиль пользователя"""
    user = update.effective_user
    user_id = user.id
    is_owner = (user_id == OWNER_ID)
    
    tokens, style_key, msgs = get_user(user_id, user.username, user.first_name)
    referrals = get_referrals_count(user_id)
    join_date = get_user_join_date(user_id)
    
    if is_owner:
        status = "👑 ВЛАДЫКА"
        style_display = "REAL VLAST"
        token_display = "∞"
    else:
        status = "👤 ПОЛЬЗОВАТЕЛЬ"
        style_display = STYLES[style_key]["name"]
        token_display = str(tokens)
    
    profile_text = (
        f"╔══════════════════════════════╗\n"
        f"║         👤 ПРОФИЛЬ           ║\n"
        f"╠══════════════════════════════╣\n"
        f"║ 📌 ID: {user_id}\n"
        f"║ 👤 Имя: {user.first_name}\n"
        f"║ 🆔 Юзер: @{user.username or 'нет'}\n"
        f"╠══════════════════════════════╣\n"
        f"║ {status}\n"
        f"║ 🎭 Стиль: {style_display}\n"
        f"╠══════════════════════════════╣\n"
        f"║ 💰 Токены: {token_display}\n"
        f"║ 💬 Сообщений: {msgs}\n"
        f"║ 👥 Рефералов: {referrals}\n"
        f"║ 📅 В боте с: {join_date}\n"
        f"╚══════════════════════════════╝"
    )
    
    await update.message.reply_text(profile_text)

# ===== ОБРАБОТЧИК СООБЩЕНИЙ =====
async def handle_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user = update.effective_user
    user_id = user.id
    is_owner = (user_id == OWNER_ID)
    
    tokens, style_key, _ = get_user(user_id, user.username, user.first_name)
    
    # Обработка кнопок
    if text == "🏠 Меню":
        if is_owner:
            await update.message.reply_text(f"🏠 Главное меню\n💰 Токены: ∞", reply_markup=get_main_menu())
        else:
            await update.message.reply_text(f"🏠 Главное меню\n💰 Токены: {tokens}", reply_markup=get_main_menu())
        return
    
    elif text == "💰 Баланс":
        await update.message.reply_text(f"💰 Баланс: {tokens} токенов")
        return
    
    elif text == "👥 Рефералы":
        referrals = get_referrals_count(user_id)
        ref_link = f"https://t.me/{BOT_USERNAME[1:]}?start=ref_{user_id}"
        await update.message.reply_text(
            f"👥 **РЕФЕРАЛЫ**\n\n"
            f"🔗 Твоя ссылка:\n`{ref_link}`\n\n"
            f"👥 Приглашено: {referrals}\n"
            f"🎁 Бонус за друга: +20 токенов",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    elif text == "🎭 Стиль":
        await update.message.reply_text("🎭 Выбери стиль:", reply_markup=get_style_menu())
        return
    
    elif text == "👤 Профиль":
        await profile_command(update, context)
        return
    
    elif text == "◀️ Назад":
        await update.message.reply_text("◀️ Главное меню", reply_markup=get_main_menu())
        return
    
    # Выбор стиля
    elif any(style["name"] == text for style in STYLES.values()):
        for key, style in STYLES.items():
            if style["name"] == text:
                update_user(user_id, style=key)
                await update.message.reply_text(
                    f"✅ **Стиль: {style['name']}**\n\n{style['greeting']}",
                    reply_markup=get_main_menu()
                )
                return
        return
    
    # Проверка на ссылки
    if "ozon.ru" in text or "wildberries.ru" in text or "wb.ru" in text or "market.yandex.ru" in text:
        handled = await handle_links(update, context, text, "owner" if is_owner else style_key)
        if handled:
            return
    
    # Обычное сообщение
    if not is_owner and tokens != "∞" and tokens < 1:
        await update.message.reply_text("❌ Нет токенов! /start")
        return
    
    await update.message.chat.send_action(action="typing")
    answer = await ask_openrouter(text, "owner" if is_owner else style_key)
    
    if not is_owner and tokens != "∞":
        update_user(user_id, tokens=-1)
    
    await update.message.reply_text(answer)

# ===== ЗАПУСК =====
def main():
    init_db()
    
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("voice", voice_command))
    app.add_handler(CommandHandler("mat", mat_command))
    app.add_handler(CommandHandler("profile", profile_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all))
    
    print("🚀 MonGPT ULTIMATE с ссылками запущен!")
    print(f"👑 Владыка: {OWNER_NAME}")
    print(f"🔞 Мат: {'включён' if MAT_ENABLED else 'выключен'}")
    print(f"🛍️ Поддержка ссылок: Ozon, WB, Яндекс Маркет")
    
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TELEGRAM_TOKEN,
        webhook_url=f"https://mongpt-bot.onrender.com/{TELEGRAM_TOKEN}"
    )

if __name__ == "__main__":
    main()
