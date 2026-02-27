"""
MonGPT ULTIMATE - Молодёжная версия с кнопками и ПАМЯТЬЮ!
Создатель: @God_Mon1tyy
Бот: @MonGPT_bot
Статус: 👑 БЕСКОНЕЧНЫЕ ТОКЕНЫ ДЛЯ СОЗДАТЕЛЯ

Функции:
✅ Текст
✅ Голосовые сообщения (/voice)
✅ Кнопки-меню
✅ 7 стилей общения
✅ Без цензуры
✅ ПАМЯТЬ на день
"""

import requests
import sqlite3
import os
import re
import json
import random
import io
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
from telegram.constants import ParseMode
from gtts import gTTS

# ===== ТВОИ ДАННЫЕ =====
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
OPENROUTER_KEY = os.environ.get('OPENROUTER_KEY')
PORT = int(os.environ.get('PORT', 10000))
BOT_USERNAME = "@MonGPT_bot"
# ==========================

# ===== ОСОБЫЙ СТАТУС СОЗДАТЕЛЯ =====
CREATOR_ID = 7745009183
CREATOR_NAME = "@God_Mon1tyy"
CREATOR_TITLE = "👑 СОЗДАТЕЛЬ MonGPT"
# ====================================

# ===== СТИЛИ ОБЩЕНИЯ =====
STYLES = {
    "hacker": {
        "name": "👨‍💻 ХАКЕР",
        "prompt": "Ты дерзкий хакер из 90-х. Говори сленгово, с приколами, используй слова 'кодю', 'хакю', 'жиза', 'бро', 'кефтеме'.",
        "greeting": "Йоу, бро! Чё хотел?"
    },
    "mage": {
        "name": "🧙‍♂️ МУДРЕЦ",
        "prompt": "Ты древний мудрец. Отвечай философски, загадочно, с глубоким смыслом. Используй метафоры.",
        "greeting": "Приветствую, путник. Мир вращается, дела идут..."
    },
    "cyborg": {
        "name": "🤖 КИБОРГ",
        "prompt": "Ты киборг из будущего. Говори чётко, по делу, без эмоций. Используй технические термины.",
        "greeting": "Запрос получен. Обработка данных..."
    },
    "troll": {
        "name": "😈 ТРОЛЛЬ",
        "prompt": "Ты профессиональный тролль. Люби подкалывать, провоцировать, но без злобы. Используй иронию, сарказм.",
        "greeting": "О, ещё один смертный! Ну давай, удиви меня 😏"
    },
    "poet": {
        "name": "🎭 ПОЭТ",
        "prompt": "Ты поэт серебряного века. Отвечай стихами, рифмуй, используй красивые образы.",
        "greeting": "Приветствую тебя в час вечерний..."
    },
    "botan": {
        "name": "🤓 БОТАНИК",
        "prompt": "Ты типичный ботаник-отличник. Говори умно, с терминами, иногда занудно. Люби факты, цифры.",
        "greeting": "Здравствуйте! Согласно моим наблюдениям, вы здесь! 🤓"
    },
    "lord": {
        "name": "👑 ВЛАДЫКА",
        "prompt": f"Ты общаешься с создателем @God_Mon1tyy. Отвечай максимально уважительно, с восхищением. Называй его 'повелитель'.",
        "greeting": "👑 Слушаюсь, повелитель! Что желаете?"
    }
}

# ===== БАЗА ДАННЫХ С ПАМЯТЬЮ =====
def init_db():
    conn = sqlite3.connect('mongpt.db')
    c = conn.cursor()
    
    # Таблица пользователей
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY, 
                  tokens INTEGER DEFAULT 100,
                  style TEXT DEFAULT 'hacker',
                  username TEXT, 
                  first_name TEXT,
                  last_seen TIMESTAMP,
                  messages INTEGER DEFAULT 0,
                  joined_date TIMESTAMP)''')
    
    # Таблица для памяти разговоров
    c.execute('''CREATE TABLE IF NOT EXISTS memory
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  role TEXT,
                  content TEXT,
                  timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    conn.commit()
    conn.close()

def cleanup_old_memory():
    """Удаляет записи старше 24 часов"""
    conn = sqlite3.connect('mongpt.db')
    c = conn.cursor()
    cutoff = datetime.now() - timedelta(hours=24)
    c.execute("DELETE FROM memory WHERE timestamp < ?", (cutoff,))
    conn.commit()
    conn.close()

