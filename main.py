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
from telegram.constants import ParseMode

# ===== ТВОИ ДАННЫЕ =====
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
PORT = int(os.environ.get('PORT', 10000))
BOT_USERNAME = "@MonGPT_bot"
# ========================

# ===== ОСОБЫЙ СТАТУС (ТОЛЬКО БЕСКОНЕЧНЫЕ ТОКЕНЫ) =====
OWNER_ID = 7745009183
# =====================================================

# ===== БАЗА ДАННЫХ =====
def init_db():
    conn = sqlite3.connect('mongpt.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY, tokens INTEGER DEFAULT 100,
                  username TEXT, first_name TEXT, display_name TEXT,
                  referred_by INTEGER,
                  wins INTEGER DEFAULT 0,
                  losses INTEGER DEFAULT 0,
                  darts_wins INTEGER DEFAULT 0,
                  bowling_wins INTEGER DEFAULT 0,
                  soccer_wins INTEGER DEFAULT 0,
                  basketball_wins INTEGER DEFAULT 0,
                  joined_date TIMESTAMP)''')
    conn.commit()
    conn.close()

def get_user(user_id, username=None, first_name=None, referrer=None):
    if user_id == OWNER_ID:
        return "∞", "∞", 0, 0, 0, 0, 0, 0
    
    conn = sqlite3.connect('mongpt.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id=?", (user_id,))
    user = c.fetchone()
    
    if not user:
        display_name = first_name or username or f"User{user_id}"
        if referrer and referrer != user_id:
            c.execute("UPDATE users SET tokens = tokens + 20 WHERE id=?", (referrer,))
        
        c.execute("""INSERT INTO users 
                     (id, username, first_name, display_name, tokens, referred_by, joined_date) 
                     VALUES (?,?,?,?,?,?,?)""",
                  (user_id, username, first_name, display_name, 100, referrer, datetime.now()))
        conn.commit()
        conn.close()
        return 100, display_name, 0, 0, 0, 0, 0, 0
    
    display_name = user[4] if len(user) > 4 and user[4] else first_name or username or f"User{user_id}"
    tokens = user[1]
    wins = user[6] if len(user) > 6 else 0
    losses = user[7] if len(user) > 7 else 0
    darts = user[8] if len(user) > 8 else 0
    bowling = user[9] if len(user) > 9 else 0
    soccer = user[10] if len(user) > 10 else 0
    basketball = user[11] if len(user) > 11 else 0
    
    conn.close()
    return tokens, display_name, wins, losses, darts, bowling, soccer, basketball

def update_user(user_id, tokens=None, display_name=None, wins=None, losses=None, 
                darts=None, bowling=None, soccer=None, basketball=None):
    conn = sqlite3.connect('mongpt.db')
    c = conn.cursor()
    
    if tokens:
        c.execute("UPDATE users SET tokens = tokens + ? WHERE id=?", (tokens, user_id))
    if display_name:
        c.execute("UPDATE users SET display_name = ? WHERE id=?", (display_name, user_id))
    if wins is not None:
        c.execute("UPDATE users SET wins = wins + ? WHERE id=?", (wins, user_id))
    if losses is not None:
        c.execute("UPDATE users SET losses = losses + ? WHERE id=?", (losses, user_id))
    if darts is not None:
        c.execute("UPDATE users SET darts_wins = darts_wins + ? WHERE id=?", (darts, user_id))
    if bowling is not None:
        c.execute("UPDATE users SET bowling_wins = bowling_wins + ? WHERE id=?", (bowling, user_id))
    if soccer is not None:
        c.execute("UPDATE users SET soccer_wins = soccer_wins + ? WHERE id=?", (soccer, user_id))
    if basketball is not None:
        c.execute("UPDATE users SET basketball_wins = basketball_wins + ? WHERE id=?", (basketball, user_id))
    
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

# ===== ФУНКЦИИ ДЛЯ ИГР =====
def get_emoji(game_type):
    emojis = {
        'dice': '🎲',
        'darts': '🎯',
        'bowling': '🎳',
        'soccer': '⚽',
        'basketball': '🏀'
    }
    return emojis.get(game_type, '🎲')

def get_game_name(game_type):
    names = {
        'dice': 'Кости',
        'darts': 'Дартс',
        'bowling': 'Боулинг',
        'soccer': 'Футбол',
        'basketball': 'Баскетбол'
    }
    return names.get(game_type, 'Игра')

def get_game_win_condition(game_type, results):
    """Определяет, выиграл ли игрок в зависимости от игры"""
    total = sum(results)
    
    if game_type == 'dice':
        return total > 10 * len(results) / 2
    elif game_type == 'darts':
        return total > 15 * len(results) / 2
    elif game_type == 'bowling':
        return total > 15 * len(results) / 2
    elif game_type in ['soccer', 'basketball']:
        return any(r > 3 for r in results)
    return False

# ===== КОМАНДЫ ДЛЯ ИГР =====
async def play_game(update: Update, context: ContextTypes.DEFAULT_TYPE, game_type, bet, rounds=1):
    """Общая функция для запуска игры"""
    user = update.effective_user
    user_id = user.id
    
    # Проверка баланса
    tokens, display_name, wins, losses, darts, bowling, soccer, basketball = get_user(user_id)
    if tokens != "∞" and tokens < bet:
        await update.message.reply_text(f"❌ Недостаточно монет! Есть {tokens}")
        return False
    
    # Отправляем кости
    msg = await update.message.reply_text(f"🎮 **{get_game_name(game_type)}**\n🎲 Бросаем...")
    
    results = []
    for i in range(rounds):
        dice = await context.bot.send_dice(chat_id=update.message.chat_id, emoji=get_emoji(game_type))
        results.append(dice.dice.value)
        await asyncio.sleep(1)  # Пауза между бросками
    
    total = sum(results)
    win = get_game_win_condition(game_type, results)
    
    # Обновляем статистику
    win_amount = 0
    if win:
        win_amount = bet * 2
        update_user(user_id, tokens=win_amount - bet, wins=1)
        
        # Обновляем победы по конкретной игре
        if game_type == 'darts':
            update_user(user_id, darts=1)
        elif game_type == 'bowling':
            update_user(user_id, bowling=1)
        elif game_type == 'soccer':
            update_user(user_id, soccer=1)
        elif game_type == 'basketball':
            update_user(user_id, basketball=1)
    else:
        update_user(user_id, tokens=-bet, losses=1)
    
    # Формируем результат
    if rounds == 1:
        result_line = f"🎲 Результат: {results[0]}"
    else:
        result_line = f"🎲 Броски: {' + '.join(map(str, results))} = {total}"
    
    result_text = f"🎉 **ТЫ ВЫИГРАЛ!** +{win_amount - bet} монет" if win else f"💔 **ТЫ ПРОИГРАЛ!** -{bet} монет"
    
    text = (f"🎮 **{get_game_name(game_type)}**\n"
            f"💰 Ставка: {bet}\n"
            f"{result_line}\n"
            f"{result_text}")
    
    await msg.delete()
    await update.message.reply_text(text)
    return True

async def dice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Игра в кости"""
    if not context.args:
        await update.message.reply_text("❌ Использование: /dice [ставка] [раунды]\nПример: /dice 50 3")
        return
    
    try:
        bet = int(context.args[0])
        rounds = 1
        if len(context.args) > 1:
            rounds = int(context.args[1])
            if rounds not in [1, 3]:
                await update.message.reply_text("❌ Раундов может быть 1 или 3!")
                return
    except:
        await update.message.reply_text("❌ Неверные параметры!")
        return
    
    await play_game(update, context, 'dice', bet, rounds)

async def darts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Игра в дартс"""
    if not context.args:
        await update.message.reply_text("❌ Использование: /darts [ставка] [раунды]\nПример: /darts 50 3")
        return
    
    try:
        bet = int(context.args[0])
        rounds = 1
        if len(context.args) > 1:
            rounds = int(context.args[1])
            if rounds not in [1, 3]:
                await update.message.reply_text("❌ Раундов может быть 1 или 3!")
                return
    except:
        await update.message.reply_text("❌ Неверные параметры!")
        return
    
    await play_game(update, context, 'darts', bet, rounds)

async def bowling_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Игра в боулинг"""
    if not context.args:
        await update.message.reply_text("❌ Использование: /bowling [ставка] [раунды]\nПример: /bowling 50 3")
        return
    
    try:
        bet = int(context.args[0])
        rounds = 1
        if len(context.args) > 1:
            rounds = int(context.args[1])
            if rounds not in [1, 3]:
                await update.message.reply_text("❌ Раундов может быть 1 или 3!")
                return
    except:
        await update.message.reply_text("❌ Неверные параметры!")
        return
    
    await play_game(update, context, 'bowling', bet, rounds)

async def soccer_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Игра в футбол"""
    if not context.args:
        await update.message.reply_text("❌ Использование: /soccer [ставка]\nПример: /soccer 50")
        return
    
    try:
        bet = int(context.args[0])
    except:
        await update.message.reply_text("❌ Неверная ставка!")
        return
    
    await play_game(update, context, 'soccer', bet, 1)

async def basketball_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Игра в баскетбол"""
    if not context.args:
        await update.message.reply_text("❌ Использование: /basketball [ставка]\nПример: /basketball 50")
        return
    
    try:
        bet = int(context.args[0])
    except:
        await update.message.reply_text("❌ Неверная ставка!")
        return
    
    await play_game(update, context, 'basketball', bet, 1)

# ===== КНОПКИ =====
def get_main_keyboard():
    keyboard = [
        [InlineKeyboardButton("🏠 Меню", callback_data="menu"),
         InlineKeyboardButton("💰 Баланс", callback_data="balance")],
        [InlineKeyboardButton("👥 Рефералы", callback_data="referrals"),
         InlineKeyboardButton("🎮 Игры", callback_data="games_menu")],
        [InlineKeyboardButton("👤 Профиль", callback_data="profile"),
         InlineKeyboardButton("🏆 Топ", callback_data="top")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_games_keyboard():
    keyboard = [
        [InlineKeyboardButton("🎲 Кости", callback_data="game_dice"),
         InlineKeyboardButton("🎯 Дартс", callback_data="game_darts")],
        [InlineKeyboardButton("🎳 Боулинг", callback_data="game_bowling"),
         InlineKeyboardButton("⚽ Футбол", callback_data="game_soccer")],
        [InlineKeyboardButton("🏀 Баскетбол", callback_data="game_basketball"),
         InlineKeyboardButton("◀️ Назад", callback_data="menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ===== ТОП =====
async def top_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает топ бедварсеров по монетам"""
    
    conn = sqlite3.connect('mongpt.db')
    c = conn.cursor()
    
    c.execute("SELECT username, display_name, tokens FROM users ORDER BY tokens DESC LIMIT 10")
    top_users = c.fetchall()
    
    conn.close()
    
    if not top_users:
        await update.message.reply_text("📊 Пока нет данных для топа")
        return
    
    text = "🏆 **ТОП БЕДВАРСЕРОВ ПО МОНЕТАМ** 🏆\n\n"
    
    for i, (username, display_name, tokens) in enumerate(top_users, 1):
        name = display_name or username or f"Игрок {i}"
        if username:
            name = f"@{username}"
        
        if i == 1:
            medal = "👑"
        elif i == 2:
            medal = "🥈"
        elif i == 3:
            medal = "🥉"
        else:
            medal = "🎮"
        
        text += f"{i}. {medal} {name} — {tokens} 🪙\n"
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

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
    
    tokens, display_name, wins, losses, darts, bowling, soccer, basketball = get_user(user.id, user.username, user.first_name, referrer)
    
    text = (f"👋 **Йоу, {display_name}!**\n"
            f"💰 **Монеты:** {tokens}\n"
            f"🏆 **Побед:** {wins} | Поражений: {losses}\n\n"
            f"🎮 **Доступные игры:**\n"
            f"/dice [ставка] [1/3] — 🎲 Кости\n"
            f"/darts [ставка] [1/3] — 🎯 Дартс\n"
            f"/bowling [ставка] [1/3] — 🎳 Боулинг\n"
            f"/soccer [ставка] — ⚽ Футбол\n"
            f"/basketball [ставка] — 🏀 Баскетбол\n\n"
            f"📊 **Другие команды:**\n"
            f"/balance — баланс\n"
            f"/profile — профиль\n"
            f"/top — топ игроков\n"
            f"/referrals — рефералы\n"
            f"/name — сменить имя\n\n"
            f"👇 **Или используй кнопки:**")
    
    await update.message.reply_text(text, reply_markup=get_main_keyboard(), parse_mode=ParseMode.MARKDOWN)

async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    tokens, _, _, _, _, _, _, _ = get_user(user_id)
    await update.message.reply_text(f"💰 **Твой баланс:** {tokens} монет")

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    tokens, display_name, wins, losses, darts, bowling, soccer, basketball = get_user(user_id, user.username, user.first_name)
    referrals = get_referrals_count(user_id)
    join_date = get_user_join_date(user_id)
    
    total_games = wins + losses
    winrate = (wins / total_games * 100) if total_games > 0 else 0
    
    text = (f"👤 **ПРОФИЛЬ**\n"
            f"📌 **ID:** `{user_id}`\n"
            f"👤 **Имя:** {display_name}\n"
            f"💰 **Монеты:** {tokens}\n"
            f"🏆 **Всего побед:** {wins}\n"
            f"💔 **Поражений:** {losses}\n"
            f"📊 **Винрейт:** {winrate:.1f}%\n\n"
            f"🎯 **Победы по играм:**\n"
            f"🎲 Кости: {wins}\n"
            f"🎯 Дартс: {darts}\n"
            f"🎳 Боулинг: {bowling}\n"
            f"⚽ Футбол: {soccer}\n"
            f"🏀 Баскетбол: {basketball}\n\n"
            f"👥 **Рефералов:** {referrals}\n"
            f"📅 **В боте с:** {join_date}")
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def referrals_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    referrals = get_referrals_count(user_id)
    ref_link = f"https://t.me/{BOT_USERNAME[1:]}?start=ref_{user_id}"
    
    text = (f"👥 **РЕФЕРАЛЫ**\n\n"
            f"🔗 **Твоя ссылка:**\n`{ref_link}`\n\n"
            f"👥 **Приглашено:** {referrals}\n"
            f"🎁 **Бонус за друга:** +20 монет")
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def name_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ **Пример:** /name Новое имя")
        return
    
    new_name = ' '.join(context.args)
    user_id = update.effective_user.id
    
    if len(new_name) > 30:
        await update.message.reply_text("❌ **Слишком длинное имя!**")
        return
    
    update_user(user_id, display_name=new_name)
    await update.message.reply_text(f"✅ **Имя изменено на:** {new_name}")

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
        await update.message.reply_text(text)
        return
    
    command = context.args[0]
    
    if command == "stats":
        conn = sqlite3.connect('mongpt.db')
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM users")
        total_users = c.fetchone()[0]
        
        c.execute("SELECT SUM(tokens) FROM users")
        total_tokens = c.fetchone()[0] or 0
        
        c.execute("SELECT username, tokens FROM users ORDER BY tokens DESC LIMIT 5")
        top_users = c.fetchall()
        
        conn.close()
        
        text = (f"📊 **СТАТИСТИКА БОТА**\n\n"
                f"👥 Всего пользователей: {total_users}\n"
                f"💰 Всего монет: {total_tokens}\n\n"
                f"🏆 **Топ-5 богачей:**\n")
        
        for i, (username, tokens) in enumerate(top_users, 1):
            text += f"{i}. @{username or 'Аноним'} — {tokens} 🪙\n"
        
        await update.message.reply_text(text)
    
    elif command == "give" and len(context.args) >= 3:
        target = context.args[1]
        amount = int(context.args[2])
        
        conn = sqlite3.connect('mongpt.db')
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE username=?", (target.replace('@', ''),))
        result = c.fetchone()
        conn.close()
        
        if result:
            update_user(result[0], tokens=amount)
            await update.message.reply_text(f"✅ Начислено {amount} монет пользователю {target}")
        else:
            await update.message.reply_text("❌ Пользователь не найден")

# ===== ОБРАБОТЧИК КНОПОК =====
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if query.data == "menu":
        tokens, display_name, wins, losses, _, _, _, _ = get_user(user_id)
        text = (f"🏠 **Главное меню**\n"
                f"💰 **Монеты:** {tokens}\n"
                f"🏆 **Побед:** {wins} | Поражений: {losses}")
        await query.edit_message_text(text, reply_markup=get_main_keyboard(), parse_mode=ParseMode.MARKDOWN)
        return
    
    elif query.data == "balance":
        tokens, _, _, _, _, _, _, _ = get_user(user_id)
        await query.edit_message_text(f"💰 **Баланс:** {tokens} монет", reply_markup=get_main_keyboard(), parse_mode=ParseMode.MARKDOWN)
        return
    
    elif query.data == "referrals":
        referrals = get_referrals_count(user_id)
        ref_link = f"https://t.me/{BOT_USERNAME[1:]}?start=ref_{user_id}"
        text = (f"👥 **Рефералы**\n\n"
                f"🔗 **Твоя ссылка:**\n`{ref_link}`\n\n"
                f"👥 **Приглашено:** {referrals}\n"
                f"🎁 **Бонус за друга:** +20 монет")
        await query.edit_message_text(text, reply_markup=get_main_keyboard(), parse_mode=ParseMode.MARKDOWN)
        return
    
    elif query.data == "games_menu":
        await query.edit_message_text("🎮 **Выбери игру:**", reply_markup=get_games_keyboard(), parse_mode=ParseMode.MARKDOWN)
        return
    
    elif query.data == "profile":
        tokens, display_name, wins, losses, darts, bowling, soccer, basketball = get_user(user_id)
        referrals = get_referrals_count(user_id)
        join_date = get_user_join_date(user_id)
        
        total_games = wins + losses
        winrate = (wins / total_games * 100) if total_games > 0 else 0
        
        text = (f"👤 **ПРОФИЛЬ**\n"
                f"📌 **ID:** `{user_id}`\n"
                f"👤 **Имя:** {display_name}\n"
                f"💰 **Монеты:** {tokens}\n"
                f"🏆 **Всего побед:** {wins}\n"
                f"💔 **Поражений:** {losses}\n"
                f"📊 **Винрейт:** {winrate:.1f}%\n\n"
                f"🎯 **Победы по играм:**\n"
                f"🎲 Кости: {wins}\n"
                f"🎯 Дартс: {darts}\n"
                f"🎳 Боулинг: {bowling}\n"
                f"⚽ Футбол: {soccer}\n"
                f"🏀 Баскетбол: {basketball}\n\n"
                f"👥 **Рефералов:** {referrals}\n"
                f"📅 **В боте с:** {join_date}")
        await query.edit_message_text(text, reply_markup=get_main_keyboard(), parse_mode=ParseMode.MARKDOWN)
        return
    
    elif query.data == "top":
        await top_command(update, context)
        return
    
    elif query.data == "game_dice":
        await query.edit_message_text("🎲 **Кости**\n\nИспользуй команду:\n`/dice [ставка] [1/3]`\nПример: `/dice 50 3`", parse_mode=ParseMode.MARKDOWN)
        return
    
    elif query.data == "game_darts":
        await query.edit_message_text("🎯 **Дартс**\n\nИспользуй команду:\n`/darts [ставка] [1/3]`\nПример: `/darts 50 3`", parse_mode=ParseMode.MARKDOWN)
        return
    
    elif query.data == "game_bowling":
        await query.edit_message_text("🎳 **Боулинг**\n\nИспользуй команду:\n`/bowling [ставка] [1/3]`\nПример: `/bowling 50 3`", parse_mode=ParseMode.MARKDOWN)
        return
    
    elif query.data == "game_soccer":
        await query.edit_message_text("⚽ **Футбол**\n\nИспользуй команду:\n`/soccer [ставка]`\nПример: `/soccer 50`", parse_mode=ParseMode.MARKDOWN)
        return
    
    elif query.data == "game_basketball":
        await query.edit_message_text("🏀 **Баскетбол**\n\nИспользуй команду:\n`/basketball [ставка]`\nПример: `/basketball 50`", parse_mode=ParseMode.MARKDOWN)
        return

# ===== ОСНОВНОЙ ОБРАБОТЧИК =====
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    if text.startswith('/start'):
        await start(update, context)
    elif text.startswith('/balance'):
        await balance_command(update, context)
    elif text.startswith('/profile'):
        await profile_command(update, context)
    elif text.startswith('/referrals'):
        await referrals_command(update, context)
    elif text.startswith('/name'):
        await name_command(update, context)
    elif text.startswith('/top'):
        await top_command(update, context)
    elif text.startswith('/dice'):
        await dice_command(update, context)
    elif text.startswith('/darts'):
        await darts_command(update, context)
    elif text.startswith('/bowling'):
        await bowling_command(update, context)
    elif text.startswith('/soccer'):
        await soccer_command(update, context)
    elif text.startswith('/basketball'):
        await basketball_command(update, context)
    elif text.startswith('/admin'):
        await admin_command(update, context)
    else:
        await update.message.reply_text("❓ Используй /start для меню")

# ===== ЗАПУСК =====
def main():
    init_db()
    
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("balance", balance_command))
    app.add_handler(CommandHandler("profile", profile_command))
    app.add_handler(CommandHandler("referrals", referrals_command))
    app.add_handler(CommandHandler("name", name_command))
    app.add_handler(CommandHandler("top", top_command))
    app.add_handler(CommandHandler("dice", dice_command))
    app.add_handler(CommandHandler("darts", darts_command))
    app.add_handler(CommandHandler("bowling", bowling_command))
    app.add_handler(CommandHandler("soccer", soccer_command))
    app.add_handler(CommandHandler("basketball", basketball_command))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🚀 MonGPT ULTIMATE запущен!")
    print(f"👑 Админ: @God_Mon1tyy")
    
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TELEGRAM_TOKEN,
        webhook_url=f"https://mongpt-bot.onrender.com/{TELEGRAM_TOKEN}"
    )

if __name__ == "__main__":
    main()
