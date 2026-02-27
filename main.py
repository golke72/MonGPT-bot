import requests
import sqlite3
import os
import random
import io
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
from gtts import gTTS

# ===== ТВОИ ДАННЫЕ =====
OPENROUTER_KEY = os.environ.get('OPENROUTER_KEY')
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
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
    "cyborg": {"name": "🤖 КИБОРГ", "prompt": "Ты киборг. Отвечай чётко, сухо, по делу.", "greeting": "Запрос получен."},
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
                  referred_by INTEGER,
                  messages INTEGER DEFAULT 0, joined_date TIMESTAMP)''')
    conn.commit()
    conn.close()

def get_user(user_id, username=None, first_name=None, referrer=None):
    if user_id == CREATOR_ID:
        return "∞", "lord", 0
    
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

# ===== КНОПКИ ПОД СООБЩЕНИЯМИ =====
def get_main_keyboard():
    keyboard = [
        [InlineKeyboardButton("🏠 Меню", callback_data="menu"),
         InlineKeyboardButton("💰 Баланс", callback_data="balance")],
        [InlineKeyboardButton("👥 Рефералы", callback_data="referrals"),
         InlineKeyboardButton("🎭 Стиль", callback_data="style_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_style_keyboard():
    keyboard = []
    for key, style in STYLES.items():
        keyboard.append([InlineKeyboardButton(style["name"], callback_data=f"style_{key}")])
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="menu")])
    return InlineKeyboardMarkup(keyboard)

# ===== ЗАПРОС К OPENROUTER =====
async def ask_openrouter(user_input, style_key="hacker"):
    style = STYLES.get(style_key, STYLES["hacker"])
    
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
                    {"role": "system", "content": style["prompt"]},
                    {"role": "user", "content": user_input}
                ]
            },
            timeout=30
        )
        
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        return f"😵 Ошибка {response.status_code}"
    except Exception as e:
        return f"⏱️ Ошибка"

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
    
    if user.id == CREATOR_ID:
        text = f"👑 С возвращением, создатель!\n💰 Токены: ∞\n🎭 Твой стиль: ВЛАДЫКА"
    else:
        text = f"👋 Привет, {user.first_name}!\n💰 Токены: {tokens}\n🎭 Стиль: {STYLES[style]['name']}"
    
    await update.message.reply_text(text, reply_markup=get_main_keyboard())

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
    except:
        await update.message.reply_text("❌ Ошибка")

# ===== ОБРАБОТЧИК КНОПОК =====
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    user_id = user.id
    is_creator = (user_id == CREATOR_ID)
    
    if query.data == "menu":
        tokens, style, _ = get_user(user_id, user.username, user.first_name)
        
        if is_creator:
            text = f"🏠 Главное меню\n💰 Токены: ∞\n🎭 Твой стиль: ВЛАДЫКА"
        else:
            text = f"🏠 Главное меню\n💰 Токены: {tokens}\n🎭 Стиль: {STYLES[style]['name']}"
        
        await query.edit_message_text(text, reply_markup=get_main_keyboard())
    
    elif query.data == "balance":
        tokens, _, _ = get_user(user_id)
        await query.edit_message_text(f"💰 Баланс: {tokens} токенов", reply_markup=get_main_keyboard())
    
    elif query.data == "referrals":
        referrals = get_referrals_count(user_id)
        ref_link = f"https://t.me/{BOT_USERNAME[1:]}?start=ref_{user_id}"
        text = f"👥 Рефералы\n\nСсылка: {ref_link}\nПриглашено: {referrals}\nБонус за друга: +20 токенов"
        await query.edit_message_text(text, reply_markup=get_main_keyboard())
    
    elif query.data == "style_menu":
        await query.edit_message_text("🎭 Выбери стиль:", reply_markup=get_style_keyboard())
    
    elif query.data.startswith("style_"):
        style_key = query.data.replace("style_", "")
        if style_key in STYLES:
            update_user(user_id, style=style_key)
            await query.edit_message_text(
                f"✅ Стиль: {STYLES[style_key]['name']}\n\n{STYLES[style_key]['greeting']}",
                reply_markup=get_main_keyboard()
            )

# ===== ОБРАБОТЧИК СООБЩЕНИЙ =====
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
    
    answer = await ask_openrouter(user_input, "lord" if is_creator else style_key)
    
    if not is_creator and tokens != "∞":
        update_user(user_id, tokens=-1)
    
    await update.message.reply_text(answer, reply_markup=get_main_keyboard())

# ===== ЗАПУСК =====
def main():
    init_db()
    
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("voice", voice_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("MonGPT с кнопками и стилями запущен!")
    
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TELEGRAM_TOKEN,
        webhook_url=f"https://mongpt-bot.onrender.com/{TELEGRAM_TOKEN}"
    )

if __name__ == "__main__":
    main()
