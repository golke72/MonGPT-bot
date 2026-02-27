"""
MonGPT ULTIMATE PRO MAX - Версия с распознаванием всего и голосовыми ответами!
Создатель: @God_Mon1tyy
Бот: @MonGPT_bot
Статус: 👑 БЕСКОНЕЧНЫЕ ТОКЕНЫ ДЛЯ СОЗДАТЕЛЯ

Функции:
✅ Текст
✅ Голосовые сообщения (распознаёт)
✅ Видео и кружки (распознаёт)
✅ YouTube / Instagram / TikTok ссылки
✅ Генерация голосовых ответов по команде /voice
✅ Управление матом
✅ Кнопки и команды
✅ Твой особый статус
"""

import requests
import sqlite3
import os
import re
import json
import random
import io
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
from telegram.constants import ParseMode
from gtts import gTTS

# ===== ТВОИ ДАННЫЕ =====
TELEGRAM_TOKEN = "8735549741:AAFt4ydTV5BFGhVv_iKKJbO3TxfefbIpEc0"
POE_API_KEY = "PKkByuEiScElrfyx7VGeztMX6xoDQv_O5p8G3Bwio_M"
PORT = int(os.environ.get('PORT', 10000))
BOT_USERNAME = "@MonGPT_bot"
# ========================

# ===== ОСОБЫЙ СТАТУС СОЗДАТЕЛЯ =====
CREATOR_ID = 7745009183
CREATOR_NAME = "@God_Mon1tyy"
CREATOR_TITLE = "👑 СОЗДАТЕЛЬ MonGPT"
# ====================================

# ===== НАСТРОЙКИ =====
DEFAULT_MODEL = "MonGPT"
MODELS = {
    "claude": "Claude-3.5-Sonnet",
    "gpt4": "GPT-4o",
    "gemini": "Gemini-1.5-Pro",
    "mon": "MonGPT"
}

# Список плохих слов
BAD_WORDS = ["хуй", "пизда", "блядь", "сука", "ебать", "пиздец", "нахер", "залупа"]
MAT_FILTER = True  # По умолчанию включен
# ======================

