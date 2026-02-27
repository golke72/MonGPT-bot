"""
MonGPT - для Render.com
Работает 24/7, отвечает мгновенно
"""

import requests
import sqlite3
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from telegram.constants import ParseMode

# ===== ТВОИ ДАННЫЕ =====
TELEGRAM_TOKEN = "8735549741:AAFt4ydTV5BFGhVv_iKKJbO3TxfefbIpEc0"
POE_API_KEY = "PKkByuEiScElrfyx7VGeztMX6xoDQv_O5p8G3Bwio_M"
BOT_NAME = "MonGPT"
ADMIN_ID = 7745009183
PORT = int(os.environ.get('PORT', 10000))
# =======================

# База данных
def init_db():
    conn = sqlite3.connect('mongpt.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY, tokens INTEGER DEFAULT 50,
                  username TEXT, first_name TEXT, last_daily TEXT)''')
    conn.commit()
    conn.close()

def get_user(user_id, username=None, first_name=None):
    conn = sqlite3.connect('mongpt.db')
    c = conn.cursor()
    c.execute("SELECT tokens FROM users WHERE id=?", (user_id,))
    row = c.fetchone()
    
    if not row:
        c.execute("INSERT INTO users (id, username, first_name, tokens) VALUES (?,?,?,?)",
                  (user_id, username, first_name, 50))
        conn.commit()
        tokens = 50
    else:
        tokens = row[0]
        if username or first_name:
            c.execute("UPDATE users SET username=?, first_name=? WHERE id=?",
                      (username, first_name, user_id))
            conn.commit()
    conn.close()
    return tokens

def use_token(user_id):
    conn = sqlite3.connect('mongpt.db')
    c = conn.cursor()
    c.execute("UPDATE users SET tokens = tokens - 1 WHERE id=?", (user_id,))
    conn.commit()
    conn.close()

def add_tokens(user_id, amount):
    conn = sqlite3.connect('mongpt.db')
    c = conn.cursor()
    c.execute("UPDATE users SET tokens = tokens + ? WHERE id=?", (amount, user_id))
    conn.commit()
    conn.close()

# Команды бота
async def start(update: Update, context):
    user = update.effective_user
    tokens = get_user(user.id, user.username, user.first_name)
    
    keyboard = [
        [InlineKeyboardButton("💰 Баланс", callback_data="balance")],
        [InlineKeyboardButton("❓ Помощь", callback_data="help")]
    ]
    
    await update.message.reply_text(
        f"🤙 **Йоу, {user.first_name}!**\n\n"
        f"Это **MonGPT** на сервере — отвечаю мгновенно! ⚡\n"
        f"💰 Токенов: {tokens}\n"
        f"💬 Просто пиши сообщения!",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )

async def button_handler(update: Update, context):
    query = update.callback_query
    await query.answer()
    
    if query.data == "balance":
        tokens = get_user(query.from_user.id)
        await query.edit_message_text(f"💰 Твой баланс: {tokens} токенов")
    
    elif query.data == "help":
        await query.edit_message_text(
            "❓ **Помощь**\n\n"
            "/start - начало\n"
            "/balance - баланс\n\n"
            "1 сообщение = 1 токен\n"
            "Админ: @God_Mon1tyy"
        )

async def balance_command(update: Update, context):
    user = update.effective_user
    tokens = get_user(user.id, user.username, user.first_name)
    await update.message.reply_text(f"💰 Твой баланс: {tokens} токенов")

async def handle_message(update: Update, context):
    user = update.effective_user
    text = update.message.text
    
    # Получаем токены
    tokens = get_user(user.id, user.username, user.first_name)
    
    # Проверка баланса
    if tokens < 1:
        await update.message.reply_text("❌ Нет токенов! /start чтобы получить 50")
        return
    
    # Сообщаем что бот думает
    await update.message.chat.send_action(action="typing")
    
    try:
        # Запрос к Poe API
        response = requests.post(
            "https://api.poe.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {POE_API_KEY}"},
            json={
                "model": BOT_NAME,
                "messages": [{"role": "user", "content": text}]
            },
            timeout=15
        )
        
        if response.status_code == 200:
            answer = response.json()['choices'][0]['message']['content']
            use_token(user.id)
            
            # Новый баланс
            conn = sqlite3.connect('mongpt.db')
            c = conn.cursor()
            c.execute("SELECT tokens FROM users WHERE id=?", (user.id,))
            new_balance = c.fetchone()[0]
            conn.close()
            
            await update.message.reply_text(f"{answer}\n\n_💎 Осталось: {new_balance}_")
        else:
            await update.message.reply_text("😵 Ошибка API, попробуй позже")
            
    except Exception as e:
        await update.message.reply_text(f"⏱️ Ошибка: {str(e)[:50]}")

# Админ-команды
async def admin_command(update: Update, context):
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Только для админа!")
        return
    
    if not context.args:
        await update.message.reply_text(
            "🛠 **Админ-команды**\n\n"
            "/admin add 7745009183 1000 - добавить токены"
        )
        return
    
    if context.args[0] == "add" and len(context.args) >= 3:
        target_id = int(context.args[1])
        amount = int(context.args[2])
        add_tokens(target_id, amount)
        await update.message.reply_text(f"✅ Добавлено {amount} токенов {target_id}")

# Запуск
if __name__ == "__main__":
    init_db()
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("balance", balance_command))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print(f"🚀 MonGPT запущен на Render (порт {PORT})")
    
    # Для Render используем webhook
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TELEGRAM_TOKEN,
        webhook_url=f"https://your-app-name.onrender.com/{TELEGRAM_TOKEN}"
    )
