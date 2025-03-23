import telebot
from telebot import types
from javascript import require, On
import time
import sqlite3
import json

# Замените на ваш токен Telegram-бота
TELEGRAM_BOT_TOKEN = '7610642746:AAH6a96m_EpRpwB5GSB9gxrJZCQjMebe_7U'

# Инициализация бота
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

# Загрузка mineflayer через javascript.require
mineflayer = require('mineflayer')

# Глобальные переменные
mineBot = None
server_list = {}  # Список серверов: {user_id: {"host": "адрес", "port": "порт"}}
last_message_time = {}  # Время последнего сообщения бота в игре
track_chat = False  # Флаг для отслеживания игрового чата
chat_users = {}  # Словарь для хранения пользователей, которые включили отслеживание чата

# Подключение к базе данных
conn = sqlite3.connect('servers.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS servers
                  (user_id INTEGER, server_data TEXT)''')
conn.commit()

# Загрузка серверов из базы данных
def load_servers(user_id):
    cursor.execute("SELECT server_data FROM servers WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    server_list[user_id] = [json.loads(row[0]) for row in rows]

# Сохранение сервера в базу данных
def save_server(user_id, server_data):
    cursor.execute("INSERT INTO servers (user_id, server_data) VALUES (?, ?)",
                   (user_id, json.dumps(server_data)))
    conn.commit()

# Удаление сервера из базы данных
def delete_server(user_id, server_data):
    cursor.execute("DELETE FROM servers WHERE user_id = ? AND server_data = ?",
                   (user_id, json.dumps(server_data)))
    conn.commit()

# Обработчик команды /start
@bot.message_handler(commands=['start'])
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
    global mineBot
    user_id = message.from_user.id

    if user_id not in server_list or not server_list[user_id]:
        bot.send_message(message.chat.id, "❌ Сначала добавьте сервер с помощью команды /Servers.")
        return

    server = server_list[user_id][0]  # Используем первый сервер из списка
    bot.send_message(message.chat.id, '🚀 Бот запускается...')

    # Создаем бота Minecraft
    mineBot = mineflayer.createBot({
        'host': server["host"],
        'port': server["port"],
        'username': server.get("username", "BotServer"),
        'version': False
    })

    # Обработчик успешного подключения
    @On(mineBot, 'login')
    def handle_login(*args):
        bot.send_message(message.chat.id, '✅ Бот успешно подключился к серверу Minecraft!')
        last_message_time[user_id] = time.time()  # Запоминаем время последнего сообщения

    # Обработчик ошибок подключения
    @On(mineBot, 'error')
    def handle_error(err, *args):
        bot.send_message(message.chat.id, f'❌ Ошибка подключения: {err}')

    # Обработчик сообщений в чате Minecraft
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
        load_servers(user_id)
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
@bot.callback_query_handler(func=lambda call: call.data.startswith("delete_"))
def delete_server_callback(call):
    user_id = call.from_user.id
    server_str = call.data.replace("delete_", "")
    host, port = server_str.split(':')
    server_data = {"host": host, "port": int(port)}
    delete_server(user_id, server_data)
    load_servers(user_id)
    bot.send_message(call.message.chat.id, f"✅ Сервер удален: {host}:{port}")

# Обработчик команды /ChangeNick
@bot.message_handler(commands=['ChangeNick'])
def change_nick(message):
    msg = bot.send_message(message.chat.id, "👤 Введите новый ник:")
    bot.register_next_step_handler(msg, process_nick_input)

def process_nick_input(message):
    user_id = message.from_user.id
    if user_id in server_list and server_list[user_id]:
        server_list[user_id][0]["username"] = message.text
        bot.send_message(message.chat.id, f"✅ Ник изменен на: {message.text}")
    else:
        bot.send_message(message.chat.id, "❌ Сначала добавьте сервер с помощью команды /Servers.")

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

# Обработчик команды /GetPlayers
@bot.message_handler(commands=['GetPlayers'])
def get_players(message):
    global mineBot
    if mineBot:
        try:
            players = mineBot.players
            player_list = [player.username for player in players.values()]
            bot.send_message(message.chat.id, f"👥 Игроки на сервере: {', '.join(player_list)}")
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Ошибка при получении списка игроков: {e}")
    else:
        bot.send_message(message.chat.id, "❌ Бот Minecraft не запущен. Используйте /BotStart.")

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

# Запуск бота
bot.polling(none_stop=True)