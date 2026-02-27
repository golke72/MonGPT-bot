import sqlite3
import os
import random
import re
from datetime import datetime
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
active_games = {}  # {game_id: game_data}

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
    if user_id == OWNER_ID:
        return 999999, 999, 0, 0, True, "👑"
    
    conn = sqlite3.connect('mongpt.db')
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
        bj_wins = 0
        vip = False
    else:
        coins = user[3]
        wins = user[4]
        losses = user[5]
        bj_wins = user[6] if len(user) > 6 else 0
        vip = user[7] if len(user) > 7 else False
    
    conn.close()
    return coins, wins, losses, bj_wins, vip, user[2] or "Игрок"

def update_user(user_id, coins=None, win=None, loss=None, bj_win=None, vip=None):
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

# ===== ФУНКЦИИ ДЛЯ ИГР =====
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
    """Обрабатывает все текстовые команды"""
    text = update.message.text.lower().strip()
    user = update.effective_user
    
    # Проверяем, ответил ли на сообщение (для дуэлей)
    replied = update.message.reply_to_message
    opponent = replied.from_user if replied else None
    
    # Баланс
    if text == 'б':
        coins, _, _, _, _, name = get_user(user.id)
        await update.message.reply_text(f"💰 **{name}, твой баланс:** {coins} монет")
        return
    
    # Топ
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
    
    # Перевод монет
    if text.startswith('дать '):
        parts = text.split()
        if len(parts) != 2 or not replied:
            await update.message.reply_text("❌ Ответь на сообщение друга и напиши: дать 100")
            return
        
        try:
            amount = int(parts[1])
            if amount <= 0:
                raise ValueError
        except:
            await update.message.reply_text("❌ Неверная сумма")
            return
        
        # Проверяем баланс
        coins, _, _, _, _, _ = get_user(user.id)
        if coins < amount:
            await update.message.reply_text(f"❌ У тебя только {coins} монет")
            return
        
        opponent_id = opponent.id
        
        # Переводим
        update_user(user.id, coins=-amount)
        update_user(opponent_id, coins=amount)
        
        await update.message.reply_text(f"✅ Переведено {amount} монет {opponent.first_name}")
        
        # Уведомление
        try:
            await context.bot.send_message(
                opponent_id,
                f"💰 **ПЕРЕВОД!**\n\n{user.first_name} перевёл тебе {amount} монет!"
            )
        except:
            pass
        return
    
    # ДУЭЛИ (только по ответу)
    duel_games = ['кости', 'дартс', 'боулинг', 'футбол', 'баскет', '21']
    
    for game in duel_games:
        if text.startswith(game):
            if not replied:
                await update.message.reply_text(f"❌ Ответь на сообщение друга, чтобы сыграть в {game}!")
                return
            
            if opponent.id == user.id:
                await update.message.reply_text("❌ Нельзя играть с самим собой!")
                return
            
            if opponent.is_bot:
                await update.message.reply_text("❌ С ботами не играем!")
                return
            
            parts = text.split()
            if len(parts) != 2:
                await update.message.reply_text(f"❌ {game} [ставка]\nПример: {game} 50")
                return
            
            try:
                bet = int(parts[1])
                if bet <= 0:
                    raise ValueError
            except:
                await update.message.reply_text("❌ Неверная ставка")
                return
            
            # Проверяем балансы
            user_coins, _, _, _, user_vip, _ = get_user(user.id)
            opp_coins, _, _, _, opp_vip, opp_name = get_user(opponent.id)
            
            if not user_vip and user_coins < bet:
                await update.message.reply_text(f"❌ У тебя только {user_coins} монет")
                return
            
            if not opp_vip and opp_coins < bet:
                await update.message.reply_text(f"❌ У {opp_name} только {opp_coins} монет")
                return
            
            # Запускаем нужную игру
            if game == '21':
                await start_21(update, context, user, opponent, bet)
            else:
                await start_duel(update, context, user, opponent, bet, game)
            return
    
    # Если ничего не подошло
    await update.message.reply_text(
        "❓ Неизвестная команда. Напиши /help для списка команд."
    )