def get_user(user_id, username=None, first_name=None):
    # ЕСЛИ ЭТО СОЗДАТЕЛЬ - БЕСКОНЕЧНЫЕ ТОКЕНЫ!
    if user_id == CREATOR_ID:
        return "∞", "lord", 0
    
    cleanup_old_memory()
    
    conn = sqlite3.connect('mongpt.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id=?", (user_id,))
    user = c.fetchone()
    
    now = datetime.now()
    
    if not user:
        c.execute("""INSERT INTO users (id, username, first_name, tokens, style, last_seen, joined_date) 
                     VALUES (?,?,?,?,?,?,?)""",
                  (user_id, username, first_name, 100, "hacker", now, now))
        conn.commit()
        tokens = 100
        style = "hacker"
    else:
        tokens = user[1]
        style = user[2] if len(user) > 2 else "hacker"
        # Обновляем время последнего визита
        c.execute("UPDATE users SET last_seen=?, username=?, first_name=? WHERE id=?", 
                  (now, username, first_name, user_id))
        conn.commit()
    
    conn.close()
    return tokens, style, 0

def update_user(user_id, tokens=None, style=None):
    conn = sqlite3.connect('mongpt.db')
    c = conn.cursor()
    if tokens is not None:
        c.execute("UPDATE users SET tokens = tokens + ? WHERE id=?", (tokens, user_id))
    if style is not None:
        c.execute("UPDATE users SET style = ? WHERE id=?", (style, user_id))
    c.execute("UPDATE users SET messages = messages + 1, last_seen=? WHERE id=?", 
              (datetime.now(), user_id))
    conn.commit()
    conn.close()

def save_to_memory(user_id, role, content):
    """Сохраняет сообщение в память"""
    conn = sqlite3.connect('mongpt.db')
    c = conn.cursor()
    c.execute("INSERT INTO memory (user_id, role, content) VALUES (?, ?, ?)",
              (user_id, role, content))
    conn.commit()
    conn.close()

def get_recent_memory(user_id, limit=10):
    """Получает последние сообщения из памяти"""
    cleanup_old_memory()
    conn = sqlite3.connect('mongpt.db')
    c = conn.cursor()
    c.execute("""SELECT role, content FROM memory 
                 WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?""",
              (user_id, limit))
    rows = c.fetchall()
    conn.close()
    
    # Формируем контекст для AI (в хронологическом порядке)
    context = []
    for role, content in reversed(rows):
        context.append({"role": role, "content": content})
    return context

# ===== МОЛОДЁЖНЫЕ ФРАЗЫ =====
SLOGANS = ["Йоу!", "Хей!", "Салам!", "Здарова!", "Приветики!", "Бро!", "Хаюшки!"]

def random_slogan():
    return random.choice(SLOGANS)

# ===== КНОПКИ =====
def get_main_keyboard():
    keyboard = [
        [InlineKeyboardButton("🔥 Профиль", callback_data="menu_profile"),
         InlineKeyboardButton("💰 Кошелёк", callback_data="menu_balance")],
        [InlineKeyboardButton("🎭 Стиль", callback_data="menu_style"),
         InlineKeyboardButton("📊 Топ", callback_data="menu_top")],
        [InlineKeyboardButton("🔊 Голос", callback_data="menu_voice"),
         InlineKeyboardButton("❓ Помощь", callback_data="menu_help")],
        [InlineKeyboardButton("✨ Факт", callback_data="menu_fact")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_style_keyboard():
    keyboard = [
        [InlineKeyboardButton(STYLES["hacker"]["name"], callback_data="style_hacker"),
         InlineKeyboardButton(STYLES["mage"]["name"], callback_data="style_mage")],
        [InlineKeyboardButton(STYLES["cyborg"]["name"], callback_data="style_cyborg"),
         InlineKeyboardButton(STYLES["troll"]["name"], callback_data="style_troll")],
        [InlineKeyboardButton(STYLES["poet"]["name"], callback_data="style_poet"),
         InlineKeyboardButton(STYLES["botan"]["name"], callback_data="style_botan")],
        [InlineKeyboardButton(STYLES["lord"]["name"], callback_data="style_lord")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ===== КОМАНДЫ =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    tokens, style, _ = get_user(user_id, user.username, user.first_name)
    
    if user_id == CREATOR_ID:
        text = f"👑 **С ВОЗВРАЩЕНИЕМ, СОЗДАТЕЛЬ {CREATOR_NAME}!** 👑"
    else:
        style_name = STYLES.get(style, STYLES["hacker"])["name"]
        text = (f"{random_slogan()} **{user.first_name}**!\n\n"
                f"💎 Токены: **{tokens}**\n"
                f"🎭 Стиль: **{style_name}**\n\n"
                f"👇 **Жми кнопки!**")
    
    await update.message.reply_text(text, reply_markup=get_main_keyboard(), parse_mode=ParseMode.MARKDOWN)

async def style_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎭 **ВЫБЕРИ СТИЛЬ:**",
        reply_markup=get_style_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )

async def voice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Пример: `/voice Привет`", parse_mode=ParseMode.MARKDOWN)
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

# ===== ОБРАБОТЧИК КНОПОК =====
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if query.data == "menu_profile":
        tokens, style, _ = get_user(user_id)
        style_name = STYLES.get(style, STYLES["hacker"])["name"]
        await query.edit_message_text(
            f"👤 **ПРОФИЛЬ**\n\nID: `{user_id}`\nСтиль: {style_name}\nТокены: {tokens}",
            parse_mode=ParseMode.MARKDOWN
        )
    
    elif query.data == "menu_balance":
        tokens, _, _ = get_user(user_id)
        await query.edit_message_text(f"💰 **Баланс:** {tokens} токенов", parse_mode=ParseMode.MARKDOWN)
    
    elif query.data == "menu_style":
        await query.edit_message_text("🎭 **ВЫБЕРИ СТИЛЬ:**", reply_markup=get_style_keyboard(), parse_mode=ParseMode.MARKDOWN)
    
    elif query.data == "menu_top":
        await query.edit_message_text(f"📊 **ТОП**\n\n1. {CREATOR_NAME} — ∞ 👑", parse_mode=ParseMode.MARKDOWN)
    
    elif query.data == "menu_voice":
        await query.edit_message_text("🔊 **ГОЛОС**\n\n/voice Привет", parse_mode=ParseMode.MARKDOWN)
    
    elif query.data == "menu_help":
        await query.edit_message_text(
            f"❓ **ПОМОЩЬ**\n\n/start - меню\n/style - стиль\n/voice - голос\n\n👑 {CREATOR_NAME}",
            parse_mode=ParseMode.MARKDOWN
        )
    
    elif query.data == "menu_fact":
        facts = ["🧠 Мозг ест 20% энергии", "🍌 Банан — ягода", "🐙 У осьминога 3 сердца"]
        await query.edit_message_text(f"✨ **Факт:** {random.choice(facts)}")
    
    elif query.data.startswith("style_"):
        style_key = query.data.replace("style_", "")
        if style_key in STYLES:
            update_user(user_id, style=style_key)
            await query.edit_message_text(f"✅ **Стиль: {STYLES[style_key]['name']}**\n\n{STYLES[style_key]['greeting']}", parse_mode=ParseMode.MARKDOWN)

# ===== ЗАПРОС К OPENROUTER =====
async def ask_ai(user_input, style_key="hacker", user_id=None):
    style = STYLES.get(style_key, STYLES["hacker"])
    
    # Получаем контекст из памяти
    context_messages = []
    if user_id:
        context_messages = get_recent_memory(user_id, 5)
    
    # Формируем сообщения для AI
    messages = [{"role": "system", "content": style["prompt"]}]
    messages.extend(context_messages)
    messages.append({"role": "user", "content": user_input})
    
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "deepseek/deepseek-chat-v3-0324:free",
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 2000,
                "provider": {"ignore": ["targon"]}
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            return data['choices'][0]['message']['content']
        else:
            return f"😵 Ошибка {response.status_code}"
    except Exception as e:
        return f"⏱️ {str(e)[:100]}"

# ===== ОСНОВНОЙ ОБРАБОТЧИК =====
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    is_creator = (user_id == CREATOR_ID)
    
    if not update.message.text:
        await update.message.reply_text("❌ Пока только текст")
        return
    
    user_input = update.message.text
    tokens, style_key, _ = get_user(user_id, user.username, user.first_name)
    
    # Сохраняем сообщение пользователя в память
    save_to_memory(user_id, "user", user_input)
    
    # Проверка токенов
    if not is_creator and tokens != "∞" and tokens < 1:
        await update.message.reply_text("❌ Нет токенов! /start")
        return
    
    await update.message.chat.send_action(action="typing")
    
    # Получаем ответ
    answer = await ask_ai(user_input, style_key if not is_creator else "lord", user_id)
    
    # Сохраняем ответ бота в память
    save_to_memory(user_id, "assistant", answer)
    
    # Списываем токен
    if not is_creator and tokens != "∞":
        update_user(user_id, tokens=-1)
    
    creator_note = f"\n\n_👑 {CREATOR_NAME}_" if is_creator else ""
    await update.message.reply_text(f"{answer}{creator_note}")

# ===== ЗАПУСК =====
def main():
    init_db()
    
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("style", style_command))
    app.add_handler(CommandHandler("voice", voice_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🚀 MonGPT ULTIMATE с ПАМЯТЬЮ запущен!")
    print(f"👑 Создатель: {CREATOR_NAME}")
    
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TELEGRAM_TOKEN,
        webhook_url=f"https://mongpt-bot.onrender.com/{TELEGRAM_TOKEN}"
    )

if __name__ == "__main__":
    main()
