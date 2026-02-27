"""
MonGPT ULTIMATE - Интерфейс как в iMessage!
Создатель: @God_Mon1tyy
Бот: @MonGPT_bot
"""

import requests
import sqlite3
import os
import random
import io
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
from telegram.constants import ParseMode
from gtts import gTTS

# ===== ТВОИ ДАННЫЕ =====
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
OPENROUTER_KEY = os.environ.get('OPENROUTER_KEY')
PORT = int(os.environ.get('PORT', 10000))
BOT_USERNAME = "@MonGPT_bot"
# ========================

# ===== ОСОБЫЙ СТАТУС СОЗДАТЕЛЯ =====
CREATOR_ID = 7745009183
CREATOR_NAME = "@God_Mon1tyy"
# ====================================

# ===== СТИЛИ ОБЩЕНИЯ =====
STYLES = {
    "hacker": {"name": "👨‍💻 ХАКЕР", "prompt": "Ты дерзкий хакер. Отвечай сленгом, коротко, с приколами.", "greeting": "Йоу, бро!"},
    "mage": {"name": "🧙‍♂️ МУДРЕЦ", "prompt": "Ты мудрец. Отвечай философски, загадочно, красиво.", "greeting": "Приветствую, путник..."},
    "cyborg": {"name": "🤖 КИБОРГ", "prompt": "Ты киборг. Отвечай чётко, сухо, по делу.", "greeting": "Запрос получлен."},
    "troll": {"name": "😈 ТРОЛЛЬ", "prompt": "Ты тролль. Подкалывай, провоцируй, но без злобы.", "greeting": "О, ещё один! 😏"},
    "poet": {"name": "🎭 ПОЭТ", "prompt": "Ты поэт. Отвечай стихами, рифмуй.", "greeting": "Приветствую тебя..."},
    "botan": {"name": "🤓 БОТАНИК", "prompt": "Ты ботаник. Отвечай умно, с фактами, терминами.", "greeting": "Здравствуйте! 🤓"},
    "lord": {"name": "👑 ВЛАДЫКА", "prompt": f"Ты общаешься с создателем @God_Mon1tyy. Отвечай уважительно, называй 'повелитель'.", "greeting": "👑 Слушаюсь, повелитель!"}
}

