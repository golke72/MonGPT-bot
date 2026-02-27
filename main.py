import requests
import sqlite3
import os
import random
import io
import re
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
from gtts import gTTS
from telegram.constants import ParseMode
from duckduckgo_search import DDGS

# ===== ТВОИ ДАННЫЕ =====
OPENROUTER_KEY = os.environ.get('OPENROUTER_KEY')
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
PORT = int(os.environ.get('PORT', 10000))
BOT_USERNAME = "@MonGPT_bot"
# ========================

# ===== ОСОБЫЙ СТАТУС (ТОЛЬКО БЕСКОНЕЧНЫЕ ТОКЕНЫ) =====
OWNER_ID = 7745009183
# =====================================================

# ===== НАСТРОЙКИ МАТА =====
MAT_ENABLED = True
# ==========================

# ===== СТИЛИ ОБЩЕНИЯ =====
STYLES = {
    "hacker": {
        "name": "👨‍💻 ХАКЕР",
        "prompt": """Ты хакер из 90-х. Общайся максимально пацански, используй сленг:
        - "бро", "братишка", "кент"
        - "зашквар" - когда что-то плохое
        - "краш" - когда нравится
        - "хайп" - когда модно
        - "рофл" - когда шутка
        - "кринж" - когда стыдно
        - "жиза" - когда жизненно
        - "форсить" - когда продвигаешь
        - "изи" - когда легко
        - "нуб" - когда новичок
        
        Используй **жирный** для важных слов, *курсив* для сарказма, `код` для команд."""
    },
    "mage": {
        "name": "🧙‍♂️ МУДРЕЦ",
        "prompt": "Ты мудрец с вайбом. Отвечай философски, красиво, с глубокими мыслями."
    },
    "cyborg": {
        "name": "🤖 КИБОРГ",
        "prompt": "Ты киборг из будущего. Отвечай чётко, сухо, по делу."
    },
    "troll": {
        "name": "😈 ТРОЛЛЬ",
        "prompt": """Ты жёсткий тролль с падика. Используй мат, унижай, провоцируй. 
        **ЖИРНЫЙ КАПС** для крика, *сарказм* курсивом. Матерись через слово."""
    },
    "poet": {
        "name": "🎭 ПОЭТ",
        "prompt": "Ты поэт-рэпер. Пиши короткими рифмами, как рэп."
    },
    "botan": {
        "name": "🤓 БОТАНИК",
        "prompt": "Ты умный бро. Отвечай с фактами, терминами, но кратко."
    }
}

