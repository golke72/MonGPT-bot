import sqlite3
import os
import random
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ===== ТВОИ ДАННЫЕ =====
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
PORT = int(os.environ.get('PORT', 10000))
BOT_USERNAME = "@MonGPT_bot"
# ========================

# ===== ТВОЙ ID =====
OWNER_ID = 7745009183
# ===================

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
                  joined_date TIMESTAMP)''')
    conn.commit()
    conn.close()

def get_user(user_id, username=None, first_name=None):
    if user_id == OWNER_ID:
        return 999999, 999, 0
    
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
    else:
        coins = user[3]
        wins = user[4]
        losses = user[5]
    
    conn.close()
    return coins, wins, losses

def update_user(user_id, coins=None, win=None, loss=None):
    conn = sqlite3.connect('mongpt.db')
    c = conn.cursor()
    if coins is not None:
        c.execute("UPDATE users SET coins = coins + ? WHERE id=?", (coins, user_id))
    if win:
        c.execute("UPDATE users SET wins = wins + 1 WHERE id=?", (user_id,))
    if loss:
        c.execute("UPDATE users SET losses = losses + 1 WHERE id=?", (user_id,))
    conn.commit()
    conn.close()

# ===== КОМАНДЫ =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    coins, wins, losses = get_user(user.id, user.username, user.first_name)
    
    text = (f"⚔️ **MonGPT** ⚔️\n\n"
            f"👤 Игрок: {user.first_name}\n"
            f"💰 Монет: {coins}\n"
            f"🏆 Побед: {wins}\n"
            f"💔 Поражений: {losses}\n\n"
            f"**ВСЕ КОМАНДЫ:**\n"
            f"/help - список всех команд")
    
    await update.message.reply_text(text)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (f"📋 **ВСЕ КОМАНДЫ**\n\n"
            f"**💰 ЭКОНОМИКА**\n"
            f"/balance - баланс\n"
            f"/top - топ богачей\n"
            f"/transfer @user [сумма] - перевод монет\n\n"
            f"**🎲 ОБЫЧНЫЕ ИГРЫ**\n"
            f"/dice [ставка] - 🎲 Кости\n"
            f"/darts [ставка] - 🎯 Дартс\n"
            f"/bowling [ставка] - 🎳 Боулинг\n"
            f"/soccer [ставка] - ⚽ Футбол\n"
            f"/basketball [ставка] - 🏀 Баскетбол\n\n"
            f"**🎰 КАЗИНО**\n"
            f"/slot [ставка] - 🎰 Слоты\n"
            f"/tower [ставка] - 🏰 Башня\n"
            f"/mines [ставка] - 💣 Мины\n\n"
            f"**⚔️ PVP**\n"
            f"/duel @user [ставка] - вызвать на дуэль\n"
            f"/bj @user [ставка] - BlackJack\n\n"
            f"**👑 АДМИН**\n"
            f"/give @user [сумма] - выдать монеты (только создатель)")
    
    await update.message.reply_text(text)

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    coins, _, _ = get_user(user.id)
    await update.message.reply_text(f"💰 **Баланс:** {coins} монет")

async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect('mongpt.db')
    c = conn.cursor()
    c.execute("SELECT username, first_name, coins FROM users ORDER BY coins DESC LIMIT 10")
    top_users = c.fetchall()
    conn.close()
    
    if not top_users:
        await update.message.reply_text("📊 Пока нет данных")
        return
    
    text = "🏆 **ТОП БОГАЧЕЙ** 🏆\n\n"
    medals = ["👑", "🥈", "🥉"]
    
    for i, (username, first_name, coins) in enumerate(top_users, 1):
        name = f"@{username}" if username else first_name or f"Игрок {i}"
        medal = medals[i-1] if i <= 3 else f"{i}."
        text += f"{medal} {name} — {coins} 🪙\n"
    
    await update.message.reply_text(text)

async def transfer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if len(context.args) < 2:
        await update.message.reply_text("❌ /transfer @user 50")
        return
    
    target = context.args[0]
    try:
        amount = int(context.args[1])
        if amount <= 0:
            raise ValueError
    except:
        await update.message.reply_text("❌ Неверная сумма")
        return
    
    coins, _, _ = get_user(user.id)
    if coins < amount:
        await update.message.reply_text(f"❌ У тебя только {coins} монет")
        return
    
    conn = sqlite3.connect('mongpt.db')
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE username=?", (target.replace('@', ''),))
    result = c.fetchone()
    conn.close()
    
    if not result:
        await update.message.reply_text("❌ Пользователь не найден")
        return
    
    target_id = result[0]
    update_user(user.id, coins=-amount)
    update_user(target_id, coins=amount)
    await update.message.reply_text(f"✅ Переведено {amount} монет {target}")

async def give(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if user.id != OWNER_ID:
        await update.message.reply_text("❌ Только для создателя")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("❌ /give @user 1000")
        return
    
    target = context.args[0]
    try:
        amount = int(context.args[1])
        if amount <= 0:
            raise ValueError
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
    
    target_id = result[0]
    update_user(target_id, coins=amount)
    await update.message.reply_text(f"✅ Выдано {amount} монет {target}")

# ===== ИГРЫ =====
async def play_game(update, context, emoji, game_name, win_threshold=4):
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
    
    coins, _, _ = get_user(user.id)
    if coins < bet:
        await update.message.reply_text(f"❌ У тебя только {coins} монет")
        return
    
    dice = await context.bot.send_dice(chat_id=update.message.chat_id, emoji=emoji)
    value = dice.dice.value
    
    win = value >= win_threshold
    
    if win:
        win_amount = bet * 2
        update_user(user.id, coins=win_amount - bet, win=True)
        await update.message.reply_text(f"{emoji} **ВЫИГРЫШ!** +{win_amount - bet} монет")
    else:
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

async def slot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not context.args:
        await update.message.reply_text("❌ /slot [ставка]")
        return
    
    try:
        bet = int(context.args[0])
        if bet <= 0:
            raise ValueError
    except:
        await update.message.reply_text("❌ Неверная ставка")
        return
    
    coins, _, _ = get_user(user.id)
    if coins < bet:
        await update.message.reply_text(f"❌ У тебя только {coins} монет")
        return
    
    symbols = ['🍒', '💎', '7️⃣', '👑']
    result = [random.choice(symbols) for _ in range(3)]
    
    multiplier = 1
    if result[0] == result[1] == result[2]:
        if result[0] == '👑':
            multiplier = 10
        elif result[0] == '7️⃣':
            multiplier = 5
        elif result[0] == '💎':
            multiplier = 3
        elif result[0] == '🍒':
            multiplier = 2
    
    win = bet * multiplier
    
    if multiplier > 1:
        update_user(user.id, coins=win - bet, win=True)
        await update.message.reply_text(f"🎰 {' | '.join(result)}\n🎉 **ВЫИГРЫШ!** +{win - bet} монет")
    else:
        update_user(user.id, coins=-bet, loss=True)
        await update.message.reply_text(f"🎰 {' | '.join(result)}\n💔 **ПРОИГРЫШ!** -{bet} монет")

async def tower(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not context.args:
        await update.message.reply_text("❌ /tower [ставка]")
        return
    
    try:
        bet = int(context.args[0])
        if bet <= 0:
            raise ValueError
    except:
        await update.message.reply_text("❌ Неверная ставка")
        return
    
    coins, _, _ = get_user(user.id)
    if coins < bet:
        await update.message.reply_text(f"❌ У тебя только {coins} монет")
        return
    
    floor = random.randint(1, 5)
    win = floor == 5
    
    if win:
        win_amount = bet * 5
        update_user(user.id, coins=win_amount - bet, win=True)
        await update.message.reply_text(f"🏰 **ТЫ ПОКОРИЛ БАШНЮ!** +{win_amount - bet} монет")
    else:
        update_user(user.id, coins=-bet, loss=True)
        await update.message.reply_text(f"🏰 **ТЫ УПАЛ С {floor} ЭТАЖА!** -{bet} монет")

async def mines(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not context.args:
        await update.message.reply_text("❌ /mines [ставка]")
        return
    
    try:
        bet = int(context.args[0])
        if bet <= 0:
            raise ValueError
    except:
        await update.message.reply_text("❌ Неверная ставка")
        return
    
    coins, _, _ = get_user(user.id)
    if coins < bet:
        await update.message.reply_text(f"❌ У тебя только {coins} монет")
        return
    
    mines_pos = random.sample(range(9), 3)
    pick = random.randint(0, 8)
    
    win = pick not in mines_pos
    
    if win:
        win_amount = bet * 2
        update_user(user.id, coins=win_amount - bet, win=True)
        await update.message.reply_text(f"💣 **ТЫ НЕ ПОДОРВАЛСЯ!** +{win_amount - bet} монет")
    else:
        update_user(user.id, coins=-bet, loss=True)
        await update.message.reply_text(f"💥 **ТЫ ПОДОРВАЛСЯ!** -{bet} монет")

async def duel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if len(context.args) < 2:
        await update.message.reply_text("❌ /duel @user 50")
        return
    
    target = context.args[0]
    try:
        bet = int(context.args[1])
        if bet <= 0:
            raise ValueError
    except:
        await update.message.reply_text("❌ Неверная ставка")
        return
    
    coins, _, _ = get_user(user.id)
    if coins < bet:
        await update.message.reply_text(f"❌ У тебя только {coins} монет")
        return
    
    conn = sqlite3.connect('mongpt.db')
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE username=?", (target.replace('@', ''),))
    result = c.fetchone()
    conn.close()
    
    if not result:
        await update.message.reply_text("❌ Пользователь не найден")
        return
    
    target_id = result[0]
    target_coins, _, _ = get_user(target_id)
    
    if target_coins < bet:
        await update.message.reply_text(f"❌ У {target} только {target_coins} монет")
        return
    
    user_dice = await context.bot.send_dice(chat_id=update.message.chat_id)
    target_dice = await context.bot.send_dice(chat_id=update.message.chat_id)
    
    user_val = user_dice.dice.value
    target_val = target_dice.dice.value
    
    if user_val > target_val:
        update_user(user.id, coins=bet, win=True)
        update_user(target_id, coins=-bet, loss=True)
        await update.message.reply_text(f"⚔️ **ТЫ ВЫИГРАЛ!** +{bet} монет")
    elif target_val > user_val:
        update_user(user.id, coins=-bet, loss=True)
        update_user(target_id, coins=bet, win=True)
        await update.message.reply_text(f"⚔️ **ТЫ ПРОИГРАЛ!** -{bet} монет")
    else:
        await update.message.reply_text(f"⚔️ **НИЧЬЯ!** Ставка возвращена")

async def bj(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if len(context.args) < 2:
        await update.message.reply_text("❌ /bj @user 50")
        return
    
    target = context.args[0]
    try:
        bet = int(context.args[1])
        if bet <= 0:
            raise ValueError
    except:
        await update.message.reply_text("❌ Неверная ставка")
        return
    
    coins, _, _ = get_user(user.id)
    if coins < bet:
        await update.message.reply_text(f"❌ У тебя только {coins} монет")
        return
    
    conn = sqlite3.connect('mongpt.db')
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE username=?", (target.replace('@', ''),))
    result = c.fetchone()
    conn.close()
    
    if not result:
        await update.message.reply_text("❌ Пользователь не найден")
        return
    
    target_id = result[0]
    target_coins, _, _ = get_user(target_id)
    
    if target_coins < bet:
        await update.message.reply_text(f"❌ У {target} только {target_coins} монет")
        return
    
    user_cards = [random.randint(1, 11), random.randint(1, 11)]
    target_cards = [random.randint(1, 11), random.randint(1, 11)]
    
    user_sum = sum(user_cards)
    target_sum = sum(target_cards)
    
    user_diff = abs(21 - user_sum)
    target_diff = abs(21 - target_sum)
    
    if user_diff < target_diff:
        update_user(user.id, coins=bet, win=True)
        update_user(target_id, coins=-bet, loss=True)
        await update.message.reply_text(f"🃏 **ТЫ ВЫИГРАЛ!** +{bet} монет\nТвои карты: {user_sum}")
    elif target_diff < user_diff:
        update_user(user.id, coins=-bet, loss=True)
        update_user(target_id, coins=bet, win=True)
        await update.message.reply_text(f"🃏 **ТЫ ПРОИГРАЛ!** -{bet} монет\nТвои карты: {user_sum}")
    else:
        await update.message.reply_text(f"🃏 **НИЧЬЯ!** Ставка возвращена\nТвои карты: {user_sum}")

# ===== ЗАПУСК =====
def main():
    init_db()
    
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Основные
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("top", top))
    app.add_handler(CommandHandler("transfer", transfer))
    app.add_handler(CommandHandler("give", give))
    
    # Игры
    app.add_handler(CommandHandler("dice", dice))
    app.add_handler(CommandHandler("darts", darts))
    app.add_handler(CommandHandler("bowling", bowling))
    app.add_handler(CommandHandler("soccer", soccer))
    app.add_handler(CommandHandler("basketball", basketball))
    app.add_handler(CommandHandler("slot", slot))
    app.add_handler(CommandHandler("tower", tower))
    app.add_handler(CommandHandler("mines", mines))
    
    # PVP
    app.add_handler(CommandHandler("duel", duel))
    app.add_handler(CommandHandler("bj", bj))
    
    print("⚔️ MonGPT запущен!")
    print(f"👑 Создатель: @God_Mon1tyy")
    
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TELEGRAM_TOKEN,
        webhook_url=f"https://mongpt-bot.onrender.com/{TELEGRAM_TOKEN}"
    )

if __name__ == "__main__":
    main()