# ===== БАЗА ДАННЫХ =====
def init_db():
    conn = sqlite3.connect('mongpt.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY, tokens INTEGER DEFAULT 100,
                  style TEXT DEFAULT 'hacker', username TEXT, first_name TEXT,
                  messages INTEGER DEFAULT 0, joined_date TIMESTAMP)''')
    conn.commit()
    conn.close()

def get_user(user_id, username=None, first_name=None):
    if user_id == CREATOR_ID:
        return "∞", "lord", 0
    
    conn = sqlite3.connect('mongpt.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id=?", (user_id,))
    user = c.fetchone()
    
    if not user:
        c.execute("INSERT INTO users (id, username, first_name, tokens, style, joined_date) VALUES (?,?,?,?,?,?)",
                  (user_id, username, first_name, 100, "hacker", datetime.now()))
        conn.commit()
        return 100, "hacker", 0
    
    conn.close()
    return user[1], user[2], user[5]

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

# ===== ИНТЕРФЕЙС КАК В IMESSAGE =====
def get_main_menu():
    """Главное меню (снизу экрана)"""
    keyboard = [
        [KeyboardButton("🏠 Меню"), KeyboardButton("💬 Сообщение"), KeyboardButton("➕ Новый чат")],
        [KeyboardButton("⚙️ Настройки"), KeyboardButton("⭐ Premium"), KeyboardButton("📜 История")]
    ]
    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        input_field_placeholder="Напиши сообщение..."
    )

def get_settings_menu():
    """Меню настроек"""
    keyboard = [
        [KeyboardButton("🎭 Сменить стиль"), KeyboardButton("💰 Баланс")],
        [KeyboardButton("🔊 Голос"), KeyboardButton("◀️ Назад")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_style_menu():
    """Меню выбора стиля"""
    keyboard = []
    for key, style in STYLES.items():
        keyboard.append([KeyboardButton(style["name"])])
    keyboard.append([KeyboardButton("◀️ Назад")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ===== КОМАНДЫ =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    tokens, style, _ = get_user(user.id, user.username, user.first_name)
    
    if user.id == CREATOR_ID:
        text = f"👑 **С ВОЗВРАЩЕНИЕМ, {CREATOR_NAME}!**\n\n💰 Токены: ∞\n🎭 Твой стиль: ВЛАДЫКА"
    else:
        text = f"👋 **Привет, {user.first_name}!**\n\n💰 Токены: {tokens}\n🎭 Стиль: {STYLES[style]['name']}"
    
    await update.message.reply_text(
        text,
        reply_markup=get_main_menu(),
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на кнопки меню"""
    text = update.message.text
    user = update.effective_user
    user_id = user.id
    is_creator = (user_id == CREATOR_ID)
    
    # Главное меню
    if text == "🏠 Меню":
        await start(update, context)
    
    elif text == "💬 Сообщение":
        await update.message.reply_text("✍️ Напиши любое сообщение — я отвечу!")
    
    elif text == "➕ Новый чат":
        context.chat_data.clear()
        await update.message.reply_text("🔄 Новый чат начат!", reply_markup=get_main_menu())
    
    elif text == "⚙️ Настройки":
        await update.message.reply_text("⚙️ **Настройки**", reply_markup=get_settings_menu(), parse_mode=ParseMode.MARKDOWN)
    
    elif text == "⭐ Premium":
        if is_creator:
            await update.message.reply_text("👑 Ты создатель — у тебя уже ∞ токенов!")
        else:
            tokens, _, _ = get_user(user_id)
            await update.message.reply_text(f"💎 У тебя {tokens} токенов. Покупай ещё!")
    
    elif text == "📜 История":
        tokens, style, msgs = get_user(user_id)
        await update.message.reply_text(f"📊 **Статистика**\n\nСообщений: {msgs}\nТокенов: {tokens}", parse_mode=ParseMode.MARKDOWN)
    
    # Меню настроек
    elif text == "🎭 Сменить стиль":
        await update.message.reply_text("🎭 **Выбери стиль:**", reply_markup=get_style_menu(), parse_mode=ParseMode.MARKDOWN)
    
    elif text == "💰 Баланс":
        tokens, _, _ = get_user(user_id)
        await update.message.reply_text(f"💰 Твой баланс: {tokens} токенов")
    
    elif text == "🔊 Голос":
        await update.message.reply_text("🔊 Используй: /voice Привет")
    
    elif text == "◀️ Назад":
        await update.message.reply_text("◀️ Главное меню", reply_markup=get_main_menu())
    
    # Выбор стиля
    elif any(style["name"] == text for style in STYLES.values()):
        for key, style in STYLES.items():
            if style["name"] == text:
                update_user(user_id, style=key)
                await update.message.reply_text(
                    f"✅ Стиль изменён на {style['name']}\n\n{style['greeting']}",
                    reply_markup=get_main_menu()
                )
                break
    
    else:
        # Если не кнопка — передаём в AI
        await handle_message(update, context)

# ===== ГОЛОСОВЫЕ КОМАНДЫ =====
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

# ===== ЗАПРОС К OPENROUTER =====
async def ask_ai(user_input, style_key="hacker"):
    style = STYLES.get(style_key, STYLES["hacker"])
    
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "deepseek/deepseek-chat-v3-0324:free",
                "messages": [
                    {"role": "system", "content": style["prompt"]},
                    {"role": "user", "content": user_input}
                ]
            },
            timeout=30
        )
        
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        return f"😵 Ошибка API: {response.status_code}"
    except Exception as e:
        return f"⏱️ Ошибка: {str(e)[:100]}"

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
    
    if not is_creator and tokens != "∞" and tokens < 1:
        await update.message.reply_text("❌ Нет токенов! /start")
        return
    
    await update.message.chat.send_action(action="typing")
    
    answer = await ask_ai(user_input, "lord" if is_creator else style_key)
    
    if not is_creator and tokens != "∞":
        update_user(user_id, tokens=-1)
    
    await update.message.reply_text(answer, reply_markup=get_main_menu())

# ===== ЗАПУСК =====
def main():
    init_db()
    
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("voice", voice_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu))
    
    print("🚀 MonGPT с iMessage-интерфейсом запущен!")
    print(f"👑 Создатель: {CREATOR_NAME}")
    
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TELEGRAM_TOKEN,
        webhook_url=f"https://mongpt-bot.onrender.com/{TELEGRAM_TOKEN}"
    )

if __name__ == "__main__":
    main()
