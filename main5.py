import telebot
from telebot import types
from javascript import require, On
import time
import sqlite3
import json
import re

# Замените на ваш токен Telegram-бота
TELEGRAM_BOT_TOKEN = ''
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
mineflayer = require('mineflayer')

mineBot = None
server_list = {} 
last_message_time = {}  
track_chat = False  
chat_users = {}  

conn = sqlite3.connect('configs.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS configs
                  (user_id INTEGER, server_data TEXT, bot_username TEXT DEFAULT 'Bot')''')
conn.commit()

def get_bot_username(user_id):
    try:
        cursor.execute("SELECT bot_username FROM configs WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return row[0] if row else 'Bot'  
    except Exception as e:
        print(f"Ошибка при получении ника: {e}")
        return 'Bot'
    

def load_servers(user_id):
    cursor.execute("SELECT server_data FROM configs WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    
    if not rows:
        server_list[user_id] = []
        return
    
    try:
        servers = json.loads(rows[0][0])
        
        if isinstance(servers, list):
            server_list[user_id] = servers
        else:
            server_list[user_id] = [servers]
            
    except json.JSONDecodeError as e:
        print(f"Ошибка декодирования JSON: {e}")
        server_list[user_id] = []

def save_server(user_id, server_data):
    cursor.execute("SELECT server_data FROM configs WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    
    if row:
        servers = json.loads(row[0])
        servers.append(server_data)
        cursor.execute("UPDATE configs SET server_data = ? WHERE user_id = ?",
                      (json.dumps(servers), user_id))
    else:
        cursor.execute("INSERT INTO configs (user_id, server_data) VALUES (?, ?)",
                      (user_id, json.dumps([server_data])))
    conn.commit()

def delete_server(user_id, server_data):
    cursor.execute("DELETE FROM configs WHERE user_id = ? AND server_data = ?",
                   (user_id, json.dumps(server_data)))
    conn.commit()

# Обработчик команды /start
@bot.message_handler(commands=['start', 'Help'])
def start(message):
    user_id = message.from_user.id
    load_servers(user_id)

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton('/BotStart 🚀'))
    markup.add(types.KeyboardButton('/BotStop 🛑'))
    markup.add(types.KeyboardButton('/Servers 🌐'))
    markup.add(types.KeyboardButton('/ChangeNick 👤'))
    markup.add(types.KeyboardButton('/SendMessage 📨'))
    markup.add(types.KeyboardButton('/GetCoordinates 📍'))
    markup.add(types.KeyboardButton('/GetPlayers 👥'))
    markup.add(types.KeyboardButton('/GetStatus 📊'))
    markup.add(types.KeyboardButton('/Help ❓'))

    come_mess = f'👋 Привет, {message.from_user.first_name}!'
    bot_comm = (
        '📜 Список команд:\n'
        '🚀 /BotStart - запустить бота.\n'
        '🛑 /BotStop - остановить бота.\n'
        '🌐 /Servers - управление серверами.\n'
        '👤 /ChangeNick - изменить ник бота.\n'
        '📨 /SendMessage - отправить сообщение в чат.\n'
        '📍 /GetCoordinates - узнать свои координаты.\n'
        '👥 /GetPlayers - список игроков на сервере.\n'
        '📊 /GetStatus - узнать свое состояние.\n'
        '❓ /Help - список команд.'
    )
    bot.send_message(message.chat.id, come_mess, reply_markup=markup)
    bot.send_message(message.chat.id, bot_comm, parse_mode='html')

# Обработчик команды /BotStart
@bot.message_handler(commands=['BotStart'])
def bot_start(message):
    global mineBot, Nick
    user_id = message.from_user.id
    load_servers(user_id)
    if user_id not in server_list or not server_list[user_id]:
        bot.send_message(message.chat.id, "❌ Сначала добавьте сервер с помощью команды /Servers.")
        return

    server = server_list[user_id][0]
    bot.send_message(message.chat.id, '🚀 Бот запускается...')
    cursor.execute("SELECT bot_username FROM configs WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    print(rows)
    bot_username = get_bot_username(user_id)
    try:
        mineBot = mineflayer.createBot({
            'host': server["host"],
            'port': server["port"],
            'username': bot_username,
            'version': False
        })
        
        @On(mineBot, 'login')
        def handle_login(*args):
            bot.send_message(message.chat.id, '✅ Бот успешно подключился к серверу Minecraft!')
            last_message_time[user_id] = time.time()

        @On(mineBot, 'error')
        def handle_error(err, *args):
            bot.send_message(message.chat.id, f'❌ Ошибка подключения')
            print(str(err)[:200])
            mineBot = None

    except Exception as e:
        bot.send_message(message.chat.id, f'❌ Не удалось создать бота')
        print(e)
        mineBot = None
    

    # Обработчик ошибок подключения
    @On(mineBot, 'error')
    def handle_error(err, *args):
        print(err)
    @On(mineBot, 'chat')
    def handle_chat(username, message, *args):
        if track_chat:
            for user_id in chat_users:
                bot.send_message(user_id, f"💬 <b>{username}</b>: {message}", parse_mode='html')

# Обработчик команды /BotStop
@bot.message_handler(commands=['BotStop'])
def bot_stop(message):
    global mineBot
    if mineBot:
        bot.send_message(message.chat.id, '🛑 Бот останавливается...')
        mineBot.quit()
        mineBot = None
        bot.send_message(message.chat.id, '✅ Бот успешно остановлен!')
    else:
        bot.send_message(message.chat.id, '❌ Бот не запущен.')

# Обработчик команды /Servers
@bot.message_handler(commands=['Servers'])
def servers_menu(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🌐 Выбрать из сохраненных", callback_data="select_server"))
    markup.add(types.InlineKeyboardButton("➕ Добавить сервер", callback_data="add_server"))
    markup.add(types.InlineKeyboardButton("➖ Удалить сервер", callback_data="delete_server"))
    bot.send_message(message.chat.id, "🌐 Управление серверами:", reply_markup=markup)

# Обработчик инлайн кнопок для /Servers
@bot.callback_query_handler(func=lambda call: call.data in ["select_server", "add_server", "delete_server"])

def servers_callback(call):
    user_id = call.from_user.id
    load_servers(user_id)
    if call.data == "select_server":
        if user_id in server_list and server_list[user_id]:
            markup = types.InlineKeyboardMarkup()
            for server in server_list[user_id]:
                server_str = f"{server['host']}:{server['port']}"
                markup.add(types.InlineKeyboardButton(server_str, callback_data=f"select_{server_str}"))
            markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_servers"))
            bot.send_message(call.message.chat.id, "🌐 Выберите сервер:", reply_markup=markup)
        else:
            bot.send_message(call.message.chat.id, "❌ Нет сохраненных серверов.")
    elif call.data == "add_server":
        msg = bot.send_message(call.message.chat.id, "Введите адрес сервера и порт в формате: адрес:порт")
        bot.register_next_step_handler(msg, process_add_server)
    elif call.data == "delete_server":
        if user_id in server_list and server_list[user_id]:
            markup = types.InlineKeyboardMarkup()
            for server in server_list[user_id]:
                server_str = f"{server['host']}:{server['port']}"
                markup.add(types.InlineKeyboardButton(server_str, callback_data=f"delete_{server_str}"))
            markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_servers"))
            bot.send_message(call.message.chat.id, "🌐 Выберите сервер для удаления:", reply_markup=markup)
        else:
            bot.send_message(call.message.chat.id, "❌ Нет сохраненных серверов.")

# Обработчик добавления сервера
def process_add_server(message):
    user_id = message.from_user.id
    try:
        host, port = message.text.split(':')
        server_data = {"host": host, "port": int(port)}
        save_server(user_id, server_data)
        bot.send_message(message.chat.id, f"✅ Сервер добавлен: {host}:{port}")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}. Введите адрес и порт в формате: адрес:порт")


    

# Обработчик выбора сервера
@bot.callback_query_handler(func=lambda call: call.data.startswith("select_"))
def select_server(call):
    user_id = call.from_user.id
    server_str = call.data.replace("select_", "")
    host, port = server_str.split(':')
    server_list[user_id] = [{"host": host, "port": int(port)}]
    bot.send_message(call.message.chat.id, f"✅ Выбран сервер: {host}:{port}")

# Обработчик удаления сервера
def delete_server(user_id, server_data):
    """Удаляет сервер из базы данных"""
    cursor.execute("SELECT server_data FROM configs WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    
    if not row or not row[0]:
        return False
    
    try:
        servers = json.loads(row[0])
        
        index_to_delete = None
        for i, server in enumerate(servers):
            if (str(server['host']) == str(server_data['host']) and 
                int(server['port']) == int(server_data['port'])):
                index_to_delete = i
                break
        
        if index_to_delete is not None:
            del servers[index_to_delete]
            
            cursor.execute("UPDATE configs SET server_data = ? WHERE user_id = ?",
                          (json.dumps(servers), user_id))
            conn.commit()
            return True
            
    except Exception as e:
        print(f"Ошибка при удалении сервера: {e}")
    
    return False

@bot.callback_query_handler(func=lambda call: call.data.startswith("delete_"))
def delete_server_callback(call):
    user_id = call.from_user.id
    server_str = call.data.replace("delete_", "")
    
    try:
        host, port = server_str.split(':')
        server_data = {"host": host, "port": int(port)}
        
        if delete_server(user_id, server_data):
            load_servers(user_id)
            bot.send_message(call.message.chat.id, f"✅ Сервер удален: {host}:{port}")
        else:
            bot.send_message(call.message.chat.id, "❌ Сервер не найден или произошла ошибка")
            
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ Ошибка: {str(e)[:200]}")
        print(f"Ошибка в delete_server_callback: {e}")

def update_bot_username(user_id, new_username):
    try:
        if not new_username or not new_username.strip():
            return False
            
        new_username = new_username.strip()[:16]
        
        cursor.execute("UPDATE configs SET bot_username = ? WHERE user_id = ?", 
                         (new_username, user_id))
        conn.commit()
        return True
        
    except Exception as e:
        print(f"Ошибка при обновлении ника: {e}")
        conn.rollback()
        return False

# Обработчик команды /ChangeNick
@bot.message_handler(commands=['ChangeNick'])
def change_nick(message):
    global mineBot
    if mineBot:
        mineBot.quit()
        mineBot = None
    msg = bot.send_message(message.chat.id, "👤 Введите новый ник для бота (макс. 16 символов):")
    bot.register_next_step_handler(msg, process_nick_input)

def process_nick_input(message):
    user_id = message.from_user.id
    new_username = message.text
    
    if update_bot_username(user_id, new_username):
        bot.send_message(message.chat.id, f"✅ Ник бота успешно изменен на: {new_username}")
    else:
        bot.send_message(message.chat.id, "❌ Не удалось изменить ник. Попробуйте другой вариант.")



# Обработчик команды /SendMessage
@bot.message_handler(commands=['SendMessage'])
def send_message_menu(message):
    msg = bot.send_message(message.chat.id, "📨 Введите сообщение для отправки в Minecraft:")
    bot.register_next_step_handler(msg, process_message_input)

def process_message_input(message):
    global mineBot
    if mineBot:
        try:
            mineBot.chat(message.text)
            bot.send_message(message.chat.id, f"✅ Сообщение отправлено в Minecraft: {message.text}")
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Ошибка при отправке сообщения: {e}")
    else:
        bot.send_message(message.chat.id, "❌ Бот Minecraft не запущен. Используйте /BotStart.")

# Обработчик команды /GetCoordinates
@bot.message_handler(commands=['GetCoordinates'])
def get_coordinates(message):
    global mineBot
    if mineBot:
        try:
            pos = mineBot.entity.position
            bot.send_message(message.chat.id, f"📍 Ваши координаты: x={pos.x:.2f}, y={pos.y:.2f}, z={pos.z:.2f}")
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Ошибка при получении координат: {e}")
    else:
        bot.send_message(message.chat.id, "❌ Бот Minecraft не запущен. Используйте /BotStart.")



def extract_usernames_from_text(data_text):
    """Извлекает все имена игроков из текстового представления объекта"""
    pattern = r"username: '([^']+)'"
    return re.findall(pattern, data_text)

@bot.message_handler(commands=['GetPlayers'])
def get_players(message):
    global mineBot

    if not mineBot:
        bot.send_message(message.chat.id, "❌ Бот не подключен. Используйте /BotStart.")
        return

    try:
        players_text = str(mineBot.players)
        
        player_names = extract_usernames_from_text(players_text)
        
        unique_names = list(set(player_names))
        
        markup = types.InlineKeyboardMarkup()
        for name in unique_names:
            markup.add(types.InlineKeyboardButton(name, callback_data='ignore'))

        if unique_names:
            bot.send_message(message.chat.id, "👥 Игроки онлайн:", reply_markup=markup)
        else:
            bot.send_message(message.chat.id, "🔴 На сервере нет игроков")

    except Exception as e:
        error_msg = str(e)[:300]
        bot.send_message(message.chat.id, f"❌ Ошибка: {error_msg}")




# Обработчик команды /GetStatus
@bot.message_handler(commands=['GetStatus'])
def get_status(message):
    global mineBot
    if mineBot:
        try:
            health = mineBot.health
            food = mineBot.food
            game_mode = mineBot.game.gameMode
            difficulty = mineBot.game.difficulty
            time_of_day = mineBot.time.timeOfDay
            bot.send_message(message.chat.id, f"📊 Состояние:\n"
                                             f"❤️ Здоровье: {health}\n"
                                             f"🍖 Голод: {food}\n"
                                             f"🎮 Режим игры: {game_mode}\n"
                                             f"⚔️ Сложность: {difficulty}\n"
                                             f"⏰ Время: {time_of_day}")
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Ошибка при получении состояния: {e}")
    else:
        bot.send_message(message.chat.id, "❌ Бот Minecraft не запущен. Используйте /BotStart.")

# Обработчик кнопки "Назад" для /Servers
@bot.callback_query_handler(func=lambda call: call.data == "back_to_servers")
def back_to_servers(call):
    servers_menu(call.message)

bot.polling(none_stop=True)
