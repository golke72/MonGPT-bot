import sqlite3
import os
import random
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

# ===== ТВОИ ДАННЫЕ =====
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
PORT = int(os.environ.get('PORT', 10000))
BOT_USERNAME = "@MonGPT_bot"
# ========================

# ===== ТВОЙ ID =====
OWNER_ID = 7745009183
# ===================

# ===== ИГРОВЫЕ ДАННЫЕ =====
active_21 = {}  # {game_id: game_data}
duel_challenges = {}  # {challenge_id: challenge_data}

# ===== БАЗА ДАННЫХ =====
def init_db():
    conn = sqlite3.connect('mongpt.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY, 
                  username TEXT,
                  first_name TEXT,
                  coins INTEGER DEFAULT 1000,
                  wins INTEGER DEFAULT 0,
                  losses INTEGER DEFAULT 0,
                  bj_wins INTEGER DEFAULT 0,
                  vip BOOLEAN DEFAULT 0,
                  joined_date TIMESTAMP)''')
    conn.commit()
    conn.close()

def get_user(user_id, username=None, first_name=None):
    """Получает или создаёт пользователя"""
    conn = sqlite3.connect('mongpt.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id=?", (user_id,))
    user = c.fetchone()
    
    if not user:
        coins = 1000
        vip = False
        
        c.execute("""INSERT INTO users 
                     (id, username, first_name, coins, vip, joined_date) 
                     VALUES (?,?,?,?,?,?)""",
                  (user_id, username, first_name, coins, vip, datetime.now()))
        conn.commit()
        wins = 0
        losses = 0
        bj_wins = 0
    else:
        coins = user[3]
        wins = user[4]
        losses = user[5]
        bj_wins = user[6] if len(user) > 6 else 0
        vip = user[7] if len(user) > 7 else False
    
    conn.close()
    return coins, wins, losses, bj_wins, vip, user[2] or "Игрок"

def update_user(user_id, coins=None, win=None, loss=None, bj_win=None, vip=None):
    """Обновляет данные пользователя"""
    conn = sqlite3.connect('mongpt.db')
    c = conn.cursor()
    if coins is not None:
        c.execute("UPDATE users SET coins = coins + ? WHERE id=?", (coins, user_id))
    if win:
        c.execute("UPDATE users SET wins = wins + 1 WHERE id=?", (user_id,))
    if loss:
        c.execute("UPDATE users SET losses = losses + 1 WHERE id=?", (user_id,))
    if bj_win:
        c.execute("UPDATE users SET bj_wins = bj_wins + 1 WHERE id=?", (user_id,))
    if vip is not None:
        c.execute("UPDATE users SET vip = ? WHERE id=?", (vip, user_id))
    conn.commit()
    conn.close()

# ===== ФУНКЦИИ ДЛЯ 21 =====
def create_deck():
    suits = ['♠', '♥', '♦', '♣']
    cards = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
    deck = []
    for suit in suits:
        for card in cards:
            deck.append(f"{card}{suit}")
    random.shuffle(deck)
    return deck

def card_value(card):
    rank = card[:-1]
    if rank in ['J', 'Q', 'K']:
        return 10
    elif rank == 'A':
        return 11
    else:
        return int(rank)

def calculate_hand(hand):
    total = 0
    aces = 0
    for card in hand:
        val = card_value(card)
        if val == 11:
            aces += 1
        total += val
    while total > 21 and aces > 0:
        total -= 10
        aces -= 1
    return total

def hand_to_string(hand):
    return ' '.join(hand)

# ===== ОБРАБОТЧИК ТЕКСТОВЫХ КОМАНД =====
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает только команды"""
    text = update.message.text.lower().strip()
    user = update.effective_user
    
    allowed_commands = ['б', 'топ', 'дать', 'дуэль', 'выдать', 'снять', 'vip', 'unvip', 'инфо']
    
    command = text.split()[0] if text else ""
    
    if command not in allowed_commands:
        return
    
    # ===== БАЛАНС =====
    if text == 'б':
        coins, _, _, _, _, name = get_user(user.id)
        await update.message.reply_text(f"💰 **{name}, твой баланс:** {coins} монет")
        return
    
    # ===== ТОП =====
    if text == 'топ':
        conn = sqlite3.connect('mongpt.db')
        c = conn.cursor()
        c.execute("SELECT username, first_name, coins FROM users ORDER BY coins DESC LIMIT 10")
        top_users = c.fetchall()
        conn.close()
        
        if not top_users:
            await update.message.reply_text("📊 Пока нет данных")
            return
        
        result = "🏆 **ТОП БОГАЧЕЙ** 🏆\n\n"
        for i, (username, first_name, coins) in enumerate(top_users, 1):
            name = f"@{username}" if username else first_name or f"Игрок {i}"
            medal = "👑" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            result += f"{medal} {name} — {coins} 🪙\n"
        
        await update.message.reply_text(result)
        return
    
    # ===== ПЕРЕВОД МОНЕТ =====
    if command == 'дать':
        replied = update.message.reply_to_message
        if not replied:
            await update.message.reply_text("❌ Ответь на сообщение друга, чтобы перевести монеты!")
            return
        
        opponent = replied.from_user
        
        if opponent.id == user.id:
            await update.message.reply_text("❌ Нельзя переводить самому себе!")
            return
        
        parts = text.split()
        if len(parts) != 2:
            await update.message.reply_text("❌ Напиши: дать 100")
            return
        
        try:
            amount = int(parts[1])
            if amount <= 0:
                raise ValueError
        except:
            await update.message.reply_text("❌ Неверная сумма")
            return
        
        coins, _, _, _, _, _ = get_user(user.id)
        if coins < amount:
            await update.message.reply_text(f"❌ У тебя только {coins} монет")
            return
        
        update_user(user.id, coins=-amount)
        update_user(opponent.id, coins=amount)
        
        await update.message.reply_text(f"✅ Переведено {amount} монет {opponent.first_name}")
        
        try:
            await context.bot.send_message(
                opponent.id,
                f"💰 **ПЕРЕВОД!**\n\n{user.first_name} перевёл тебе {amount} монет!"
            )
        except:
            pass
        return
    
    # ===== ДУЭЛЬ (кости) =====
    if command == 'дуэль':
        replied = update.message.reply_to_message
        if not replied:
            await update.message.reply_text("❌ Ответь на сообщение друга, чтобы вызвать его на дуэль!")
            return
        
        opponent = replied.from_user
        
        if opponent.id == user.id:
            await update.message.reply_text("❌ Нельзя вызывать самого себя!")
            return
        
        if opponent.is_bot:
            await update.message.reply_text("❌ С ботами не дуэлимся!")
            return
        
        parts = text.split()
        if len(parts) != 2:
            await update.message.reply_text("❌ дуэль [ставка]\nПример: дуэль 50")
            return
        
        try:
            bet = int(parts[1])
            if bet <= 0:
                raise ValueError
        except:
            await update.message.reply_text("❌ Неверная ставка")
            return
        
        # Проверяем балансы
        user_coins, _, _, _, user_vip, user_name = get_user(user.id)
        opp_coins, _, _, _, opp_vip, opp_name = get_user(opponent.id)
        
        if not user_vip and user_coins < bet:
            await update.message.reply_text(f"❌ У тебя только {user_coins} монет")
            return
        
        if not opp_vip and opp_coins < bet:
            await update.message.reply_text(f"❌ У {opp_name} только {opp_coins} монет")
            return
        
        # Создаём вызов
        challenge_id = f"duel_{user.id}_{opponent.id}_{datetime.now().timestamp()}"
        
        duel_challenges[challenge_id] = {
            'challenger': user.id,
            'opponent': opponent.id,
            'bet': bet,
            'type': 'duel'
        }
        
        keyboard = [[
            InlineKeyboardButton("✅ Принять", callback_data=f"accept_duel_{challenge_id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"decline_duel_{challenge_id}")
        ]]
        
        await context.bot.send_message(
            opponent.id,
            f"⚔️ **ТЕБЯ ВЫЗЫВАЮТ НА ДУЭЛЬ!**\n\n"
            f"👤 Противник: {user_name}\n"
            f"💰 Ставка: {bet}\n\n"
            f"У тебя 2 минуты, чтобы принять!",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        await update.message.reply_text(
            f"⚔️ **ВЫЗОВ ОТПРАВЛЕН!**\n\n"
            f"👤 Противник: {opp_name}\n"
            f"💰 Ставка: {bet}\n\n"
            f"⏳ Ожидание ответа..."
        )
        return
    
    # ===== АДМИН-КОМАНДЫ (только для OWNER_ID) =====
    if user.id != OWNER_ID:
        return
    
    # ВЫДАТЬ МОНЕТЫ
    if command == 'выдать':
        replied = update.message.reply_to_message
        if not replied:
            await update.message.reply_text("❌ Ответь на сообщение игрока, чтобы выдать монеты!")
            return
        
        target = replied.from_user
        parts = text.split()
        
        if len(parts) != 2:
            await update.message.reply_text("❌ Напиши: выдать 1000")
            return
        
        try:
            amount = int(parts[1])
            if amount <= 0:
                raise ValueError
        except:
            await update.message.reply_text("❌ Неверная сумма")
            return
        
        update_user(target.id, coins=amount)
        await update.message.reply_text(f"✅ Выдано {amount} монет {target.first_name}")
        
        try:
            await context.bot.send_message(
                target.id,
                f"🎁 **ПОДАРОК ОТ АДМИНА!**\n\n+{amount} монет зачислено на баланс!"
            )
        except:
            pass
        return
    
    # СНЯТЬ МОНЕТЫ
    if command == 'снять':
        replied = update.message.reply_to_message
        if not replied:
            await update.message.reply_text("❌ Ответь на сообщение игрока, чтобы снять монеты!")
            return
        
        target = replied.from_user
        parts = text.split()
        
        if len(parts) != 2:
            await update.message.reply_text("❌ Напиши: снять 500")
            return
        
        try:
            amount = int(parts[1])
            if amount <= 0:
                raise ValueError
        except:
            await update.message.reply_text("❌ Неверная сумма")
            return
        
        target_coins, _, _, _, _, _ = get_user(target.id)
        if target_coins < amount:
            await update.message.reply_text(f"❌ У игрока только {target_coins} монет")
            return
        
        update_user(target.id, coins=-amount)
        await update.message.reply_text(f"✅ Снято {amount} монет у {target.first_name}")
        return
    
    # СДЕЛАТЬ VIP
    if command == 'vip':
        replied = update.message.reply_to_message
        if not replied:
            await update.message.reply_text("❌ Ответь на сообщение игрока, чтобы сделать VIP!")
            return
        
        target = replied.from_user
        update_user(target.id, vip=True)
        await update.message.reply_text(f"✅ {target.first_name} теперь VIP!")
        
        try:
            await context.bot.send_message(
                target.id,
                f"👑 **VIP СТАТУС!**\n\nТы получил VIP-статус от администратора!"
            )
        except:
            pass
        return
    
    # УБРАТЬ VIP
    if command == 'unvip':
        replied = update.message.reply_to_message
        if not replied:
            await update.message.reply_text("❌ Ответь на сообщение игрока, чтобы убрать VIP!")
            return
        
        target = replied.from_user
        update_user(target.id, vip=False)
        await update.message.reply_text(f"✅ У {target.first_name} убран VIP")
        return
    
    # ИНФОРМАЦИЯ
    if command == 'инфо':
        replied = update.message.reply_to_message
        if not replied:
            await update.message.reply_text("❌ Ответь на сообщение игрока, чтобы получить информацию!")
            return
        
        target = replied.from_user
        coins, wins, losses, bj_wins, vip, name = get_user(target.id)
        
        total = wins + losses
        winrate = (wins / total * 100) if total > 0 else 0
        
        text = (
            f"📊 **ИНФОРМАЦИЯ ОБ ИГРОКЕ**\n\n"
            f"👤 Имя: {name}\n"
            f"🆔 ID: {target.id}\n"
            f"💰 Монет: {coins}\n"
            f"🏆 Побед: {wins}\n"
            f"💔 Поражений: {losses}\n"
            f"📊 Винрейт: {winrate:.1f}%\n"
            f"🃏 Побед в 21: {bj_wins}\n"
            f"👑 VIP: {'Да' if vip else 'Нет'}"
        )
        
        await update.message.reply_text(text)
        return

# ===== КОМАНДА 21 =====
async def twenty_one(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для игры в 21"""
    user = update.effective_user
    
    if not update.message.reply_to_message:
        await update.message.reply_text(
            "❌ **Ответь на сообщение друга, чтобы сыграть в 21!**\n"
            "Пример: ответь на его сообщение и напиши /21 50"
        )
        return
    
    opponent = update.message.reply_to_message.from_user
    
    if opponent.id == user.id:
        await update.message.reply_text("❌ Нельзя играть с самим собой!")
        return
    
    if opponent.is_bot:
        await update.message.reply_text("❌ С ботами не играем!")
        return
    
    if not context.args:
        await update.message.reply_text("❌ /21 [ставка]\nПример: /21 50")
        return
    
    try:
        bet = int(context.args[0])
        if bet <= 0:
            raise ValueError
    except:
        await update.message.reply_text("❌ Неверная ставка")
        return
    
    user_coins, _, _, _, user_vip, user_name = get_user(user.id)
    opp_coins, _, _, _, opp_vip, opp_name = get_user(opponent.id)
    
    if not user_vip and user_coins < bet:
        await update.message.reply_text(f"❌ У тебя только {user_coins} монет")
        return
    
    if not opp_vip and opp_coins < bet:
        await update.message.reply_text(f"❌ У {opp_name} только {opp_coins} монет")
        return
    
    # Создаём вызов на 21
    challenge_id = f"bj_{user.id}_{opponent.id}_{datetime.now().timestamp()}"
    
    duel_challenges[challenge_id] = {
        'challenger': user.id,
        'opponent': opponent.id,
        'bet': bet,
        'type': 'bj'
    }
    
    keyboard = [[
        InlineKeyboardButton("✅ Принять", callback_data=f"accept_bj_{challenge_id}"),
        InlineKeyboardButton("❌ Отклонить", callback_data=f"decline_bj_{challenge_id}")
    ]]
    
    await context.bot.send_message(
        opponent.id,
        f"🃏 **ТЕБЯ ВЫЗЫВАЮТ НА 21!**\n\n"
        f"👤 Противник: {user_name}\n"
        f"💰 Ставка: {bet}\n\n"
        f"У тебя 2 минуты, чтобы принять!",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    await update.message.reply_text(
        f"🃏 **ВЫЗОВ ОТПРАВЛЕН!**\n\n"
        f"👤 Противник: {opp_name}\n"
        f"💰 Ставка: {bet}\n\n"
        f"⏳ Ожидание ответа..."
    )

# ===== ОБРАБОТЧИК КНОПОК =====
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик всех кнопок"""
    query = update.callback_query
    await query.answer()
    
    data = query.data.split('_')
    action = data[0]
    challenge_id = '_'.join(data[2:])
    
    if challenge_id not in duel_challenges:
        await query.edit_message_text("❌ Вызов уже недействителен!")
        return
    
    challenge = duel_challenges[challenge_id]
    user_id = query.from_user.id
    
    if user_id != challenge['opponent']:
        await query.answer("Это не твой вызов!", show_alert=True)
        return
    
    game_type = challenge.get('type', 'duel')
    
    if action == 'accept':
        await query.edit_message_text("✅ Вызов принят! Игра начинается...")
        
        if game_type == 'bj':
            await start_bj_game(query, context, challenge)
        else:
            await start_duel_game(query, context, challenge)
        
        del duel_challenges[challenge_id]
        
    elif action == 'decline':
        await query.edit_message_text("❌ Вызов отклонён")
        del duel_challenges[challenge_id]

async def start_duel_game(query, context, challenge):
    """Начинает игру в дуэль (кости)"""
    challenger_id = challenge['challenger']
    opponent_id = challenge['opponent']
    bet = challenge['bet']
    
    chall_name = (await context.bot.get_chat(challenger_id)).first_name
    opp_name = (await context.bot.get_chat(opponent_id)).first_name
    
    await query.message.reply_text("🎲 Бросаем кости...")
    
    chall_dice = await context.bot.send_dice(chat_id=query.message.chat_id)
    opp_dice = await context.bot.send_dice(chat_id=query.message.chat_id)
    
    chall_val = chall_dice.dice.value
    opp_val = opp_dice.dice.value
    
    if chall_val > opp_val:
        update_user(challenger_id, coins=bet, win=True)
        update_user(opponent_id, coins=-bet, loss=True)
        result = f"🎉 **{chall_name} ВЫИГРАЛ!** +{bet} монет"
    elif opp_val > chall_val:
        update_user(challenger_id, coins=-bet, loss=True)
        update_user(opponent_id, coins=bet, win=True)
        result = f"🎉 **{opp_name} ВЫИГРАЛ!** +{bet} монет"
    else:
        result = f"🤝 **НИЧЬЯ!** Ставка возвращена"
    
    await query.message.reply_text(
        f"⚔️ **ДУЭЛЬ ЗАВЕРШЕНА**\n\n"
        f"👤 {chall_name}: {chall_val}\n"
        f"👤 {opp_name}: {opp_val}\n"
        f"💰 Ставка: {bet}\n\n"
        f"{result}"
    )

async def start_bj_game(query, context, challenge):
    """Начинает игру в 21"""
    player1 = challenge['challenger']
    player2 = challenge['opponent']
    bet = challenge['bet']
    
    game_id = f"21_{player1}_{player2}_{datetime.now().timestamp()}"
    
    deck = create_deck()
    hand1 = [deck.pop(), deck.pop()]
    hand2 = [deck.pop(), deck.pop()]
    
    active_21[game_id] = {
        'player1': player1,
        'player2': player2,
        'bet': bet,
        'hand1': hand1,
        'hand2': hand2,
        'deck': deck,
        'turn': player1,
        'stood1': False,
        'stood2': False
    }
    
    game = active_21[game_id]
    
    keyboard = [[
        InlineKeyboardButton("🃏 Взять", callback_data=f"21_hit_{game_id}"),
        InlineKeyboardButton("⏹️ Хватит", callback_data=f"21_stand_{game_id}")
    ]]
    
    p1_name = (await context.bot.get_chat(player1)).first_name
    p2_name = (await context.bot.get_chat(player2)).first_name
    
    p1_hand = hand_to_string(game['hand1'])
    p1_score = calculate_hand(game['hand1'])
    p2_display = hand_to_string([game['hand2'][0], '🂠'])
    
    await context.bot.send_message(
        player1,
        f"🃏 **21 (БЛЭКДЖЕК)**\n\n"
        f"💰 Ставка: {bet}\n\n"
        f"👤 **Ты**:\n"
        f"Карты: {p1_hand}\n"
        f"Очки: {p1_score}\n\n"
        f"👤 **{p2_name}**:\n"
        f"Карты: {p2_display}\n\n"
        f"🎮 Твой ход",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    p2_hand = hand_to_string([game['hand2'][0], '🂠'])
    p2_score = "?"
    p1_display = hand_to_string(game['hand1'])
    
    await context.bot.send_message(
        player2,
        f"🃏 **21 (БЛЭКДЖЕК)**\n\n"
        f"💰 Ставка: {bet}\n\n"
        f"👤 **{p1_name}**:\n"
        f"Карты: {p1_display}\n\n"
        f"👤 **Ты**:\n"
        f"Карты: {p2_hand}\n"
        f"Очки: {p2_score}\n\n"
        f"🎮 Ход {p1_name}..."
    )

async def twenty_one_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопок для 21"""
    query = update.callback_query
    await query.answer()
    
    data = query.data.split('_')
    action = data[1]
    game_id = '_'.join(data[2:])
    
    if game_id not in active_21:
        await query.edit_message_text("❌ Игра уже закончена!")
        return
    
    game = active_21[game_id]
    user_id = query.from_user.id
    
    if user_id not in [game['player1'], game['player2']]:
        await query.answer("Это не твоя игра!", show_alert=True)
        return
    
    if game['turn'] != user_id:
        await query.answer("Сейчас не твой ход!", show_alert=True)
        return
    
    if user_id == game['player1']:
        my_hand = game['hand1']
        opp_hand = game['hand2']
        my_id = game['player1']
        opp_id = game['player2']
    else:
        my_hand = game['hand2']
        opp_hand = game['hand1']
        my_id = game['player2']
        opp_id = game['player1']
    
    opp_name = (await context.bot.get_chat(opp_id)).first_name
    
    if action == 'hit':
        new_card = game['deck'].pop()
        my_hand.append(new_card)
        score = calculate_hand(my_hand)
        
        if score > 21:
            update_user(my_id, coins=-game['bet'], loss=True)
            update_user(opp_id, coins=game['bet'], win=True, bj_win=True)
            
            my_hand_str = hand_to_string(my_hand)
            opp_hand_str = hand_to_string(opp_hand)
            
            await query.edit_message_text(
                f"🃏 **ИГРА ЗАВЕРШЕНА**\n\n"
                f"💰 Ставка: {game['bet']}\n\n"
                f"👤 **Ты**:\n"
                f"Карты: {my_hand_str}\n"
                f"Очки: {score}\n\n"
                f"👤 **{opp_name}**:\n"
                f"Карты: {opp_hand_str}\n"
                f"Очки: {calculate_hand(opp_hand)}\n\n"
                f"💔 **ТЫ ПРОИГРАЛ!** Перебор! -{game['bet']} монет"
            )
            
            await context.bot.send_message(
                opp_id,
                f"🎉 **ТЫ ВЫИГРАЛ!** Противник перебрал! +{game['bet']} монет"
            )
            
            del active_21[game_id]
            return
        else:
            game['turn'] = opp_id
        
        my_hand_str = hand_to_string(my_hand)
        my_score = calculate_hand(my_hand)
        
        if game['turn'] == game['player1']:
            opp_display = hand_to_string([game['hand2'][0], '🂠'])
            opp_score = "?"
            turn_text = f"Ход {opp_name}"
        else:
            opp_display = hand_to_string(opp_hand)
            opp_score = calculate_hand(opp_hand)
            turn_text = f"Ход {opp_name}"
        
        keyboard = [[
            InlineKeyboardButton("🃏 Взять", callback_data=f"21_hit_{game_id}"),
            InlineKeyboardButton("⏹️ Хватит", callback_data=f"21_stand_{game_id}")
        ]]
        
        await query.edit_message_text(
            f"🃏 **21 (БЛЭКДЖЕК)**\n\n"
            f"💰 Ставка: {game['bet']}\n\n"
            f"👤 **Ты**:\n"
            f"Карты: {my_hand_str}\n"
            f"Очки: {my_score}\n\n"
            f"👤 **{opp_name}**:\n"
            f"Карты: {opp_display}\n"
            f"Очки: {opp_score}\n\n"
            f"🎮 {turn_text}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        await context.bot.send_message(
            opp_id,
            f"🃏 **21 (БЛЭКДЖЕК)**\n\n"
            f"💰 Ставка: {game['bet']}\n\n"
            f"👤 **Ты**:\n"
            f"Карты: {hand_to_string([opp_hand[0], '🂠'])}\n"
            f"🎮 Твой ход!",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif action == 'stand':
        if user_id == game['player1']:
            game['stood1'] = True
            game['turn'] = game['player2']
        else:
            game['stood2'] = True
            game['turn'] = game['player1']
        
        if game['stood1'] and game['stood2']:
            p1_score = calculate_hand(game['hand1'])
            p2_score = calculate_hand(game['hand2'])
            
            p1_name = (await context.bot.get_chat(game['player1'])).first_name
            p2_name = (await context.bot.get_chat(game['player2'])).first_name
            p1_hand = hand_to_string(game['hand1'])
            p2_hand = hand_to_string(game['hand2'])
            
            if p1_score > p2_score:
                update_user(game['player1'], coins=game['bet'], win=True, bj_win=True)
                update_user(game['player2'], coins=-game['bet'], loss=True)
                result = f"🎉 **{p1_name} ВЫИГРАЛ!** +{game['bet']} монет"
            elif p2_score > p1_score:
                update_user(game['player1'], coins=-game['bet'], loss=True)
                update_user(game['player2'], coins=game['bet'], win=True, bj_win=True)
                result = f"🎉 **{p2_name} ВЫИГРАЛ!** +{game['bet']} монет"
            else:
                result = f"🤝 **НИЧЬЯ!**"
            
            await context.bot.send_message(
                game['player1'],
                f"🃏 **ИГРА ЗАВЕРШЕНА**\n\n"
                f"💰 Ставка: {game['bet']}\n\n"
                f"👤 **Ты**:\n"
                f"Карты: {p1_hand}\n"
                f"Очки: {p1_score}\n\n"
                f"👤 **{p2_name}**:\n"
                f"Карты: {p2_hand}\n"
                f"Очки: {p2_score}\n\n"
                f"{result}"
            )
            
            await context.bot.send_message(
                game['player2'],
                f"🃏 **ИГРА ЗАВЕРШЕНА**\n\n"
                f"💰 Ставка: {game['bet']}\n\n"
                f"👤 **{p1_name}**:\n"
                f"Карты: {p1_hand}\n"
                f"Очки: {p1_score}\n\n"
                f"👤 **Ты**:\n"
                f"Карты: {p2_hand}\n"
                f"Очки: {p2_score}\n\n"
                f"{result}"
            )
            
            del active_21[game_id]
        else:
            my_hand = game['hand1'] if user_id == game['player1'] else game['hand2']
            opp_hand = game['hand2'] if user_id == game['player1'] else game['hand1']
            
            my_hand_str = hand_to_string(my_hand)
            my_score = calculate_hand(my_hand)
            
            if game['turn'] == game['player1']:
                opp_display = hand_to_string([game['hand2'][0], '🂠'])
                opp_score = "?"
                turn_text = f"Ход { (await context.bot.get_chat(game['player1'])).first_name }"
            else:
                opp_display = hand_to_string(opp_hand)
                opp_score = calculate_hand(opp_hand)
                turn_text = f"Ход { (await context.bot.get_chat(game['player2'])).first_name }"
            
            keyboard = [[
                InlineKeyboardButton("🃏 Взять", callback_data=f"21_hit_{game_id}"),
                InlineKeyboardButton("⏹️ Хватит", callback_data=f"21_stand_{game_id}")
            ]]
            
            await query.edit_message_text(
                f"🃏 **21 (БЛЭКДЖЕК)**\n\n"
                f"💰 Ставка: {game['bet']}\n\n"
                f"👤 **Ты**:\n"
                f"Карты: {my_hand_str}\n"
                f"Очки: {my_score}\n\n"
                f"👤 **{opp_name}**:\n"
                f"Карты: {opp_display}\n"
                f"Очки: {opp_score}\n\n"
                f"🎮 {turn_text}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

# ===== ОБЫЧНЫЕ ИГРЫ =====
async def play_game(update, context, emoji, game_name, win_threshold=4):
    """Обычные игры против бота"""
    user = update.effective_user
    
    if not context.args:
        await update.message.reply_text(f"❌ /{game_name} [ставка]")
        return
    
    try:
        bet = int(context.args[0])
        if bet <= 0:
            raise ValueError
    except:
        await update.message.reply_text("❌ Неверная ставка")
        return
    
    coins, _, _, _, vip, _ = get_user(user.id)
    if not vip and coins < bet:
        await update.message.reply_text(f"❌ У тебя только {coins} монет")
        return
    
    dice = await context.bot.send_dice(chat_id=update.message.chat_id, emoji=emoji)
    value = dice.dice.value
    
    win = value >= win_threshold
    
    if win:
        win_amount = bet * 2
        if not vip:
            update_user(user.id, coins=win_amount - bet, win=True)
        await update.message.reply_text(f"{emoji} **ВЫИГРЫШ!** +{win_amount - bet} монет")
    else:
        if not vip:
            update_user(user.id, coins=-bet, loss=True)
        await update.message.reply_text(f"{emoji} **ПРОИГРЫШ!** -{bet} монет")

async def dice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await play_game(update, context, '🎲', 'dice', 4)

async def darts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await play_game(update, context, '🎯', 'darts', 4)

async def bowling(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await play_game(update, context, '🎳', 'bowling', 4)

async def soccer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await play_game(update, context, '⚽', 'soccer', 4)

async def basketball(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await play_game(update, context, '🏀', 'basketball', 4)

# ===== КОМАНДЫ =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    coins, wins, losses, bj_wins, vip, name = get_user(user.id, user.username, user.first_name)
    
    text = (
        f"🎮 **MonGPT CASINO** 🎮\n\n"
        f"👤 Игрок: {name}\n"
        f"💰 Монет: {coins}\n"
        f"🏆 Побед: {wins}\n"
        f"💔 Поражений: {losses}\n"
        f"🃏 Побед в 21: {bj_wins}\n"
        f"{'👑 VIP' if vip else '👤 Обычный'}\n\n"
        f"**ТЕКСТОВЫЕ КОМАНДЫ:**\n"
        f"б - баланс\n"
        f"топ - топ богачей\n"
        f"дать 100 - перевести монеты (ответь)\n"
        f"дуэль 50 - вызвать на дуэль (ответь)\n\n"
        f"**ИГРЫ С БОТОМ:**\n"
        f"/dice 50 - 🎲 Кости\n"
        f"/darts 50 - 🎯 Дартс\n"
        f"/bowling 50 - 🎳 Боулинг\n"
        f"/soccer 50 - ⚽ Футбол\n"
        f"/basketball 50 - 🏀 Баскетбол\n\n"
        f"**ИГРЫ С ДРУЗЬЯМИ:**\n"
        f"/21 50 - 🃏 Блэкджек (ответь)\n\n"
        f"**👑 АДМИН-КОМАНДЫ:**\n"
        f"(ответь на сообщение игрока)\n"
        f"выдать 1000 - выдать монеты\n"
        f"снять 500 - снять монеты\n"
        f"vip - сделать VIP\n"
        f"unvip - убрать VIP\n"
        f"инфо - информация об игроке"
    )
    
    await update.message.reply_text(text)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)

# ===== ЗАПУСК =====
def main():
    init_db()
    
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Основные команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("21", twenty_one))
    app.add_handler(CommandHandler("dice", dice))
    app.add_handler(CommandHandler("darts", darts))
    app.add_handler(CommandHandler("bowling", bowling))
    app.add_handler(CommandHandler("soccer", soccer))
    app.add_handler(CommandHandler("basketball", basketball))
    
    # Обработчик текстовых команд
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Callback обработчики
    app.add_handler(CallbackQueryHandler(button_handler, pattern="^(accept|decline)_"))
    app.add_handler(CallbackQueryHandler(twenty_one_callback, pattern="^21_"))
    
    print("🎮 MonGPT CASINO запущен!")
    print(f"👑 Создатель: @God_Mon1tyy")
    
    # Используем polling вместо webhook
    app.run_polling()

if __name__ == "__main__":
    # Простой HTTP-сервер для Render (чтобы видел открытый порт)
    class HealthCheck(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'MonGPT Bot is running!')
        
        def log_message(self, format, *args):
            pass  # Не логируем каждый запрос
    
    def run_health_server():
        try:
            server = HTTPServer(('0.0.0.0', PORT), HealthCheck)
            print(f"✅ Health server running on port {PORT}")
            server.serve_forever()
        except Exception as e:
            print(f"⚠️ Health server error: {e}")
            time.sleep(5)
            run_health_server()
    
    # Запускаем health-сервер в отдельном потоке
    health_thread = threading.Thread(target=run_health_server, daemon=True)
    health_thread.start()
    
    # Даём серверу время запуститься
    time.sleep(2)
    
    # Запускаем бота
    main()
