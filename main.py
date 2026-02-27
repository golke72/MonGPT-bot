import sqlite3
import os
import random
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.constants import ParseMode

# ===== ТВОИ ДАННЫЕ =====
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
PORT = int(os.environ.get('PORT', 10000))
BOT_USERNAME = "@BedPVP_bot"
# ========================

# ===== ТВОЙ ID =====
OWNER_ID = 7745009183
# ===================

# ===== ИГРОВЫЕ ДАННЫЕ =====
active_duels = {}
active_bj = {}
active_tower = {}
active_mines = {}
active_slots = {}

# ===== БАЗА ДАННЫХ =====
def init_db():
    conn = sqlite3.connect('bedpvp.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY, 
                  username TEXT,
                  first_name TEXT,
                  coins INTEGER DEFAULT 1000,
                  wins INTEGER DEFAULT 0,
                  losses INTEGER DEFAULT 0,
                  tower_wins INTEGER DEFAULT 0,
                  mines_wins INTEGER DEFAULT 0,
                  duel_wins INTEGER DEFAULT 0,
                  bj_wins INTEGER DEFAULT 0,
                  slot_wins INTEGER DEFAULT 0,
                  joined_date TIMESTAMP)''')
    conn.commit()
    conn.close()

def get_user(user_id, username=None, first_name=None):
    if user_id == OWNER_ID:
        return 999999, 999, 0, 999, 999, 999, 999, 999, "👑 СОЗДАТЕЛЬ"
    
    conn = sqlite3.connect('bedpvp.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id=?", (user_id,))
    user = c.fetchone()
    
    if not user:
        c.execute("INSERT INTO users (id, username, first_name, joined_date) VALUES (?,?,?,?)",
                  (user_id, username, first_name, datetime.now()))
        conn.commit()
        coins = 1000
        wins = 0
        losses = 0
        tower = 0
        mines = 0
        duel = 0
        bj = 0
        slot = 0
    else:
        coins = user[3]
        wins = user[4]
        losses = user[5]
        tower = user[6] if len(user) > 6 else 0
        mines = user[7] if len(user) > 7 else 0
        duel = user[8] if len(user) > 8 else 0
        bj = user[9] if len(user) > 9 else 0
        slot = user[10] if len(user) > 10 else 0
    
    conn.close()
    return coins, wins, losses, tower, mines, duel, bj, slot, user[2] or "Игрок"

def update_user(user_id, coins=None, win=None, loss=None, tower=None, mines=None, duel=None, bj=None, slot=None):
    conn = sqlite3.connect('bedpvp.db')
    c = conn.cursor()
    if coins is not None:
        c.execute("UPDATE users SET coins = coins + ? WHERE id=?", (coins, user_id))
    if win:
        c.execute("UPDATE users SET wins = wins + 1 WHERE id=?", (user_id,))
    if loss:
        c.execute("UPDATE users SET losses = losses + 1 WHERE id=?", (user_id,))
    if tower:
        c.execute("UPDATE users SET tower_wins = tower_wins + 1 WHERE id=?", (user_id,))
    if mines:
        c.execute("UPDATE users SET mines_wins = mines_wins + 1 WHERE id=?", (user_id,))
    if duel:
        c.execute("UPDATE users SET duel_wins = duel_wins + 1 WHERE id=?", (user_id,))
    if bj:
        c.execute("UPDATE users SET bj_wins = bj_wins + 1 WHERE id=?", (user_id,))
    if slot:
        c.execute("UPDATE users SET slot_wins = slot_wins + 1 WHERE id=?", (user_id,))
    conn.commit()
    conn.close()

# ===== ДУЭЛИ =====
async def duel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вызов на дуэль"""
    user = update.effective_user
    
    if not context.args:
        await update.message.reply_text(
            "❌ **Ошибка**\n\nИспользование: `/duel @user [ставка]`\nПример: `/duel @durov 50`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    target = context.args[0]
    bet = 10
    
    if len(context.args) > 1:
        try:
            bet = int(context.args[1])
            if bet <= 0:
                raise ValueError
        except:
            await update.message.reply_text("❌ **Неверная ставка!**")
            return
    
    # Проверка баланса
    coins, _, _, _, _, _, _, _, _ = get_user(user.id)
    if coins < bet:
        await update.message.reply_text(f"❌ **Недостаточно монет!** У тебя {coins}")
        return
    
    # Поиск оппонента
    target_id = None
    conn = sqlite3.connect('bedpvp.db')
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE username=?", (target.replace('@', ''),))
    result = c.fetchone()
    conn.close()
    
    if not result:
        await update.message.reply_text("❌ **Пользователь не найден!**")
        return
    
    target_id = result[0]
    
    # Создаём дуэль
    duel_id = f"duel_{user.id}_{target_id}_{datetime.now().timestamp()}"
    
    keyboard = [
        [InlineKeyboardButton("✅ Принять", callback_data=f"accept_{duel_id}"),
         InlineKeyboardButton("❌ Отклонить", callback_data=f"decline_{duel_id}")]
    ]
    
    await update.message.reply_text(
        f"⚔️ **ВЫЗОВ НА ДУЭЛЬ** ⚔️\n\n"
        f"👤 **От:** @{user.username or 'Игрок'}\n"
        f"👤 **Кому:** {target}\n"
        f"💰 **Ставка:** {bet} монет\n\n"
        f"⏳ У тебя 2 минуты, чтобы принять!",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    # Уведомляем оппонента
    try:
        await context.bot.send_message(
            target_id,
            f"⚔️ **ТЕБЯ ВЫЗЫВАЮТ НА ДУЭЛЬ!** ⚔️\n\n"
            f"👤 **Противник:** @{user.username or 'Игрок'}\n"
            f"💰 **Ставка:** {bet} монет\n\n"
            f"Напиши `/accept` чтобы принять!"
        )
    except:
        pass

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главное меню с гифкой"""
    user = update.effective_user
    coins, wins, losses, tower, mines, duel, bj, slot, name = get_user(user.id, user.username, user.first_name)
    
    text = (
        f"**[⚔️] BEDPVP TURBO [⚔️]**\n\n"
        f"**[👤] Игрок:** {name}\n"
        f"**[💰] Монет:** {coins}\n"
        f"**[🏆] Побед:** {wins} | **[💔] Поражений:** {losses}\n\n"
        f"**[🎮] ДОСТУПНЫЕ ИГРЫ:**\n\n"
        f"**[⚔️] PVP-ДУЭЛИ**\n"
        f"  `/duel @user 50` — вызвать на дуэль\n\n"
        f"**[🎲] КОСТИ**\n"
        f"  `/dice 50` — 1 бросок\n"
        f"  `/dice 50 3` — 3 броска\n\n"
        f"**[🎯] ДАРТС**\n"
        f"  `/darts 50` — 1 бросок\n"
        f"  `/darts 50 3` — 3 броска\n\n"
        f"**[🎳] БОУЛИНГ**\n"
        f"  `/bowling 50` — 1 бросок\n"
        f"  `/bowling 50 3` — 3 броска\n\n"
        f"**[⚽] ФУТБОЛ**\n"
        f"  `/soccer 50` — удар по воротам\n\n"
        f"**[🏀] БАСКЕТБОЛ**\n"
        f"  `/basketball 50` — бросок мяча\n\n"
        f"**[🃏] БЛЭКДЖЕК**\n"
        f"  `/bj @user 50` — BlackJack 1v1\n\n"
        f"**[🏰] БАШНЯ**\n"
        f"  `/tower 50` — покори башню (множители x2-x20)\n\n"
        f"**[💣] МИНЫ**\n"
        f"  `/mines 50` — поле 5x5, собери алмазы\n\n"
        f"**[🎰] СЛОТЫ**\n"
        f"  `/slot 50` — крути барабаны (джекпот x10)\n\n"
        f"**[📊] СТАТИСТИКА**\n"
        f"  `/stats @user` — статистика игрока\n"
        f"  `/top` — топ богачей\n"
        f"  `/top tower` — топ башенных бойцов\n"
        f"  `/top mines` — топ минёров\n"
        f"  `/top duels` — топ дуэлянтов\n\n"
        f"**[💸] ЭКОНОМИКА**\n"
        f"  `/transfer @user 50` — перевести монеты\n"
        f"  `/balance` — баланс\n\n"
        f"**[⚡] СТАТУС:** ONLINE"
    )
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статистика игрока"""
    user = update.effective_user
    target_id = user.id
    
    if context.args:
        target = context.args[0]
        conn = sqlite3.connect('bedpvp.db')
        c = conn.cursor()
        c.execute("SELECT id, first_name FROM users WHERE username=?", (target.replace('@', ''),))
        result = c.fetchone()
        conn.close()
        
        if result:
            target_id = result[0]
            name = result[1]
        else:
            await update.message.reply_text("❌ **Пользователь не найден!**")
            return
    else:
        name = user.first_name
    
    coins, wins, losses, tower, mines, duel, bj, slot, _ = get_user(target_id)
    total = wins + losses
    winrate = (wins / total * 100) if total > 0 else 0
    
    text = (
        f"**[📊] СТАТИСТИКА ИГРОКА**\n\n"
        f"**[👤] Имя:** {name}\n"
        f"**[💰] Монет:** {coins}\n"
        f"**[🏆] Всего побед:** {wins}\n"
        f"**[💔] Поражений:** {losses}\n"
        f"**[📈] Винрейт:** {winrate:.1f}%\n\n"
        f"**[🏆] ПОБЕДЫ ПО ИГРАМ:**\n"
        f"  [🏰] Башня: {tower}\n"
        f"  [💣] Мины: {mines}\n"
        f"  [⚔️] Дуэли: {duel}\n"
        f"  [🃏] Блэкджек: {bj}\n"
        f"  [🎰] Слоты: {slot}"
    )
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Топ игроков"""
    mode = "coins"
    title = "БОГАЧЕЙ"
    
    if context.args:
        if context.args[0] == "tower":
            mode = "tower_wins"
            title = "БАШЕННЫХ БОЙЦОВ"
        elif context.args[0] == "mines":
            mode = "mines_wins"
            title = "МИНЁРОВ"
        elif context.args[0] == "duels":
            mode = "duel_wins"
            title = "ДУЭЛЯНТОВ"
    
    conn = sqlite3.connect('bedpvp.db')
    c = conn.cursor()
    c.execute(f"SELECT username, first_name, {mode} FROM users ORDER BY {mode} DESC LIMIT 10")
    top_users = c.fetchall()
    conn.close()
    
    if not top_users:
        await update.message.reply_text("📊 **Пока нет данных для топа**")
        return
    
    text = f"**[🏆] ТОП {title} [🏆]**\n\n"
    
    medals = ["👑", "🥈", "🥉"]
    for i, (username, first_name, value) in enumerate(top_users, 1):
        name = f"@{username}" if username else first_name or f"Игрок {i}"
        medal = medals[i-1] if i <= 3 else "▫️"
        
        if mode == "coins":
            text += f"{medal} {i}. {name} — {value} 🪙\n"
        else:
            text += f"{medal} {i}. {name} — {value} 🏆\n"
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверка баланса"""
    user = update.effective_user
    coins, _, _, _, _, _, _, _, _ = get_user(user.id)
    await update.message.reply_text(f"💰 **Твой баланс:** {coins} монет")

async def transfer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Перевод монет"""
    user = update.effective_user
    
    if not context.args or len(context.args) < 2:
        await update.message.reply_text("❌ **Использование:** `/transfer @user 50`", parse_mode=ParseMode.MARKDOWN)
        return
    
    target = context.args[0]
    try:
        amount = int(context.args[1])
        if amount <= 0:
            raise ValueError
    except:
        await update.message.reply_text("❌ **Неверная сумма!**")
        return
    
    # Проверка баланса
    coins, _, _, _, _, _, _, _, _ = get_user(user.id)
    if coins < amount:
        await update.message.reply_text(f"❌ **Недостаточно монет!** У тебя {coins}")
        return
    
    # Поиск получателя
    conn = sqlite3.connect('bedpvp.db')
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE username=?", (target.replace('@', ''),))
    result = c.fetchone()
    conn.close()
    
    if not result:
        await update.message.reply_text("❌ **Пользователь не найден!**")
        return
    
    target_id = result[0]
    
    # Перевод
    update_user(user.id, coins=-amount)
    update_user(target_id, coins=amount)
    
    await update.message.reply_text(f"✅ **Переведено {amount} монет** пользователю {target}")

# ===== ИГРЫ =====
async def dice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Игра в кости"""
    await play_game(update, context, '🎲', 'dice', [1,2,3,4,5,6])

async def darts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Игра в дартс"""
    await play_game(update, context, '🎯', 'darts', [1,2,3,4,5,6])

async def bowling(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Игра в боулинг"""
    await play_game(update, context, '🎳', 'bowling', [1,2,3,4,5,6])

async def soccer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Игра в футбол"""
    await play_game(update, context, '⚽', 'soccer', [1,2,3,4,5])

async def basketball(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Игра в баскетбол"""
    await play_game(update, context, '🏀', 'basketball', [1,2,3,4,5])

async def play_game(update, context, emoji, game_type, values):
    """Общая функция для игр"""
    user = update.effective_user
    
    if not context.args:
        await update.message.reply_text(f"❌ **Использование:** `/{game_type} [ставка] [раунды]`")
        return
    
    try:
        bet = int(context.args[0])
        rounds = 1
        if len(context.args) > 1:
            rounds = int(context.args[1])
            if rounds not in [1, 3]:
                await update.message.reply_text("❌ **Раундов может быть 1 или 3!**")
                return
    except:
        await update.message.reply_text("❌ **Неверные параметры!**")
        return
    
    # Проверка баланса
    coins, _, _, _, _, _, _, _, _ = get_user(user.id)
    if coins < bet:
        await update.message.reply_text(f"❌ **Недостаточно монет!** У тебя {coins}")
        return
    
    msg = await update.message.reply_text(f"{emoji} **Бросаем...**")
    
    results = []
    for i in range(rounds):
        dice = await context.bot.send_dice(chat_id=update.message.chat_id, emoji=emoji)
        results.append(dice.dice.value)
        await asyncio.sleep(1)
    
    total = sum(results)
    max_value = max(values) * rounds
    win = total > max_value * 0.6
    
    if win:
        win_amount = bet * 2
        update_user(user.id, coins=win_amount - bet, win=True)
        result_text = f"🎉 **ТЫ ВЫИГРАЛ!** +{win_amount - bet} монет"
    else:
        update_user(user.id, coins=-bet, loss=True)
        result_text = f"💔 **ТЫ ПРОИГРАЛ!** -{bet} монет"
    
    result_line = f"{' + '.join(map(str, results))} = {total}" if rounds > 1 else f"Результат: {results[0]}"
    
    text = (f"{emoji} **{game_type.upper()}**\n\n"
            f"💰 Ставка: {bet}\n"
            f"🎲 {result_line}\n"
            f"{result_text}")
    
    await msg.delete()
    await update.message.reply_text(text)

# ===== БАШНЯ =====
async def tower(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Игра в башню"""
    user = update.effective_user
    user_id = user.id
    
    if not context.args:
        await update.message.reply_text("❌ **Использование:** `/tower [ставка]`")
        return
    
    try:
        bet = int(context.args[0])
        if bet <= 0:
            raise ValueError
    except:
        await update.message.reply_text("❌ **Неверная ставка!**")
        return
    
    # Проверка баланса
    coins, _, _, _, _, _, _, _, _ = get_user(user_id)
    if coins < bet:
        await update.message.reply_text(f"❌ **Недостаточно монет!** У тебя {coins}")
        return
    
    # Создаём игру
    game_id = f"tower_{user_id}_{datetime.now().timestamp()}"
    active_tower[game_id] = {
        'user_id': user_id,
        'bet': bet,
        'floor': 0,
        'multiplier': 1,
        'game_over': False,
        'cells': []
    }
    
    await show_tower_floor(update, context, game_id)

async def show_tower_floor(update, context, game_id):
    """Показывает текущий этаж башни"""
    game = active_tower.get(game_id)
    if not game:
        return
    
    floor = game['floor'] + 1
    
    if floor > 5:
        # Победа - прошёл все этажи
        win = game['bet'] * 20
        update_user(game['user_id'], coins=win - game['bet'], tower_wins=1)
        
        await context.bot.send_message(
            game['user_id'],
            f"🏰 **ТЫ ПОКОРИЛ БАШНЮ!** 🏰\n\n"
            f"💰 Ставка: {game['bet']}\n"
            f"🎉 Выигрыш: {win} (x20)"
        )
        del active_tower[game_id]
        return
    
    # Генерируем клетки для этажа
    cells = ['⬜', '⬜', '⬜']
    win_cell = random.randint(0, 2)
    
    keyboard = []
    row = []
    for i in range(3):
        if game['game_over']:
            row.append(InlineKeyboardButton('❌', callback_data=f"tower_none"))
        else:
            row.append(InlineKeyboardButton(cells[i], callback_data=f"tower_{game_id}_{floor}_{i}"))
        if (i + 1) % 3 == 0:
            keyboard.append(row)
            row = []
    
    if not game['game_over']:
        keyboard.append([InlineKeyboardButton("💰 ЗАБРАТЬ ВЫИГРЫШ", callback_data=f"tower_cash_{game_id}")])
    
    multipliers = ['2x', '3x', '5x', '10x', '20x']
    
    await context.bot.send_message(
        game['user_id'],
        f"🏰 **БАШНЯ** 🏰\n\n"
        f"💰 Ставка: {game['bet']}\n"
        f"📈 Этаж: {floor}/5\n"
        f"🎯 Множитель: {multipliers[floor-1]}\n\n"
        f"Выбери клетку:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def tower_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик башни"""
    query = update.callback_query
    await query.answer()
    
    data = query.data.split('_')
    action = data[1]
    
    if action == "none":
        return
    
    game_id = data[2]
    game = active_tower.get(game_id)
    
    if not game or game['game_over']:
        await query.edit_message_text("❌ **Игра уже закончена!**")
        return
    
    if action == "cash":
        # Забрать выигрыш
        multipliers = [1, 2, 3, 5, 10, 20]
        win = game['bet'] * multipliers[game['floor']]
        update_user(game['user_id'], coins=win - game['bet'], win=True)
        
        await query.edit_message_text(
            f"💰 **ТЫ ЗАБРАЛ ВЫИГРЫШ!**\n\n"
            f"💰 Ставка: {game['bet']}\n"
            f"🎉 Выигрыш: {win} (x{multipliers[game['floor']]})"
        )
        del active_tower[game_id]
        return
    
    floor = int(data[3])
    cell = int(data[4])
    
    win_cell = random.randint(0, 2)
    
    if cell == win_cell:
        # Выигрышный этаж
        game['floor'] += 1
        multipliers = [1, 2, 3, 5, 10, 20]
        
        await query.edit_message_text(
            f"✅ **ТЫ ПРОШЁЛ ЭТАЖ!**\n\n"
            f"📈 Текущий этаж: {game['floor']}/5\n"
            f"🎯 Текущий множитель: {multipliers[game['floor']]}x"
        )
        
        # Показываем следующий этаж
        await show_tower_floor(update, context, game_id)
    else:
        # Проигрыш
        game['game_over'] = True
        update_user(game['user_id'], coins=-game['bet'], loss=True)
        
        await query.edit_message_text(
            f"💥 **ТЫ ПОДОРВАЛСЯ НА МИНЕ!**\n\n"
            f"💰 Потеряно: {game['bet']} монет"
        )
        del active_tower[game_id]

# ===== МИНЫ =====
async def mines(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Игра в мины"""
    user = update.effective_user
    user_id = user.id
    
    if not context.args:
        await update.message.reply_text("❌ **Использование:** `/mines [ставка]`")
        return
    
    try:
        bet = int(context.args[0])
        if bet <= 0:
            raise ValueError
    except:
        await update.message.reply_text("❌ **Неверная ставка!**")
        return
    
    # Проверка баланса
    coins, _, _, _, _, _, _, _, _ = get_user(user_id)
    if coins < bet:
        await update.message.reply_text(f"❌ **Недостаточно монет!** У тебя {coins}")
        return
    
    # Создаём игру
    game_id = f"mines_{user_id}_{datetime.now().timestamp()}"
    
    # Поле 5x5 с 3 минами
    field = ['💎'] * 22 + ['💣'] * 3
    random.shuffle(field)
    
    active_mines[game_id] = {
        'user_id': user_id,
        'bet': bet,
        'field': field,
        'opened': [False] * 25,
        'multiplier': 1.0,
        'game_over': False,
        'diamonds': 0
    }
    
    await show_mines_field(update, context, game_id)

async def show_mines_field(update, context, game_id):
    """Показывает поле с минами"""
    game = active_mines.get(game_id)
    if not game:
        return
    
    keyboard = []
    for i in range(5):
        row = []
        for j in range(5):
            idx = i * 5 + j
            if game['opened'][idx]:
                cell = game['field'][idx]
            else:
                cell = '⬛'
            row.append(InlineKeyboardButton(cell, callback_data=f"mines_{game_id}_{idx}"))
        keyboard.append(row)
    
    if not game['game_over']:
        keyboard.append([InlineKeyboardButton("💰 ЗАБРАТЬ ВЫИГРЫШ", callback_data=f"mines_cash_{game_id}")])
    
    multipliers = [1.0, 1.2, 1.5, 1.8, 2.2, 2.7, 3.3, 4.0, 4.8, 5.7, 6.7, 7.8, 9.0, 10.3, 11.7, 13.2, 14.8, 16.5, 18.3, 20.2, 22.2, 24.3, 26.5]
    
    await context.bot.send_message(
        game['user_id'],
        f"💣 **МИНЫ** 💣\n\n"
        f"💰 Ставка: {game['bet']}\n"
        f"💎 Алмазов: {game['diamonds']}\n"
        f"📈 Множитель: x{multipliers[game['diamonds']]:.1f}\n\n"
        f"Выбери клетку:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def mines_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик мин"""
    query = update.callback_query
    await query.answer()
    
    data = query.data.split('_')
    action = data[1]
    
    if action == "none":
        return
    
    game_id = data[2]
    game = active_mines.get(game_id)
    
    if not game or game['game_over']:
        await query.edit_message_text("❌ **Игра уже закончена!**")
        return
    
    if action == "cash":
        # Забрать выигрыш
        multipliers = [1.0, 1.2, 1.5, 1.8, 2.2, 2.7, 3.3, 4.0, 4.8, 5.7, 6.7, 7.8, 9.0, 10.3, 11.7, 13.2, 14.8, 16.5, 18.3, 20.2, 22.2, 24.3, 26.5]
        win = int(game['bet'] * multipliers[game['diamonds']])
        update_user(game['user_id'], coins=win - game['bet'], mines_wins=1)
        
        await query.edit_message_text(
            f"💰 **ТЫ ЗАБРАЛ ВЫИГРЫШ!**\n\n"
            f"💰 Ставка: {game['bet']}\n"
            f"💎 Алмазов: {game['diamonds']}\n"
            f"🎉 Выигрыш: {win}"
        )
        del active_mines[game_id]
        return
    
    idx = int(data[3])
    
    if game['opened'][idx]:
        return
    
    game['opened'][idx] = True
    
    if game['field'][idx] == '💣':
        # Нашли мину
        game['game_over'] = True
        update_user(game['user_id'], coins=-game['bet'], loss=True)
        
        # Показываем все мины
        field_display = []
        for i in range(5):
            row = []
            for j in range(5):
                pos = i * 5 + j
                row.append(game['field'][pos])
            field_display.append(''.join(row))
        
        field_text = '\n'.join(field_display)
        
        await query.edit_message_text(
            f"💥 **ТЫ ПОДОРВАЛСЯ НА МИНЕ!** 💥\n\n"
            f"💰 Потеряно: {game['bet']} монет\n\n"
            f"Поле:\n{field_text}"
        )
        del active_mines[game_id]
    else:
        # Нашли алмаз
        game['diamonds'] += 1
        multipliers = [1.0, 1.2, 1.5, 1.8, 2.2, 2.7, 3.3, 4.0, 4.8, 5.7, 6.7, 7.8, 9.0, 10.3, 11.7, 13.2, 14.8, 16.5, 18.3, 20.2, 22.2, 24.3, 26.5]
        
        if game['diamonds'] >= 22:
            # Все алмазы собраны
            win = int(game['bet'] * 26.5)
            update_user(game['user_id'], coins=win - game['bet'], mines_wins=1)
            
            await query.edit_message_text(
                f"🎉 **ТЫ СОБРАЛ ВСЕ АЛМАЗЫ!** 🎉\n\n"
                f"💰 Ставка: {game['bet']}\n"
                f"🎉 Выигрыш: {win}"
            )
            del active_mines[game_id]
        else:
            # Продолжаем игру
            await show_mines_field(update, context, game_id)

# ===== СЛОТЫ =====
async def slot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Слоты"""
    user = update.effective_user
    user_id = user.id
    
    if not context.args:
        await update.message.reply_text("❌ **Использование:** `/slot [ставка]`")
        return
    
    try:
        bet = int(context.args[0])
        if bet <= 0:
            raise ValueError
    except:
        await update.message.reply_text("❌ **Неверная ставка!**")
        return
    
    # Проверка баланса
    coins, _, _, _, _, _, _, _, _ = get_user(user_id)
    if coins < bet:
        await update.message.reply_text(f"❌ **Недостаточно монет!** У тебя {coins}")
        return
    
    # Крутим слоты
    symbols = ['🍒', '💎', '7️⃣', '👑']
    result = [random.choice(symbols) for _ in range(3)]
    
    # Множители
    multipliers = {
        '🍒': 2,
        '💎': 3,
        '7️⃣': 5,
        '👑': 10
    }
    
    multiplier = 1
    if result[0] == result[1] == result[2]:
        multiplier = multipliers.get(result[0], 1)
        if result[0] == '👑' and random.random() < 0.1:
            multiplier = 20  # Джекпот
    
    win = bet * multiplier
    
    if multiplier > 1:
        update_user(user_id, coins=win - bet, slot_wins=1)
        result_text = f"🎉 **ТЫ ВЫИГРАЛ!** +{win - bet} монет"
    else:
        update_user(user_id, coins=-bet, loss=True)
        result_text = f"💔 **ТЫ ПРОИГРАЛ!** -{bet} монет"
    
    await update.message.reply_text(
        f"🎰 **СЛОТЫ** 🎰\n\n"
        f"{' | '.join(result)}\n\n"
        f"💰 Ставка: {bet}\n"
        f"{result_text}"
    )

# ===== ЗАПУСК =====
def main():
    init_db()
    
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Основные команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("top", top))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("transfer", transfer))
    
    # Игры
    app.add_handler(CommandHandler("dice", dice))
    app.add_handler(CommandHandler("darts", darts))
    app.add_handler(CommandHandler("bowling", bowling))
    app.add_handler(CommandHandler("soccer", soccer))
    app.add_handler(CommandHandler("basketball", basketball))
    app.add_handler(CommandHandler("tower", tower))
    app.add_handler(CommandHandler("mines", mines))
    app.add_handler(CommandHandler("slot", slot))
    
    # Дуэли
    app.add_handler(CommandHandler("duel", duel_command))
    
    # Callback обработчики
    app.add_handler(CallbackQueryHandler(tower_callback, pattern="^tower_"))
    app.add_handler(CallbackQueryHandler(mines_callback, pattern="^mines_"))
    
    print("⚔️ BedPVP TURBO запущен!")
    print(f"👑 Владыка: @God_Mon1tyy")
    
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TELEGRAM_TOKEN,
        webhook_url=f"https://{BOT_USERNAME[1:]}.onrender.com/{TELEGRAM_TOKEN}"
    )

if __name__ == "__main__":
    main()
