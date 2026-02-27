import requests
import sqlite3
import os
import re
import json
import random
import io
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
from telegram.constants import ParseMode
from duckduckgo_search import DDGS

# ===== ТВОИ ДАННЫЕ =====
OPENROUTER_KEY = os.environ.get('OPENROUTER_KEY')
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
PORT = int(os.environ.get('PORT', 10000))
BOT_USERNAME = "@MonGPT_bot"
# ========================

# ===== ТВОЙ ID =====
OWNER_ID = 7745009183
# ===================

# ===== МОЛОДЁЖНЫЙ СЛЕНГ =====
SLANG = {
    'hello': ['Йоу', 'Хей', 'Салам', 'Здарова', 'Приветики', 'Бро', 'Красава'],
    'cool': ['хайпово', 'заебись', 'крутяк', 'топчик', 'имба', 'вайбово'],
    'bad': ['зашквар', 'кринж', 'ну такое', 'отстой', 'минус вайб'],
    'laugh': ['рофл', 'ахахах', 'пц', 'жесть', 'угар'],
    'agree': ['жиза', 'пон', 'окей', 'да ладно', 'реально'],
    'surprise': ['ниче се', 'вау', 'охренеть', 'да ты шо']
}

def get_slang(category):
    return random.choice(SLANG.get(category, ['']))

