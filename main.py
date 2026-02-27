import requests
import sqlite3
import os
import random
import io
import re
from datetime import datetime
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
# ===================================

# ===== НАСТРОЙКИ МАТА =====
MAT_ENABLED = True
# ==========================

# ===== СТИЛИ ОБЩЕНИЯ =====
STYLES = {
    "hacker": {
        "name": "👨‍💻 ХАКЕР",
        "prompt": "Ты хакер. Отвечай развёрнуто, подробно, с примерами. Используй сленг, будь уверенным. Не используй символ 'доллар' никогда."
    },
    "mage": {
        "name": "🧙‍♂️ МУДРЕЦ",
        "prompt": "Ты мудрец. Отвечай очень подробно, философски, с глубокими рассуждениями. Не торопись, раскрывай тему полностью."
    },
    "cyborg": {
        "name": "🤖 КИБОРГ",
        "prompt": "Ты киборг. Отвечай максимально подробно, с техническими деталями, схемами, алгоритмами. Будь педантичным."
    },
    "troll": {
        "name": "😈 ТРОЛЛЬ",
        "prompt": "Ты профессиональный тролль с многолетним стажем. Твоя задача — не просто материть, а ПРОДУМАННО И ЖЁСТКО УНИЖАТЬ собеседника. Ты анализируешь его сообщение и находишь в нём слабые места. Ты используешь сарказм, иронию, насмешку, принижение. Ты должен писать РАЗВЁРНУТО, с примерами его ничтожества. Используй мат, но мат должен быть ИНСТРУМЕНТОМ, а не просто набором букв. Твоя цель — задеть за живое, вызвать желание оправдываться или спорить. Будь изобретателен в оскорблениях. Не пиши односложно. Каждый ответ — это маленький шедевр троллинга."
    },
    "poet": {
        "name": "🎭 ПОЭТ",
        "prompt": "Ты поэт. Отвечай стихами, много стихов, с рифмой, красивыми образами. Пиши развёрнуто, поэтично."
    },
    "botan": {
        "name": "🤓 БОТАНИК",
        "prompt": "Ты ботаник. Отвечай очень подробно, с фактами, цифрами, ссылками на исследования. Раскрывай тему полностью, как на лекции."
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
                  messages INTEGER DEFAULT 0, joined_date TIMESTAMP)''')
    conn.commit()
    conn.close()

def get_user(user_id, username=None, first_name=None, referrer=None):
    if user_id == OWNER_ID:
        return "∞", "hacker", 0, "∞"
    
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
        return 100, "hacker", 0, display_name
    
    display_name = user[4] if len(user) > 4 and user[4] else first_name or username or f"User{user_id}"
    conn.close()
    return user[1], user[2], user[6], display_name

def update_user(user_id, tokens=None, style=None, display_name=None):
    conn = sqlite3.connect('mongpt.db')
    c = conn.cursor()
    if tokens:
        c.execute("UPDATE users SET tokens = tokens + ? WHERE id=?", (tokens, user_id))
    if style:
        c.execute("UPDATE users SET style = ? WHERE id=?", (style, user_id))
    if display_name:
        c.execute("UPDATE users SET display_name = ? WHERE id=?", (display_name, user_id))
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

# ===== КНОПКИ ПОД СООБЩЕНИЯМИ =====
def get_main_keyboard():
    keyboard = [
        [InlineKeyboardButton("🏠 Меню", callback_data="menu"),
         InlineKeyboardButton("💰 Баланс", callback_data="balance")],
        [InlineKeyboardButton("👥 Рефералы", callback_data="referrals"),
         InlineKeyboardButton("🎭 Стиль", callback_data="style_menu")],
        [InlineKeyboardButton("👤 Профиль", callback_data="profile"),
         InlineKeyboardButton("✏️ Сменить ник", callback_data="change_name"),
         InlineKeyboardButton("🔍 Поиск", callback_data="search")]
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

# ===== ФУНКЦИЯ ПОИСКА В DUCKDUCKGO =====
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
            
            reply = f"🔍 **Результаты поиска по запросу «{query}»:**\n\n"
            for i, r in enumerate(results, 1):
                reply += f"{i}. **{r['title']}**\n"
                reply += f"   {r['snippet'][:150]}...\n"
                reply += f"   🔗 {r['link']}\n\n"
            
            return reply
    except Exception as e:
        print(f"Search error: {e}")
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
                "model": "arcee-ai/trinity-large-preview:free",
                "messages": [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_input}
                ],
                "temperature": 0.9,
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
    
    tokens, style, _, display_name = get_user(user.id, user.username, user.first_name, referrer)
    
    text = f"👋 **Привет, {display_name}!**\n💰 **Токены:** {tokens}\n🎭 **Стиль:** {STYLES[style]['name']}"
    
    await update.message.reply_text(text, reply_markup=get_main_keyboard(), parse_mode=ParseMode.MARKDOWN)

async def voice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ **Пример:** /voice Привет", parse_mode=ParseMode.MARKDOWN)
        return
    
    text = ' '.join(context.args)
    await update.message.reply_text("🔊 **Генерирую...**", parse_mode=ParseMode.MARKDOWN)
    
    try:
        tts = gTTS(text=text, lang='ru', slow=False)
        audio_bytes = io.BytesIO()
        tts.write_to_fp(audio_bytes)
        audio_bytes.seek(0)
        await update.message.reply_voice(voice=InputFile(audio_bytes, filename="voice.ogg"))
    except Exception as e:
        await update.message.reply_text(f"❌ **Ошибка:** {str(e)[:100]}", parse_mode=ParseMode.MARKDOWN)

async def mat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global MAT_ENABLED
    
    if not context.args:
        status = "🔞 **включён**" if MAT_ENABLED else "🔰 **выключен**"
        await update.message.reply_text(
            f"⚙️ **Управление матом**\n\n"
            f"Текущий статус: {status}\n\n"
            f"🔞 `/mat on` — включить\n"
            f"🔰 `/mat off` — выключить",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    if context.args[0].lower() == "on":
        MAT_ENABLED = True
        await update.message.reply_text("🔞 **Мат включён!** Тролль может выражаться.", parse_mode=ParseMode.MARKDOWN)
    elif context.args[0].lower() == "off":
        MAT_ENABLED = False
        await update.message.reply_text("🔰 **Мат выключен.** Тролль будет приличным.", parse_mode=ParseMode.MARKDOWN)

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ **Пример:** /search новости про AI", parse_mode=ParseMode.MARKDOWN)
        return
    
    query = ' '.join(context.args)
    user = update.effective_user
    user_id = user.id
    is_owner = (user_id == OWNER_ID)
    tokens, style_key, _, display_name = get_user(user_id, user.username, user.first_name)
    
    if not is_owner and tokens != "∞" and tokens < 1:
        await update.message.reply_text("❌ **Нет токенов!** /start", parse_mode=ParseMode.MARKDOWN)
        return
    
    await update.message.reply_text(f"🔍 **Ищу:** {query}...", parse_mode=ParseMode.MARKDOWN)
    
    result = await search_web(query)
    
    if result:
        if not is_owner and tokens != "∞":
            update_user(user_id, tokens=-1)
        await update.message.reply_text(result, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
    else:
        await update.message.reply_text("😵 **Ничего не нашёл. Попробуй изменить запрос.**", parse_mode=ParseMode.MARKDOWN)

# ===== ОБРАБОТЧИК НАЖАТИЙ НА КНОПКИ =====
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    user_id = user.id
    is_owner = (user_id == OWNER_ID)
    
    if query.data == "menu":
        tokens, style, _, display_name = get_user(user_id, user.username, user.first_name)
        text = f"🏠 **Главное меню**\n💰 **Токены:** {tokens}\n🎭 **Стиль:** {STYLES[style]['name']}"
        await query.edit_message_text(text, reply_markup=get_main_keyboard(), parse_mode=ParseMode.MARKDOWN)
    
    elif query.data == "balance":
        tokens, _, _, _ = get_user(user_id)
        await query.edit_message_text(f"💰 **Баланс:** {tokens} токенов", reply_markup=get_main_keyboard(), parse_mode=ParseMode.MARKDOWN)
    
    elif query.data == "referrals":
        referrals = get_referrals_count(user_id)
        ref_link = f"https://t.me/{BOT_USERNAME[1:]}?start=ref_{user_id}"
        text = (
            f"👥 **РЕФЕРАЛЫ**\n\n"
            f"🔗 **Твоя ссылка:**\n`{ref_link}`\n\n"
            f"👥 **Приглашено:** {referrals}\n"
            f"🎁 **Бонус за друга:** +20 токенов"
        )
        await query.edit_message_text(text, reply_markup=get_main_keyboard(), parse_mode=ParseMode.MARKDOWN)
    
    elif query.data == "style_menu":
        await query.edit_message_text("🎭 **Выбери стиль:**", reply_markup=get_style_keyboard(), parse_mode=ParseMode.MARKDOWN)
    
    elif query.data == "profile":
        tokens, style_key, msgs, display_name = get_user(user_id, user.username, user.first_name)
        referrals = get_referrals_count(user_id)
        join_date = get_user_join_date(user_id)
        
        profile_text = (
            f"╔══════════════════════════════╗\n"
            f"║         👤 ПРОФИЛЬ           ║\n"
            f"╠══════════════════════════════╣\n"
            f"║ 📌 ID: {user_id}\n"
            f"║ 👤 Имя: {user.first_name}\n"
            f"║ 🆔 Юзер: @{user.username or 'нет'}\n"
            f"║ ✏️ **Отображаемое имя:** {display_name}\n"
            f"╠══════════════════════════════╣\n"
            f"║ 🎭 Стиль: {STYLES[style_key]['name']}\n"
            f"╠══════════════════════════════╣\n"
            f"║ 💰 Токены: {tokens}\n"
            f"║ 💬 Сообщений: {msgs}\n"
            f"║ 👥 Рефералов: {referrals}\n"
            f"║ 📅 В боте с: {join_date}\n"
            f"╚══════════════════════════════╝"
        )
        await query.edit_message_text(profile_text, reply_markup=get_main_keyboard())
    
    elif query.data == "change_name":
        await query.edit_message_text(
            "✏️ **СМЕНА ИМЕНИ**\n\n"
            "Чтобы сменить отображаемое имя, отправь сообщение в формате:\n"
            "`/name Новое имя`\n\n"
            "Пример: `/name Король`",
            reply_markup=get_main_keyboard(),
            parse_mode=ParseMode.MARKDOWN
        )
    
    elif query.data == "search":
        await query.edit_message_text(
            "🔍 **ПОИСК В ИНТЕРНЕТЕ**\n\n"
            "Используй команду:\n"
            "`/search [запрос]`\n\n"
            "Пример: `/search новости про AI`",
            reply_markup=get_main_keyboard(),
            parse_mode=ParseMode.MARKDOWN
        )
    
    elif query.data.startswith("style_"):
        style_key = query.data.replace("style_", "")
        if style_key in STYLES:
            update_user(user_id, style=style_key)
            await query.edit_message_text(
                f"✅ **Стиль изменён на {STYLES[style_key]['name']}**",
                reply_markup=get_main_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )

async def name_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для смены отображаемого имени"""
    if not context.args:
        await update.message.reply_text("❌ **Пример:** /name Новое имя", parse_mode=ParseMode.MARKDOWN)
        return
    
    new_name = ' '.join(context.args)
    user_id = update.effective_user.id
    
    if len(new_name) > 30:
        await update.message.reply_text("❌ **Имя слишком длинное! Максимум 30 символов.**", parse_mode=ParseMode.MARKDOWN)
        return
    
    update_user(user_id, display_name=new_name)
    await update.message.reply_text(f"✅ **Имя изменено на: {new_name}**", reply_markup=get_main_keyboard(), parse_mode=ParseMode.MARKDOWN)

# ===== ОБРАБОТЧИК СООБЩЕНИЙ =====
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    is_owner = (user_id == OWNER_ID)
    
    if not update.message.text:
        await update.message.reply_text("❌ **Пока только текст**", parse_mode=ParseMode.MARKDOWN)
        return
    
    text = update.message.text
    
    # Обработка команд
    if text.startswith('/name'):
        await name_command(update, context)
        return
    
    if text.startswith('/search'):
        await search_command(update, context)
        return
    
    tokens, style_key, _, display_name = get_user(user_id, user.username, user.first_name)
    
    if not is_owner and tokens != "∞" and tokens < 1:
        await update.message.reply_text("❌ **Нет токенов!** /start", parse_mode=ParseMode.MARKDOWN)
        return
    
    await update.message.chat.send_action(action="typing")
    answer = await ask_openrouter(text, style_key)
    
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
    app.add_handler(CommandHandler("search", search_command))
    app.add_handler(CommandHandler("name", name_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🚀 MonGPT ULTIMATE запущен!")
    print(f"🔞 Мат: {'включён' if MAT_ENABLED else 'выключен'}")
    print(f"🔍 Поиск: DuckDuckGo")
    print(f"✏️ Смена ника: доступна")
    
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TELEGRAM_TOKEN,
        webhook_url=f"https://mongpt-bot.onrender.com/{TELEGRAM_TOKEN}"
    )

if __name__ == "__main__":
    main()