# ===== БАЗА ДАННЫХ =====
def init_db():
    conn = sqlite3.connect('mongpt.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY, 
                  tokens INTEGER DEFAULT 50,
                  username TEXT, 
                  first_name TEXT,
                  model TEXT DEFAULT 'MonGPT',
                  mat_filter BOOLEAN DEFAULT 1,
                  vip BOOLEAN DEFAULT 0,
                  messages_count INTEGER DEFAULT 0,
                  joined_date TEXT)''')
    conn.commit()
    conn.close()

def get_user(user_id, username=None, first_name=None):
    # ЕСЛИ ЭТО СОЗДАТЕЛЬ - БЕСКОНЕЧНЫЕ ТОКЕНЫ!
    if user_id == CREATOR_ID:
        return "∞", DEFAULT_MODEL, True, True, 0  # ∞ - бесконечность
    
    conn = sqlite3.connect('mongpt.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id=?", (user_id,))
    user = c.fetchone()
    
    if not user:
        c.execute("""INSERT INTO users 
                     (id, username, first_name, tokens, joined_date) 
                     VALUES (?,?,?,?,?)""",
                  (user_id, username, first_name, 50, datetime.now().isoformat()))
        conn.commit()
        tokens = 50
        vip = False
    else:
        tokens = user[1]
        vip = bool(user[6]) if len(user) > 6 else False
    
    conn.close()
    return tokens, DEFAULT_MODEL, True, vip, 0

def update_tokens(user_id, amount):
    if user_id == CREATOR_ID:
        return
    
    conn = sqlite3.connect('mongpt.db')
    c = conn.cursor()
    c.execute("UPDATE users SET tokens = tokens + ? WHERE id=?", (amount, user_id))
    conn.commit()
    conn.close()

def use_token(user_id):
    if user_id == CREATOR_ID:
        return 0
    
    conn = sqlite3.connect('mongpt.db')
    c = conn.cursor()
    c.execute("UPDATE users SET tokens = tokens - 1, messages_count = messages_count + 1 WHERE id=?", (user_id,))
    conn.commit()
    conn.close()
    return 0

def set_mat_filter(user_id, value):
    conn = sqlite3.connect('mongpt.db')
    c = conn.cursor()
    c.execute("UPDATE users SET mat_filter=? WHERE id=?", (1 if value else 0, user_id))
    conn.commit()
    conn.close()

def set_vip(user_id, value):
    conn = sqlite3.connect('mongpt.db')
    c = conn.cursor()
    c.execute("UPDATE users SET vip=? WHERE id=?", (1 if value else 0, user_id))
    conn.commit()
    conn.close()

# ===== ФУНКЦИЯ ЦЕНЗУРЫ =====
def censor_text(text):
    if not MAT_FILTER:
        return text
    
    censored = text
    for word in BAD_WORDS:
        censored = censored.replace(word, "*" * len(word))
        censored = censored.replace(word.upper(), "*" * len(word))
        censored = censored.replace(word.capitalize(), "*" * len(word))
    return censored

# ===== ФУНКЦИЯ: РАСПОЗНАВАНИЕ ССЫЛОК =====
def extract_links(text):
    url_pattern = r'https?://[^\s]+|[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:/[^\s]*)?'
    return re.findall(url_pattern, text)

def get_link_info(url):
    try:
        if 'youtube.com' in url or 'youtu.be' in url:
            return analyze_youtube(url)
        elif 'instagram.com' in url:
            return analyze_instagram(url)
        elif 'tiktok.com' in url:
            return analyze_tiktok(url)
        else:
            response = requests.head(url, timeout=5, allow_redirects=True)
            return {
                'type': 'link',
                'url': url,
                'status': response.status_code,
                'working': response.status_code < 400
            }
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
                    'video_id': video_id,
                    'url': url
                }
    except:
        pass
    return {'type': 'youtube', 'url': url, 'error': 'Не удалось получить информацию'}

def analyze_instagram(url):
    return {'type': 'instagram', 'url': url}

def analyze_tiktok(url):
    return {'type': 'tiktok', 'url': url}

# ===== ФУНКЦИЯ РАСПОЗНАВАНИЯ ГОЛОСА =====
async def recognize_speech(voice_file):
    try:
        import speech_recognition as sr
        from pydub import AudioSegment
        
        file_path = f"voice_{random.randint(1000,9999)}.ogg"
        await voice_file.download_to_drive(file_path)
        
        audio = AudioSegment.from_ogg(file_path)
        wav_path = file_path.replace('.ogg', '.wav')
        audio.export(wav_path, format="wav")
        
        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)
            text = recognizer.recognize_google(audio_data, language="ru-RU")
        
        os.remove(file_path)
        os.remove(wav_path)
        return text
    except Exception as e:
        print(f"Ошибка распознавания: {e}")
        return None

# ===== ФУНКЦИЯ РАСПОЗНАВАНИЯ ВИДЕО =====
async def extract_audio_from_video(video_file):
    try:
        import speech_recognition as sr
        from pydub import AudioSegment
        import subprocess
        
        video_path = f"video_{random.randint(1000,9999)}.mp4"
        await video_file.download_to_drive(video_path)
        
        audio_path = video_path.replace('.mp4', '.wav')
        subprocess.run(['ffmpeg', '-i', video_path, '-vn', '-acodec', 'pcm_s16le', '-ar', '44100', '-ac', '2', audio_path], 
                      capture_output=True)
        
        recognizer = sr.Recognizer()
        with sr.AudioFile(audio_path) as source:
            audio_data = recognizer.record(source)
            text = recognizer.recognize_google(audio_data, language="ru-RU")
        
        os.remove(video_path)
        os.remove(audio_path)
        return text
    except Exception as e:
        print(f"Ошибка распознавания видео: {e}")
        return None

# ===== НОВАЯ ФУНКЦИЯ: ГЕНЕРАЦИЯ ГОЛОСОВЫХ ОТВЕТОВ =====
async def voice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет голосовое сообщение с текстом пользователя"""
    user = update.effective_user
    
    if not context.args:
        await update.message.reply_text(
            "❌ Напиши текст для озвучки.\n"
            "Пример: `/voice Привет, как дела?`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    text = ' '.join(context.args)
    await update.message.reply_text("🔊 Генерирую голосовое...")
    
    try:
        # Создаём аудио с помощью gTTS
        tts = gTTS(text=text, lang='ru', slow=False)
        
        # Сохраняем в память
        audio_bytes = io.BytesIO()
        tts.write_to_fp(audio_bytes)
        audio_bytes.seek(0)
        
        # Проверяем, создатель ли это
        is_creator = (user.id == CREATOR_ID)
        creator_note = " 👑" if is_creator else ""
        
        # Отправляем как голосовое
        await update.message.reply_voice(
            voice=InputFile(audio_bytes, filename="voice.ogg"),
            caption=f"🗣️ Голосовое сообщение{creator_note}"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)[:100]}")

# ===== КОМАНДЫ БОТА =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    if user_id == CREATOR_ID:
        await update.message.reply_text(
            f"👑 **С ВОЗВРАЩЕНИЕМ, СОЗДАТЕЛЬ {CREATOR_NAME}!** 👑\n\n"
            f"✨ **Твой особый статус активирован:**\n"
            f"• ∞ Бесконечные токены\n"
            f"• 👑 Отметка во всех чатах\n"
            f"• 🎥 Распознавание видео\n"
            f"• 🎤 Распознавание голоса\n"
            f"• 🔗 Анализ ссылок\n"
            f"• 🔊 Генерация голосовых (/voice)\n\n"
            f"Чего желаешь, повелитель?",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    tokens, _, _, vip, _ = get_user(user_id, user.username, user.first_name)
    vip_status = "👑 VIP" if vip else "👤 Обычный"
    
    keyboard = [
        [InlineKeyboardButton("💰 Баланс", callback_data="balance"),
         InlineKeyboardButton("🎮 Управление", callback_data="controls")],
        [InlineKeyboardButton("❓ Помощь", callback_data="help")]
    ]
    
    await update.message.reply_text(
        f"🤙 **Йоу, {user.first_name}!**\n\n"
        f"Добро пожаловать в **MonGPT ULTIMATE**!\n"
        f"🔥 Я умею:\n"
        f"• 🎤 Распознавать голосовые\n"
        f"• 📹 Распознавать видео и кружки\n"
        f"• 🔗 Анализировать ссылки\n"
        f"• 🔊 Генерировать голос (/voice)\n"
        f"• 💬 Отвечать на текст\n\n"
        f"💰 Твой баланс: {tokens} токенов\n"
        f"👑 Статус: {vip_status}\n\n"
        f"👤 Создатель: {CREATOR_NAME}",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )

async def mat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    _, _, mat_filter, vip, _ = get_user(user.id)
    
    if not context.args:
        status = "включен 🔰" if mat_filter else "выключен 🔞"
        await update.message.reply_text(
            f"🔰 **Управление фильтром мата**\n\n"
            f"Текущий статус: **{status}**\n\n"
            f"Команды:\n"
            f"/mat on - включить фильтр\n"
            f"/mat off - выключить фильтр",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    if context.args[0] == "on":
        set_mat_filter(user.id, True)
        await update.message.reply_text("🔰 **Фильтр мата включен!**")
    elif context.args[0] == "off":
        set_mat_filter(user.id, False)
        await update.message.reply_text("🔞 **Фильтр мата выключен!**")

async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    tokens, _, _, vip, _ = get_user(user.id, user.username, user.first_name)
    await update.message.reply_text(f"💰 Твой баланс: {tokens} токенов")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "balance":
        tokens, _, _, vip, _ = get_user(query.from_user.id)
        await query.edit_message_text(f"💰 Баланс: {tokens} токенов")
    elif query.data == "controls":
        await query.edit_message_text(
            "🎮 **Управление:**\n\n"
            "/mat - управление матом\n"
            "/balance - баланс\n"
            "/voice текст - голосовое сообщение\n\n"
            "Отправляй голосовые, видео, ссылки!"
        )
    elif query.data == "help":
        await query.edit_message_text(
            f"❓ **Помощь**\n\n"
            f"Я понимаю:\n"
            f"🎤 Голосовые сообщения\n"
            f"📹 Кружки\n"
            f"🎥 Видеофайлы\n"
            f"🔗 Ссылки (YouTube, TikTok, Instagram)\n"
            f"💬 Текст\n\n"
            f"🔊 **Новая команда:** /voice текст\n\n"
            f"👑 Создатель: {CREATOR_NAME}\n"
            f"📱 Бот: {BOT_USERNAME}"
        )

# ===== ОСНОВНОЙ ОБРАБОТЧИК =====
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    is_creator = (user_id == CREATOR_ID)
    
    tokens, model, mat_filter, vip, msgs = get_user(user_id, user.username, user.first_name)
    
    user_input = ""
    input_type = "text"
    
    # 1. Текстовое сообщение
    if update.message.text:
        user_input = update.message.text
        
        links = extract_links(user_input)
        if links:
            link_info = []
            for link in links:
                info = get_link_info(link)
                if info:
                    if info.get('type') == 'youtube':
                        link_info.append(f"📺 YouTube: {info.get('title', 'видео')}")
                    elif info.get('type') == 'instagram':
                        link_info.append(f"📸 Instagram: {info.get('url', 'пост')}")
                    elif info.get('type') == 'tiktok':
                        link_info.append(f"🎵 TikTok: {info.get('url', 'видео')}")
                    else:
                        link_info.append(f"🔗 Ссылка: {info.get('url', '')}")
            
            if link_info:
                user_input += "\n\n[ССЫЛКИ В СООБЩЕНИИ]:\n" + "\n".join(link_info)
    
    # 2. Голосовое сообщение
    elif update.message.voice:
        input_type = "voice"
        await update.message.reply_text("🎤 Распознаю голосовое сообщение...")
        voice_file = await update.message.voice.get_file()
        recognized_text = await recognize_speech(voice_file)
        
        if recognized_text:
            user_input = recognized_text
            await update.message.reply_text(f"📝 Распознано: {recognized_text}")
        else:
            await update.message.reply_text("❌ Не удалось распознать голос")
            return
    
    # 3. Видео-кружок
    elif update.message.video_note:
        input_type = "video_note"
        await update.message.reply_text("📹 Распознаю речь из видео...")
        video_file = await update.message.video_note.get_file()
        recognized_text = await extract_audio_from_video(video_file)
        
        if recognized_text:
            user_input = recognized_text
            await update.message.reply_text(f"📝 Распознано: {recognized_text}")
        else:
            await update.message.reply_text("❌ Не удалось распознать речь в видео")
            return
    
    # 4. Видеофайл
    elif update.message.video:
        input_type = "video"
        await update.message.reply_text("🎥 Анализирую видео...")
        video_file = await update.message.video.get_file()
        recognized_text = await extract_audio_from_video(video_file)
        
        if recognized_text:
            user_input = recognized_text
            await update.message.reply_text(f"📝 Распознано: {recognized_text}")
        else:
            await update.message.reply_text("❌ Не удалось распознать речь в видео")
            return
    
    else:
        await update.message.reply_text("❌ Я пока понимаю только текст, голос и видео")
        return
    
    if not user_input:
        return
    
    # Применяем цензуру
    if mat_filter:
        user_input = censor_text(user_input)
    
    # Проверка токенов
    if not is_creator and not vip and tokens < 1:
        await update.message.reply_text("❌ Нет токенов! Используй /start")
        return
    
    await update.message.chat.send_action(action="typing")
    
    try:
        system_prompt = f"Ты MonGPT. Получен {input_type}."
        if is_creator:
            system_prompt += " Сейчас с тобой общается СОЗДАТЕЛЬ @God_Mon1tyy! Отвечай с особым уважением."
        
        response = requests.post(
            "https://api.poe.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {POE_API_KEY}"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_input}
                ]
            },
            timeout=30
        )
        
        if response.status_code == 200:
            answer = response.json()['choices'][0]['message']['content']
            
            if not is_creator and not vip:
                use_token(user_id)
            
            creator_note = f"\n\n_👑 Сообщение от {CREATOR_NAME}_" if is_creator else ""
            await update.message.reply_text(f"{answer}{creator_note}")
        else:
            await update.message.reply_text("😵 Ошибка AI, попробуй позже")
            
    except Exception as e:
        await update.message.reply_text(f"⏱️ Ошибка: {str(e)[:100]}")

# ===== ЗАПУСК =====
def main():
    init_db()
    
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("mat", mat_command))
    app.add_handler(CommandHandler("balance", balance_command))
    app.add_handler(CommandHandler("voice", voice_command))
    app.add_handler(CommandHandler("say", voice_command))  # синоним
    
    # Кнопки
    app.add_handler(CallbackQueryHandler(button_handler))
    
    # Сообщения
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))
    
    print("🚀 MonGPT ULTIMATE PRO MAX запущен!")
    print(f"👑 Создатель: {CREATOR_NAME} (ID: {CREATOR_ID})")
    print(f"📱 Бот: {BOT_USERNAME}")
    print("🎤 Распознавание голоса: АКТИВНО")
    print("📹 Распознавание видео: АКТИВНО")
    print("🔗 Распознавание ссылок: АКТИВНО")
    print("🔊 Генерация голосовых: АКТИВНО (команда /voice)")
    
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TELEGRAM_TOKEN,
        webhook_url=f"https://mongpt-bot.onrender.com/{TELEGRAM_TOKEN}"
    )

if __name__ == "__main__":
    main()