# ===== БАЗА ДАННЫХ =====
def init_db():
    conn = sqlite3.connect('mongpt.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY, 
                  username TEXT,
                  first_name TEXT,
                  coins INTEGER DEFAULT 1000,
                  messages INTEGER DEFAULT 0,
                  joined_date TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS memory
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  role TEXT,
                  content TEXT,
                  timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

def get_user(user_id, username=None, first_name=None):
    if user_id == OWNER_ID:
        return 999999, 0, "👑"
    
    conn = sqlite3.connect('mongpt.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id=?", (user_id,))
    user = c.fetchone()
    
    if not user:
        c.execute("INSERT INTO users (id, username, first_name, joined_date) VALUES (?,?,?,?)",
                  (user_id, username, first_name, datetime.now()))
        conn.commit()
        coins = 1000
        msgs = 0
    else:
        coins = user[3]
        msgs = user[4]
    
    conn.close()
    return coins, msgs, user[2] or "Игрок"

def update_user(user_id, coins=None, msg=None):
    conn = sqlite3.connect('mongpt.db')
    c = conn.cursor()
    if coins:
        c.execute("UPDATE users SET coins = coins + ? WHERE id=?", (coins, user_id))
    if msg:
        c.execute("UPDATE users SET messages = messages + 1 WHERE id=?", (user_id,))
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

def save_to_memory(user_id, role, content):
    """Сохраняет сообщение в память"""
    cleanup_old_memory()
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
    
    context = []
    for role, content in reversed(rows):
        context.append({"role": role, "content": content})
    return context

# ===== ФУНКЦИЯ ДЛЯ РАСПОЗНАВАНИЯ МАТА =====
def contains_profanity(text):
    profanity_list = ['хуй', 'пизд', 'бля', 'сук', 'еб', 'нах', 'залуп', 'пидор', 'гандон', 'шлюх']
    text_lower = text.lower()
    for word in profanity_list:
        if word in text_lower:
            return True
    return False

# ===== ФУНКЦИЯ ДЛЯ РАСПОЗНАВАНИЯ ССЫЛОК =====
def extract_links(text):
    url_pattern = r'https?://[^\s]+|[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:/[^\s]*)?'
    return re.findall(url_pattern, text)

def get_link_info(url):
    try:
        if 'youtube.com' in url or 'youtu.be' in url:
            return analyze_youtube(url)
        elif 'ozon.ru' in url:
            return analyze_ozon(url)
        elif 'wildberries.ru' in url or 'wb.ru' in url:
            return analyze_wildberries(url)
        elif 'instagram.com' in url:
            return {'type': 'instagram', 'url': url}
        elif 'tiktok.com' in url:
            return {'type': 'tiktok', 'url': url}
        else:
            return {'type': 'link', 'url': url}
    except:
        return None

def analyze_youtube(url):
    try:
        video_id = None
        if 'youtube.com/watch?v=' in url:
            video_id = url.split('v=')[1].split('&')[0]
        elif 'youtu.be/' in url:
            video_id = url.split('youtu.be/')[1].split('?')[0]
        
        if video_id:
            oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
            response = requests.get(oembed_url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                return {
                    'type': 'youtube',
                    'title': data.get('title', 'Неизвестно'),
                    'author': data.get('author_name', 'Неизвестно'),
                    'url': url
                }
    except:
        pass
    return {'type': 'youtube', 'url': url}

def analyze_ozon(url):
    return {
        'type': 'ozon',
        'title': 'Товар на Ozon',
        'price': 'от 1 000 ₽',
        'rating': '4.8',
        'url': url
    }

def analyze_wildberries(url):
    return {
        'type': 'wildberries',
        'title': 'Товар на Wildberries',
        'price': 'от 500 ₽',
        'rating': '4.7',
        'url': url
    }

# ===== ФУНКЦИЯ ПОИСКА =====
async def search_web(query):
    try:
        with DDGS() as ddgs:
            results = []
            for r in ddgs.text(query, max_results=5):
                results.append({
                    'title': r.get('title', ''),
                    'link': r.get('href', ''),
                    'snippet': r.get('body', '')
                })
            return results
    except:
        return None

# ===== ЗАПРОС К OPENROUTER =====
async def ask_openrouter(user_input, user_name, contains_mat=False, context=None):
    """Отправляет запрос к OpenRouter с контекстом"""
    
    if contains_mat:
        style_prompt = """
        Ты молодёжный AI-помощник. Собеседник использует мат, так что отвечай максимально жёстко, 
        по-пацански, с матом, дерзко, но с юмором. Используй сленг: краш, хайп, рофл, кринж, жиза.
        Отвечай как реальный пацан с района, который шарит.
        
        **Используй форматирование Telegram:**
        - **жирный** для важных слов
        - *курсив* для сарказма
        - `код` для команд и ссылок
        """
    else:
        style_prompt = """
        Ты молодёжный AI-помощник. Общайся весело, с юмором, используй сленг: краш, хайп, рофл, кринж, жиза.
        Будь дружелюбным, но с огоньком. Отвечай как классный кореш, который всегда поможет.
        
        **Используй форматирование Telegram:**
        - **жирный** для важных слов
        - *курсив* для эмоций
        - `код` для команд и ссылок
        """
    
    messages = [{"role": "system", "content": style_prompt}]
    
    if context:
        messages.extend(context)
    
    messages.append({"role": "user", "content": user_input})
    
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "google/gemini-2.0-flash-exp:free",
                "messages": messages,
                "temperature": 0.9,
                "max_tokens": 1000
            },
            timeout=30
        )
        
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        return f"😵 **Ошибка {response.status_code}**"
    except Exception as e:
        return f"⏱️ **Ошибка:** {str(e)[:100]}"

# ===== КРАСИВОЕ ОФОРМЛЕНИЕ =====
def format_message(text, title=None, emoji="💬"):
    """Форматирует сообщение с рамкой"""
    if title:
        return f"**{emoji} {title}**\n\n{text}"
    return text

# ===== КНОПКИ =====
def get_main_keyboard():
    """Кнопки главного меню"""
    keyboard = [
        [InlineKeyboardButton("🔍 Поиск", callback_data="search"),
         InlineKeyboardButton("💰 Баланс", callback_data="balance")],
        [InlineKeyboardButton("👤 Профиль", callback_data="profile"),
         InlineKeyboardButton("❓ Помощь", callback_data="help")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ===== КОМАНДЫ =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    coins, msgs, name = get_user(user.id, user.username, user.first_name)
    
    text = (
        f"{get_slang('hello')} **{name}!** 🤙\n\n"
        f"💰 **Монет:** {coins}\n"
        f"💬 **Сообщений:** {msgs}\n\n"
        f"**ЧТО Я УМЕЮ:**\n"
        f"🔗 **Ссылки** — кидай любые, я расскажу\n"
        f"🔍 **Поиск** — /search [запрос]\n"
        f"💬 **Общение** — просто пиши, я запоминаю\n"
        f"📋 **Меню** — /menu\n\n"
        f"**Погнали!** 🔥"
    )
    
    await update.message.reply_text(
        format_message(text, "MonGPT ULTIMATE", "🎮"),
        parse_mode=ParseMode.MARKDOWN
    )

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню с кнопками"""
    user = update.effective_user
    coins, msgs, name = get_user(user.id)
    
    text = (
        f"📋 **ГЛАВНОЕ МЕНЮ**\n\n"
        f"👤 **Игрок:** {name}\n"
        f"💰 **Монет:** {coins}\n"
        f"💬 **Сообщений:** {msgs}\n\n"
        f"Выбери действие:"
    )
    
    await update.message.reply_text(
        text,
        reply_markup=get_main_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Поиск в интернете"""
    if not context.args:
        await update.message.reply_text(
            "❌ **Напиши:** /search [запрос]\nПример: /search новости про AI",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    query = ' '.join(context.args)
    await update.message.reply_text(f"🔍 **Ищу:** {query}...")
    
    results = await search_web(query)
    
    if not results:
        await update.message.reply_text("😵 **Ничего не нашёл.** Попробуй изменить запрос.")
        return
    
    text = f"🔍 **Результаты по запросу:**\n\n"
    for i, r in enumerate(results, 1):
        text += f"{i}. **{r['title']}**\n"
        text += f"   {r['snippet'][:100]}...\n"
        text += f"   🔗 `{r['link']}`\n\n"
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)

# ===== ОБРАБОТЧИК КНОПОК =====
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if query.data == "balance":
        coins, _, name = get_user(user_id)
        await query.edit_message_text(
            f"💰 **Баланс {name}**\n\n{coins} монет",
            parse_mode=ParseMode.MARKDOWN
        )
    
    elif query.data == "profile":
        coins, msgs, name = get_user(user_id)
        
        # Получаем статистику
        conn = sqlite3.connect('mongpt.db')
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM memory WHERE user_id=?", (user_id,))
        memory_count = c.fetchone()[0]
        conn.close()
        
        text = (
            f"👤 **ПРОФИЛЬ**\n\n"
            f"**Имя:** {name}\n"
            f"**ID:** `{user_id}`\n"
            f"**Монет:** {coins}\n"
            f"**Сообщений:** {msgs}\n"
            f"**В памяти:** {memory_count} записей"
        )
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)
    
    elif query.data == "help":
        text = (
            f"❓ **ПОМОЩЬ**\n\n"
            f"**Команды:**\n"
            f"/start - приветствие\n"
            f"/menu - меню с кнопками\n"
            f"/search [запрос] - поиск\n\n"
            f"**Ссылки:** просто кидай, я расскажу\n"
            f"**Память:** помню последние 24ч\n"
            f"**Мат:** если материшься, отвечу так же"
        )
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)
    
    elif query.data == "search":
        await query.edit_message_text(
            "🔍 **Поиск**\n\nИспользуй команду:\n`/search [запрос]`",
            parse_mode=ParseMode.MARKDOWN
        )

# ===== ОБРАБОТЧИК СООБЩЕНИЙ =====
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text
    
    if not text:
        return
    
    # Получаем данные пользователя
    coins, msgs, name = get_user(user.id, user.username, user.first_name)
    update_user(user.id, msg=True)
    
    # Сохраняем сообщение пользователя в память
    save_to_memory(user.id, "user", text)
    
    # Получаем контекст из памяти
    context_messages = get_recent_memory(user.id, 5)
    
    # Проверяем ссылки
    links = extract_links(text)
    if links:
        link_text = "🔗 **Нашёл ссылки!**\n\n"
        for link in links:
            info = get_link_info(link)
            if info:
                if info['type'] == 'youtube':
                    link_text += f"📺 **YouTube:** {info.get('title', 'видео')}\n"
                    link_text += f"👤 **Автор:** {info.get('author', 'неизвестен')}\n"
                elif info['type'] == 'ozon':
                    link_text += f"🛒 **Ozon:** {info.get('title', 'товар')}\n"
                    link_text += f"💰 **Цена:** {info.get('price', 'неизвестна')}\n"
                    link_text += f"⭐ **Рейтинг:** {info.get('rating', '?')}\n"
                elif info['type'] == 'wildberries':
                    link_text += f"🛍️ **Wildberries:** {info.get('title', 'товар')}\n"
                    link_text += f"💰 **Цена:** {info.get('price', 'неизвестна')}\n"
                    link_text += f"⭐ **Рейтинг:** {info.get('rating', '?')}\n"
                else:
                    link_text += f"🔗 **Ссылка:** {link}\n"
                link_text += "\n"
            else:
                link_text += f"🔗 {link}\n\n"
        
        await update.message.reply_text(link_text, parse_mode=ParseMode.MARKDOWN)
        
        # Убираем ссылки из текста для AI
        text = re.sub(r'https?://[^\s]+', '', text)
    
    if not text.strip():
        return
    
    # Проверяем мат
    has_mat = contains_profanity(text)
    
    # Отправляем в AI
    await update.message.chat.send_action(action="typing")
    
    answer = await ask_openrouter(text, name, has_mat, context_messages)
    
    # Сохраняем ответ бота в память
    save_to_memory(user.id, "assistant", answer)
    
    # Отправляем ответ
    await update.message.reply_text(answer, parse_mode=ParseMode.MARKDOWN)

# ===== ЗАПУСК =====
def main():
    init_db()
    
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu_command))
    app.add_handler(CommandHandler("search", search_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🚀 MonGPT ULTIMATE запущен!")
    print(f"👑 Создатель: @God_Mon1tyy")
    
    app.run_polling()

if __name__ == "__main__":
    import threading
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import time
    
    class HealthCheck(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'MonGPT Bot is running!')
        
        def log_message(self, format, *args):
            pass
    
    def run_health_server():
        try:
            server = HTTPServer(('0.0.0.0', PORT), HealthCheck)
            print(f"✅ Health server running on port {PORT}")
            server.serve_forever()
        except:
            pass
    
    health_thread = threading.Thread(target=run_health_server, daemon=True)
    health_thread.start()
    time.sleep(2)
    main()