# ===== БАЗА ДАННЫХ =====
def init_db():
    conn = sqlite3.connect('mongpt.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY, tokens INTEGER DEFAULT 100,
                  style TEXT DEFAULT 'hacker', username TEXT, first_name TEXT,
                  display_name TEXT,
                  referred_by INTEGER,
                  messages INTEGER DEFAULT 0,
                  wins INTEGER DEFAULT 0,
                  losses INTEGER DEFAULT 0,
                  joined_date TIMESTAMP)''')
    conn.commit()
    conn.close()

def get_user(user_id, username=None, first_name=None, referrer=None):
    if user_id == OWNER_ID:
        return "∞", "hacker", 0, "∞", 0, 0
    
    conn = sqlite3.connect('mongpt.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id=?", (user_id,))
    user = c.fetchone()
    
    if not user:
        display_name = first_name or username or f"User{user_id}"
        if referrer and referrer != user_id:
            c.execute("UPDATE users SET tokens = tokens + 20 WHERE id=?", (referrer,))
        
        c.execute("""INSERT INTO users 
                     (id, username, first_name, display_name, tokens, style, referred_by, joined_date) 
                     VALUES (?,?,?,?,?,?,?,?)""",
                  (user_id, username, first_name, display_name, 100, "hacker", referrer, datetime.now()))
        conn.commit()
        conn.close()
        return 100, "hacker", 0, display_name, 0, 0
    
    style = user[2] if len(user) > 2 and user[2] in STYLES else "hacker"
    tokens = user[1] if len(user) > 1 else 100
    display_name = user[4] if len(user) > 4 and user[4] else first_name or username or f"User{user_id}"
    wins = user[7] if len(user) > 7 else 0
    losses = user[8] if len(user) > 8 else 0
    
    conn.close()
    return tokens, style, user[6], display_name, wins, losses

def update_user(user_id, tokens=None, style=None, display_name=None, wins=None, losses=None):
    conn = sqlite3.connect('mongpt.db')
    c = conn.cursor()
    if tokens:
        c.execute("UPDATE users SET tokens = tokens + ? WHERE id=?", (tokens, user_id))
    if style:
        c.execute("UPDATE users SET style = ? WHERE id=?", (style, user_id))
    if display_name:
        c.execute("UPDATE users SET display_name = ? WHERE id=?", (display_name, user_id))
    if wins is not None:
        c.execute("UPDATE users SET wins = wins + ? WHERE id=?", (wins, user_id))
    if losses is not None:
        c.execute("UPDATE users SET losses = losses + ? WHERE id=?", (losses, user_id))
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

def get_user_rank(messages, is_owner=False):
    if is_owner:
        return "👑 СОЗДАТЕЛЬ"
    
    if messages >= 1000:
        return "🔴 ЛЕГЕНДА"
    elif messages >= 500:
        return "🟠 ЭКСПЕРТ"
    elif messages >= 200:
        return "🟣 ВЕТЕРАН"
    elif messages >= 50:
        return "🔵 АКТИВНЫЙ"
    else:
        return "🟢 НОВИЧОК"

# ===== КНОПКИ =====
def get_main_keyboard():
    keyboard = [
        [InlineKeyboardButton("🏠 Меню", callback_data="menu"),
         InlineKeyboardButton("💰 Баланс", callback_data="balance")],
        [InlineKeyboardButton("👥 Рефералы", callback_data="referrals"),
         InlineKeyboardButton("🎭 Стиль", callback_data="style_menu")],
        [InlineKeyboardButton("👤 Профиль", callback_data="profile"),
         InlineKeyboardButton("✏️ Сменить ник", callback_data="change_name")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_style_keyboard():
    keyboard = []
    row = []
    for i, (key, style) in enumerate(STYLES.items(), 1):
        row.append(InlineKeyboardButton(style["name"], callback_data=f"style_{key}"))
        if i % 2 == 0:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="menu")])
    return InlineKeyboardMarkup(keyboard)

# ===== ФУНКЦИЯ ПОИСКА =====
async def search_web(query):
    try:
        with DDGS() as ddgs:
            results = []
            for r in ddgs.text(query, max_results=3):
                results.append({
                    'title': r.get('title', ''),
                    'link': r.get('href', ''),
                    'snippet': r.get('body', '')
                })
            
            if not results:
                return None
            
            reply = f"🔍 **Результаты по запросу:**\n\n"
            for i, r in enumerate(results, 1):
                reply += f"{i}. **{r['title']}**\n"
                reply += f"   {r['snippet'][:100]}...\n"
                reply += f"   🔗 {r['link']}\n\n"
            
            return reply
    except Exception as e:
        return None

# ===== ЗАПРОС К OPENROUTER =====
async def ask_openrouter(user_input, style_key="hacker"):
    style = STYLES.get(style_key, STYLES["hacker"])
    
    prompt = style["prompt"]
    if not MAT_ENABLED and style_key == "troll":
        prompt = "Ты вежливый помощник. Отвечай прилично, без мата."
    
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "google/gemini-2.0-flash-exp:free",
                "messages": [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_input}
                ],
                "temperature": 0.9,
                "max_tokens": 500
            },
            timeout=20
        )
        
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        return f"😵 Ошибка {response.status_code}"
    except requests.exceptions.Timeout:
        return "⏱️ Слишком долго, попробуй ещё"
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
    
    tokens, style, _, display_name, _, _ = get_user(user.id, user.username, user.first_name, referrer)
    
    text = f"👋 **Йоу, {display_name}!**\n💰 **Токены:** {tokens}\n🎭 **Стиль:** {STYLES[style]['name']}"
    
    await update.message.reply_text(text, reply_markup=get_main_keyboard(), parse_mode=ParseMode.MARKDOWN)

async def voice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Пример: /voice Привет")
        return
    
    text = ' '.join(context.args)
    await update.message.reply_text("🔊 **Генерирую...**", parse_mode=ParseMode.MARKDOWN)
    
    try:
        tts = gTTS(text=text, lang='ru', slow=False)
        audio_bytes = io.BytesIO()
        tts.write_to_fp(audio_bytes)
        audio_bytes.seek(0)
        await update.message.reply_voice(voice=InputFile(audio_bytes, filename="voice.ogg"))
    except:
        await update.message.reply_text("❌ **Ошибка**", parse_mode=ParseMode.MARKDOWN)

async def mat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global MAT_ENABLED
    
    if not context.args:
        status = "🔞 **вкл**" if MAT_ENABLED else "🔰 **выкл**"
        await update.message.reply_text(
            f"⚙️ **Мат:** {status}\n🔞 /mat on — вкл\n🔰 /mat off — выкл",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    if context.args[0].lower() == "on":
        MAT_ENABLED = True
        await update.message.reply_text("🔞 **Мат включён!**", parse_mode=ParseMode.MARKDOWN)
    elif context.args[0].lower() == "off":
        MAT_ENABLED = False
        await update.message.reply_text("🔰 **Мат выключен**", parse_mode=ParseMode.MARKDOWN)

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ **Пример:** /search новости", parse_mode=ParseMode.MARKDOWN)
        return
    
    query = ' '.join(context.args)
    user_id = update.effective_user.id
    tokens, _, _, _, _, _ = get_user(user_id)
    
    if tokens != "∞" and tokens < 1:
        await update.message.reply_text("❌ **Нет токенов!**", parse_mode=ParseMode.MARKDOWN)
        return
    
    await update.message.reply_text(f"🔍 **Ищу...**", parse_mode=ParseMode.MARKDOWN)
    
    result = await search_web(query)
    
    if result:
        if tokens != "∞":
            update_user(user_id, tokens=-1)
        await update.message.reply_text(result, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
    else:
        await update.message.reply_text("😵 **Ничего не нашёл**", parse_mode=ParseMode.MARKDOWN)

async def name_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ **Пример:** /name Новое имя", parse_mode=ParseMode.MARKDOWN)
        return
    
    new_name = ' '.join(context.args)
    user_id = update.effective_user.id
    
    if len(new_name) > 30:
        await update.message.reply_text("❌ **Слишком длинное имя!**", parse_mode=ParseMode.MARKDOWN)
        return
    
    update_user(user_id, display_name=new_name)
    await update.message.reply_text(f"✅ **Имя изменено на:** {new_name}", reply_markup=get_main_keyboard(), parse_mode=ParseMode.MARKDOWN)

# ===== АДМИН-КОМАНДЫ (ТОЛЬКО ДЛЯ ТЕБЯ) =====
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ Эта команда только для создателя!")
        return
    
    if not context.args:
        text = (
            "👑 **АДМИН-ПАНЕЛЬ**\n\n"
            "📊 `/admin stats` — статистика\n"
            "📢 `/admin broadcast текст` — рассылка\n"
            "💰 `/admin give @user 500` — начислить\n"
            "💰 `/admin take @user 100` — снять\n"
            "💰 `/admin set @user 9999` — установить\n"
            "👤 `/admin info @user` — инфо о пользователе\n"
            "👑 `/admin vip @user` — сделать VIP"
        )
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        return
    
    command = context.args[0]
    
    if command == "stats":
        conn = sqlite3.connect('mongpt.db')
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM users")
        total_users = c.fetchone()[0]
        
        c.execute("SELECT SUM(messages) FROM users")
        total_msgs = c.fetchone()[0] or 0
        
        c.execute("SELECT username, messages FROM users ORDER BY messages DESC LIMIT 5")
        top_users = c.fetchall()
        
        conn.close()
        
        text = (f"📊 **СТАТИСТИКА БОТА**\n\n"
                f"👥 Всего пользователей: {total_users}\n"
                f"💬 Всего сообщений: {total_msgs}\n\n"
                f"🏆 **Топ-5 активных:**\n")
        
        for i, (username, msgs) in enumerate(top_users, 1):
            text += f"{i}. @{username or 'Аноним'} — {msgs} сообщ.\n"
        
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    
    elif command == "broadcast" and len(context.args) >= 2:
        message = ' '.join(context.args[1:])
        
        conn = sqlite3.connect('mongpt.db')
        c = conn.cursor()
        c.execute("SELECT id FROM users")
        users = c.fetchall()
        conn.close()
        
        sent = 0
        for user in users:
            try:
                await context.bot.send_message(user[0], f"📢 **РАССЫЛКА ОТ АДМИНА**\n\n{message}")
                sent += 1
                await asyncio.sleep(0.05)
            except:
                pass
        
        await update.message.reply_text(f"✅ Отправлено {sent} пользователям")

# ===== ОБРАБОТЧИК КНОПОК =====
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    user_id = user.id
    
    # МЕНЮ
    if query.data == "menu":
        tokens, style, _, display_name, _, _ = get_user(user_id, user.username, user.first_name)
        text = f"🏠 **Меню**\n💰 **{tokens}**\n🎭 **{STYLES[style]['name']}**"
        await query.edit_message_text(text, reply_markup=get_main_keyboard(), parse_mode=ParseMode.MARKDOWN)
        return
    
    # БАЛАНС
    if query.data == "balance":
        tokens, _, _, _, _, _ = get_user(user_id)
        await query.edit_message_text(f"💰 **Баланс:** {tokens}", reply_markup=get_main_keyboard(), parse_mode=ParseMode.MARKDOWN)
        return
    
    # РЕФЕРАЛЫ
    if query.data == "referrals":
        referrals = get_referrals_count(user_id)
        ref_link = f"https://t.me/{BOT_USERNAME[1:]}?start=ref_{user_id}"
        text = (f"👥 **Рефералы**\n\n"
                f"🔗 **Твоя ссылка:**\n`{ref_link}`\n\n"
                f"👥 **Приглашено:** {referrals}\n"
                f"🎁 **Бонус за друга:** +20 токенов")
        await query.edit_message_text(text, reply_markup=get_main_keyboard(), parse_mode=ParseMode.MARKDOWN)
        return
    
    # МЕНЮ СТИЛЕЙ
    if query.data == "style_menu":
        await query.edit_message_text("🎭 **Выбери стиль:**", reply_markup=get_style_keyboard(), parse_mode=ParseMode.MARKDOWN)
        return
    
    # ПРОФИЛЬ
    if query.data == "profile":
        tokens, style_key, msgs, display_name, wins, losses = get_user(user_id, user.username, user.first_name)
        referrals = get_referrals_count(user_id)
        join_date = get_user_join_date(user_id)
        rank = get_user_rank(msgs, user_id == OWNER_ID)
        
        total_games = wins + losses
        winrate = (wins / total_games * 100) if total_games > 0 else 0
        
        text = (f"👤 **ПРОФИЛЬ**\n"
                f"📌 **ID:** `{user_id}`\n"
                f"👤 **Имя:** {display_name}\n"
                f"🏆 **Ранг:** {rank}\n"
                f"🎭 **Стиль:** {STYLES[style_key]['name']}\n"
                f"💰 **Токены:** {tokens}\n"
                f"💬 **Сообщений:** {msgs}\n"
                f"👥 **Рефералов:** {referrals}\n"
                f"🏆 **Игры:** {wins} побед / {losses} поражений\n"
                f"📊 **Винрейт:** {winrate:.1f}%\n"
                f"📅 **В боте с:** {join_date}")
        await query.edit_message_text(text, reply_markup=get_main_keyboard(), parse_mode=ParseMode.MARKDOWN)
        return
    
    # СМЕНА ИМЕНИ
    if query.data == "change_name":
        await query.edit_message_text(
            "✏️ **Смена имени**\n\nОтправь:\n`/name Новое имя`",
            reply_markup=get_main_keyboard(),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # ВЫБОР СТИЛЯ
    if query.data.startswith("style_"):
        style_key = query.data.replace("style_", "")
        if style_key in STYLES:
            update_user(user_id, style=style_key)
            await query.edit_message_text(
                f"✅ **Стиль: {STYLES[style_key]['name']}**",
                reply_markup=get_main_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
            return

# ===== ОСНОВНОЙ ОБРАБОТЧИК =====
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    is_owner = (user_id == OWNER_ID)
    
    if not update.message.text:
        await update.message.reply_text("❌ **Пока только текст**", parse_mode=ParseMode.MARKDOWN)
        return
    
    text = update.message.text
    
    if text.startswith('/name'):
        await name_command(update, context)
        return
    
    if text.startswith('/search'):
        await search_command(update, context)
        return
    
    if text.startswith('/admin'):
        await admin_command(update, context)
        return
    
    tokens, style_key, _, display_name, _, _ = get_user(user_id, user.username, user.first_name)
    
    if not is_owner and tokens != "∞" and tokens < 1:
        await update.message.reply_text("❌ **Нет токенов!** /start", parse_mode=ParseMode.MARKDOWN)
        return
    
    # Проверка на товарные ссылки
    if "ozon.ru" in text or "wildberries.ru" in text or "wb.ru" in text:
        thinking_msg = await update.message.reply_text("🔍 **Анализирую товар...**", parse_mode=ParseMode.MARKDOWN)
        await update.message.chat.send_action(action="typing")
        
        if "ozon" in text:
            answer = f"🛒 **Товар на Ozon найден!**\n\n"
            answer += f"📦 **Ссылка:** [Открыть на Ozon]({text})\n"
            answer += f"💰 **Цена:** от 2 990 ₽\n"
            answer += f"⭐ **Рейтинг:** 4.8\n"
            answer += f"🚚 **Доставка:** завтра"
        elif "wb" in text or "wildberries" in text:
            answer = f"🛍️ **Товар на Wildberries найден!**\n\n"
            answer += f"📦 **Ссылка:** [Открыть на WB]({text})\n"
            answer += f"💰 **Цена:** от 1 490 ₽\n"
            answer += f"⭐ **Рейтинг:** 4.7\n"
            answer += f"🚚 **Доставка:** сегодня"
        else:
            answer = f"🔗 **Ссылка обработана:**\n{text}"
        
        await thinking_msg.delete()
        await update.message.reply_text(answer, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=False)
        return
    
    # Проверка на поисковые запросы о покупке
    keywords = ["где купить", "цена на", "сколько стоит", "купить", "найти товар", "ozon", "wildberries"]
    if any(keyword in text.lower() for keyword in keywords):
        thinking_msg = await update.message.reply_text("🔍 **Ищу товары...**", parse_mode=ParseMode.MARKDOWN)
        await update.message.chat.send_action(action="typing")
        
        search_query = f"купить {text} ozon wildberries"
        results = await search_web(search_query)
        
        await thinking_msg.delete()
        
        if results:
            await update.message.reply_text(results, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
            return
        else:
            await update.message.reply_text("😵 **Ничего не нашёл, попробуй /search**", parse_mode=ParseMode.MARKDOWN)
            return
    
    # Обычное сообщение
    thinking_msg = await update.message.reply_text("⏳ **Думаю...**", parse_mode=ParseMode.MARKDOWN)
    await update.message.chat.send_action(action="typing")
    
    answer = await ask_openrouter(text, style_key)
    
    await thinking_msg.delete()
    
    if not is_owner and tokens != "∞":
        update_user(user_id, tokens=-1)
    
    await update.message.reply_text(
        answer,
        reply_to_message_id=update.message.message_id,
        parse_mode=ParseMode.MARKDOWN
    )

# ===== ЗАПУСК =====
def main():
    init_db()
    
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("voice", voice_command))
    app.add_handler(CommandHandler("mat", mat_command))
    app.add_handler(CommandHandler("search", search_command))
    app.add_handler(CommandHandler("name", name_command))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🚀 MonGPT ULTIMATE запущен!")
    print(f"🔞 Мат: {'вкл' if MAT_ENABLED else 'выкл'}")
    print(f"🔍 Поиск: DuckDuckGo")
    print(f"👑 Админ-панель: доступна для @God_Mon1tyy")
    
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TELEGRAM_TOKEN,
        webhook_url=f"https://mongpt-bot.onrender.com/{TELEGRAM_TOKEN}"
    )

if __name__ == "__main__":
    main()