# ===== ДУЭЛИ =====
async def start_duel(update, context, user, opponent, bet, game_type):
    """Запускает дуэль в обычные игры"""
    game_id = f"duel_{user.id}_{opponent.id}_{datetime.now().timestamp()}"
    
    # Словарь для эмодзи
    emojis = {
        'кости': '🎲',
        'дартс': '🎯',
        'боулинг': '🎳',
        'футбол': '⚽',
        'баскет': '🏀'
    }
    emoji = emojis.get(game_type, '🎲')
    
    # Бросаем кости
    user_dice = await context.bot.send_dice(chat_id=update.message.chat_id, emoji=emoji)
    opp_dice = await context.bot.send_dice(chat_id=update.message.chat_id, emoji=emoji)
    
    user_val = user_dice.dice.value
    opp_val = opp_dice.dice.value
    
    user_coins, _, _, _, user_vip, _ = get_user(user.id)
    opp_coins, _, _, _, opp_vip, opp_name = get_user(opponent.id)
    
    result_text = ""
    
    if user_val > opp_val:
        if not user_vip:
            update_user(user.id, coins=bet, win=True)
        if not opp_vip:
            update_user(opponent.id, coins=-bet, loss=True)
        result_text = f"🎉 **ТЫ ВЫИГРАЛ!** +{bet} монет"
    elif opp_val > user_val:
        if not user_vip:
            update_user(user.id, coins=-bet, loss=True)
        if not opp_vip:
            update_user(opponent.id, coins=bet, win=True)
        result_text = f"💔 **ТЫ ПРОИГРАЛ!** -{bet} монет"
    else:
        result_text = f"🤝 **НИЧЬЯ!** Ставка возвращена"
    
    await update.message.reply_text(
        f"{emoji} **ДУЭЛЬ**\n\n"
        f"👤 Ты: {user_val}\n"
        f"👤 {opponent.first_name}: {opp_val}\n"
        f"💰 Ставка: {bet}\n\n"
        f"{result_text}"
    )

# ===== 21 (БЛЭКДЖЕК) =====
async def start_21(update, context, user, opponent, bet):
    """Запускает игру в 21"""
    game_id = f"21_{user.id}_{opponent.id}_{datetime.now().timestamp()}"
    
    deck = create_deck()
    player_hand = [deck.pop(), deck.pop()]
    opponent_hand = [deck.pop(), deck.pop()]
    
    active_games[game_id] = {
        'user1': user.id,
        'user2': opponent.id,
        'bet': bet,
        'hand1': player_hand,
        'hand2': opponent_hand,
        'deck': deck,
        'turn': user.id,
        'stood1': False,
        'stood2': False
    }
    
    game = active_games[game_id]
    
    keyboard = [[
        InlineKeyboardButton("🃏 Взять", callback_data=f"21_hit_{game_id}"),
        InlineKeyboardButton("⏹️ Хватит", callback_data=f"21_stand_{game_id}")
    ]]
    
    p1_hand = hand_to_string(game['hand1'])
    p1_score = calculate_hand(game['hand1'])
    p2_display = hand_to_string([game['hand2'][0], '🂠'])
    
    await update.message.reply_text(
        f"🃏 **21 (БЛЭКДЖЕК)**\n\n"
        f"💰 Ставка: {bet}\n\n"
        f"👤 **Ты**:\n"
        f"Карты: {p1_hand}\n"
        f"Очки: {p1_score}\n\n"
        f"👤 **{opponent.first_name}**:\n"
        f"Карты: {p2_display}\n\n"
        f"🎮 Твой ход",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def twenty_one_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопок для 21"""
    query = update.callback_query
    await query.answer()
    
    data = query.data.split('_')
    action = data[1]
    game_id = '_'.join(data[2:])
    
    if game_id not in active_games:
        await query.edit_message_text("❌ Игра уже закончена!")
        return
    
    game = active_games[game_id]
    user_id = query.from_user.id
    
    if user_id not in [game['user1'], game['user2']]:
        await query.answer("Это не твоя игра!", show_alert=True)
        return
    
    if game['turn'] != user_id:
        await query.answer("Сейчас не твой ход!", show_alert=True)
        return
    
    user1_coins, _, _, _, user1_vip, user1_name = get_user(game['user1'])
    user2_coins, _, _, _, user2_vip, user2_name = get_user(game['user2'])
    
    if action == 'hit':
        # Берём карту
        new_card = game['deck'].pop()
        
        if user_id == game['user1']:
            game['hand1'].append(new_card)
            score = calculate_hand(game['hand1'])
            
            if score > 21:
                # Перебор
                if not user1_vip:
                    update_user(game['user1'], coins=-game['bet'], loss=True)
                if not user2_vip:
                    update_user(game['user2'], coins=game['bet'], win=True, bj_win=True)
                
                p1_hand = hand_to_string(game['hand1'])
                p2_hand = hand_to_string(game['hand2'])
                
                await query.edit_message_text(
                    f"🃏 **ИГРА ЗАВЕРШЕНА**\n\n"
                    f"💰 Ставка: {game['bet']}\n\n"
                    f"👤 **Ты**:\n"
                    f"Карты: {p1_hand}\n"
                    f"Очки: {score}\n\n"
                    f"👤 **{user2_name}**:\n"
                    f"Карты: {p2_hand}\n"
                    f"Очки: {calculate_hand(game['hand2'])}\n\n"
                    f"💔 **ТЫ ПРОИГРАЛ!** Перебор!"
                )
                del active_games[game_id]
                return
            else:
                game['turn'] = game['user2']
        else:
            game['hand2'].append(new_card)
            score = calculate_hand(game['hand2'])
            
            if score > 21:
                # Перебор
                if not user2_vip:
                    update_user(game['user2'], coins=-game['bet'], loss=True)
                if not user1_vip:
                    update_user(game['user1'], coins=game['bet'], win=True, bj_win=True)
                
                p1_hand = hand_to_string(game['hand1'])
                p2_hand = hand_to_string(game['hand2'])
                
                await query.edit_message_text(
                    f"🃏 **ИГРА ЗАВЕРШЕНА**\n\n"
                    f"💰 Ставка: {game['bet']}\n\n"
                    f"👤 **{user1_name}**:\n"
                    f"Карты: {p1_hand}\n"
                    f"Очки: {calculate_hand(game['hand1'])}\n\n"
                    f"👤 **Ты**:\n"
                    f"Карты: {p2_hand}\n"
                    f"Очки: {score}\n\n"
                    f"💔 **ПРОТИВНИК ПЕРЕБРАЛ! ТЫ ВЫИГРАЛ!**"
                )
                del active_games[game_id]
                return
            else:
                game['turn'] = game['user1']
        
        # Обновляем отображение
        p1_hand = hand_to_string(game['hand1'])
        p2_hand = hand_to_string(game['hand2'])
        p1_score = calculate_hand(game['hand1'])
        
        if game['turn'] == game['user1']:
            p2_display = hand_to_string([game['hand2'][0], '🂠'])
            p2_score = "?"
            turn_text = "Твой ход"
        else:
            p2_display = hand_to_string(game['hand2'])
            p2_score = calculate_hand(game['hand2'])
            turn_text = f"Ход {user2_name}"
        
        keyboard = [[
            InlineKeyboardButton("🃏 Взять", callback_data=f"21_hit_{game_id}"),
            InlineKeyboardButton("⏹️ Хватит", callback_data=f"21_stand_{game_id}")
        ]]
        
        await query.edit_message_text(
            f"🃏 **21 (БЛЭКДЖЕК)**\n\n"
            f"💰 Ставка: {game['bet']}\n\n"
            f"👤 **Ты**:\n"
            f"Карты: {p1_hand}\n"
            f"Очки: {p1_score}\n\n"
            f"👤 **{user2_name}**:\n"
            f"Карты: {p2_display}\n"
            f"Очки: {p2_score}\n\n"
            f"🎮 {turn_text}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif action == 'stand':
        # Пас
        if user_id == game['user1']:
            game['stood1'] = True
            game['turn'] = game['user2']
        else:
            game['stood2'] = True
            game['turn'] = game['user1']
        
        # Проверяем, не закончилась ли игра
        if game['stood1'] and game['stood2']:
            # Оба пасанули
            p1_score = calculate_hand(game['hand1'])
            p2_score = calculate_hand(game['hand2'])
            
            p1_hand = hand_to_string(game['hand1'])
            p2_hand = hand_to_string(game['hand2'])
            
            result_text = ""
            
            if p1_score > p2_score:
                if not user1_vip:
                    update_user(game['user1'], coins=game['bet'], win=True, bj_win=True)
                if not user2_vip:
                    update_user(game['user2'], coins=-game['bet'], loss=True)
                result_text = f"🎉 **ТЫ ВЫИГРАЛ!** {p1_score} > {p2_score}"
            elif p2_score > p1_score:
                if not user1_vip:
                    update_user(game['user1'], coins=-game['bet'], loss=True)
                if not user2_vip:
                    update_user(game['user2'], coins=game['bet'], win=True, bj_win=True)
                result_text = f"💔 **ТЫ ПРОИГРАЛ!** {p1_score} < {p2_score}"
            else:
                result_text = f"🤝 **НИЧЬЯ!** {p1_score} = {p2_score}"
            
            await query.edit_message_text(
                f"🃏 **ИГРА ЗАВЕРШЕНА**\n\n"
                f"💰 Ставка: {game['bet']}\n\n"
                f"👤 **Ты**:\n"
                f"Карты: {p1_hand}\n"
                f"Очки: {p1_score}\n\n"
                f"👤 **{user2_name}**:\n"
                f"Карты: {p2_hand}\n"
                f"Очки: {p2_score}\n\n"
                f"{result_text}"
            )
            del active_games[game_id]
        else:
            # Продолжаем
            p1_hand = hand_to_string(game['hand1'])
            p2_hand = hand_to_string(game['hand2'])
            p1_score = calculate_hand(game['hand1'])
            
            if game['turn'] == game['user1']:
                p2_display = hand_to_string([game['hand2'][0], '🂠'])
                p2_score = "?"
                turn_text = "Твой ход"
            else:
                p2_display = hand_to_string(game['hand2'])
                p2_score = calculate_hand(game['hand2'])
                turn_text = f"Ход {user2_name}"
            
            keyboard = [[
                InlineKeyboardButton("🃏 Взять", callback_data=f"21_hit_{game_id}"),
                InlineKeyboardButton("⏹️ Хватит", callback_data=f"21_stand_{game_id}")
            ]]
            
            await query.edit_message_text(
                f"🃏 **21 (БЛЭКДЖЕК)**\n\n"
                f"💰 Ставка: {game['bet']}\n\n"
                f"👤 **Ты**:\n"
                f"Карты: {p1_hand}\n"
                f"Очки: {p1_score}\n\n"
                f"👤 **{user2_name}**:\n"
                f"Карты: {p2_display}\n"
                f"Очки: {p2_score}\n\n"
                f"🎮 {turn_text}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

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
        f"дать 100 - перевести монеты (ответь на сообщение)\n"
        f"кости 50 - дуэль в кости (ответь)\n"
        f"дартс 50 - дуэль в дартс (ответь)\n"
        f"боулинг 50 - дуэль в боулинг (ответь)\n"
        f"футбол 50 - дуэль в футбол (ответь)\n"
        f"баскет 50 - дуэль в баскетбол (ответь)\n"
        f"21 50 - Блэкджек (ответь)\n\n"
        f"**АДМИН-КОМАНДЫ:**\n"
        f"/admin - панель управления"
    )
    
    await update.message.reply_text(text)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if user.id != OWNER_ID:
        await update.message.reply_text("❌ Только для создателя!")
        return
    
    text = (
        "👑 **АДМИН-ПАНЕЛЬ**\n\n"
        "**📊 СТАТИСТИКА**\n"
        "/admin_stats - статистика\n"
        "/admin_top [coins/wins/bj] - топ\n\n"
        "**💰 УПРАВЛЕНИЕ БАЛАНСОМ**\n"
        "/admin_give @user 1000 - выдать\n"
        "/admin_take @user 500 - снять\n"
        "/admin_set @user 9999 - установить\n\n"
        "**👤 УПРАВЛЕНИЕ**\n"
        "/admin_info @user - информация\n"
        "/admin_vip @user - сделать VIP"
    )
    
    await update.message.reply_text(text)

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    
    conn = sqlite3.connect('mongpt.db')
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) FROM users")
    total = c.fetchone()[0]
    
    c.execute("SELECT SUM(coins) FROM users")
    total_coins = c.fetchone()[0] or 0
    
    c.execute("SELECT SUM(wins) FROM users")
    total_wins = c.fetchone()[0] or 0
    
    c.execute("SELECT SUM(losses) FROM users")
    total_losses = c.fetchone()[0] or 0
    
    c.execute("SELECT COUNT(*) FROM users WHERE vip = 1")
    total_vip = c.fetchone()[0] or 0
    
    conn.close()
    
    await update.message.reply_text(
        f"📊 **СТАТИСТИКА**\n\n"
        f"👥 Всего: {total}\n"
        f"👑 VIP: {total_vip}\n"
        f"💰 Монет: {total_coins}\n"
        f"🏆 Побед: {total_wins}\n"
        f"💔 Поражений: {total_losses}"
    )

async def admin_give(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("❌ /admin_give @user 1000")
        return
    
    target = context.args[0]
    try:
        amount = int(context.args[1])
    except:
        await update.message.reply_text("❌ Неверная сумма")
        return
    
    conn = sqlite3.connect('mongpt.db')
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE username=?", (target.replace('@', ''),))
    result = c.fetchone()
    conn.close()
    
    if not result:
        await update.message.reply_text("❌ Пользователь не найден")
        return
    
    update_user(result[0], coins=amount)
    await update.message.reply_text(f"✅ Выдано {amount} монет {target}")

async def admin_vip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    
    if not context.args:
        await update.message.reply_text("❌ /admin_vip @user")
        return
    
    target = context.args[0]
    
    conn = sqlite3.connect('mongpt.db')
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE username=?", (target.replace('@', ''),))
    result = c.fetchone()
    conn.close()
    
    if not result:
        await update.message.reply_text("❌ Пользователь не найден")
        return
    
    update_user(result[0], vip=True)
    await update.message.reply_text(f"✅ {target} теперь VIP!")

# ===== ЗАПУСК =====
def main():
    init_db()
    
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Основные команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CommandHandler("admin_stats", admin_stats))
    app.add_handler(CommandHandler("admin_give", admin_give))
    app.add_handler(CommandHandler("admin_vip", admin_vip))
    
    # Обработчик текстовых команд
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Callback для 21
    app.add_handler(CallbackQueryHandler(twenty_one_callback, pattern="^21_"))
    
    print("🎮 MonGPT CASINO запущен!")
    print(f"👑 Создатель: @God_Mon1tyy")
    
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TELEGRAM_TOKEN,
        webhook_url=f"https://mongpt-bot.onrender.com/{TELEGRAM_TOKEN}"
    )

if __name__ == "__main__":
    main()
