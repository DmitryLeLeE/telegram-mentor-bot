import logging
import json
import pandas as pd
import asyncio
import os
import requests # <-- ДОБАВЛЕНО для работы с облачным хранилищем

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from telegram.error import BadRequest

# --- КОНФИГУРАЦИЯ (теперь берется из безопасных переменных окружения) ---
# Эти значения мы настроим прямо на сервере, а не в коде.
TOKEN = os.environ.get("TOKEN")
JSONBIN_API_KEY = os.environ.get("JSONBIN_API_KEY")
BIN_ID = os.environ.get("BIN_ID")

ADMIN_IDS = {775251841, 796639606, 721329781}

# --- ТЕКСТ КНОПОК ---
BTN_START_REG = "▶️ Выбрать наставника"
BTN_MY_MENTOR = "👤 Мой наставник"
BTN_CHANGE_MENTOR = "🔄 Сменить наставника"

# --- ГЛОБАЛЬНАЯ БЛОКИРОВКА ---
data_lock = asyncio.Lock()

# --- Настройка логирования ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Структура данных о наставниках (остается в коде) ---
MENTORS_DATA = [
    # 1 поток
    {"id": 101, "name": "Даша Selena «Рубцы»", "limit": 13, "stream": 1},
    {"id": 102, "name": "Артур Гемпик «Разбор ваших бизнес систем»", "limit": 13, "stream": 1},
    {"id": 103, "name": "Ольга Герц «Стартер-пак для легальной работы»", "limit": 13, "stream": 1},
    {"id": 104, "name": "Сергей «Tyler» Попов «Поболтушки с Тайлером»", "limit": 13, "stream": 1},
    {"id": 105, "name": "Дима Арбузов «Прокол «Daith»»", "limit": 13, "stream": 1},
    # 2 поток
    {"id": 201, "name": "Алексей “tushk4” Вязьмин «Технические аспекты проколов»", "limit": 13, "stream": 2},
    {"id": 202, "name": "Марго Крамер «Женский генитальный пирсинг»", "limit": 13, "stream": 2},
    {"id": 203, "name": "Полина Гриненко «Маркетинг, продвижение»", "limit": 13, "stream": 2},
    {"id": 204, "name": "Артем Паршин & Маргарита Сердюкова «Создание фотографии»", "limit": 13, "stream": 2},
    {"id": 205, "name": "Настя Жабура «Как сделать чтобы топы не раскручивались»", "limit": 13, "stream": 2},
]

# --- ИЗМЕНЕНО: Функции для работы с данными через облако JSONbin.io ---

def load_data():
    """Загружает данные из JSONbin.io."""
    headers = {'X-Master-Key': JSONBIN_API_KEY}
    default_data = {"mentors": MENTORS_DATA, "mentees": {}}
    
    if not BIN_ID or not JSONBIN_API_KEY:
        logger.error("JSONbin API Key or BIN_ID not configured!")
        return default_data

    try:
        req = requests.get(f'https://api.jsonbin.io/v3/b/{BIN_ID}/latest', headers=headers, timeout=10)
        req.raise_for_status()
        data = req.json()
        
        # Проверяем, что в облаке не пустые данные
        if 'record' in data:
             data = data['record']

        if 'mentors' not in data or not data.get('mentors'):
            data['mentors'] = MENTORS_DATA
        if 'mentees' not in data:
            data['mentees'] = {}
        return data
    except Exception as e:
        logger.error(f"Failed to load data from JSONbin, using default. Error: {e}")
        return default_data

def save_data(data):
    """Сохраняет данные в JSONbin.io."""
    headers = {
        'Content-Type': 'application/json',
        'X-Master-Key': JSONBIN_API_KEY
    }
    if not BIN_ID or not JSONBIN_API_KEY:
        logger.error("Cannot save data, JSONbin API Key or BIN_ID not configured!")
        return False

    try:
        req = requests.put(f'https://api.jsonbin.io/v3/b/{BIN_ID}', json=data, headers=headers, timeout=10)
        req.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Failed to save data to JSONbin. Error: {e}")
        return False

# --- ВЕСЬ ОСТАЛЬНОЙ КОД БОТА ОСТАЕТСЯ БЕЗ ИЗМЕНЕНИЙ ---
# (здесь идет весь ваш код обработчиков: start, handle_start_registration и т.д.)
# Я скопирую его ниже для полноты.

def get_main_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    """Возвращает клавиатуру в зависимости от статуса регистрации пользователя."""
    data = load_data()
    if str(user_id) in data["mentees"] and data["mentees"][str(user_id)].get("mentor_id"):
        keyboard = [[BTN_MY_MENTOR, BTN_CHANGE_MENTOR]]
    else:
        keyboard = [[BTN_START_REG]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start. Приветствует и показывает основную клавиатуру."""
    user = update.effective_user
    reply_markup = get_main_keyboard(user.id)
    welcome_text = (
        f"Здравствуйте, {user.first_name}!\n\n"
        "Наставничество — это уникальный интерактивный формат, где участники погружаются в атмосферу живого диалога. "
        "Вместо традиционных лекций — беседа в мини-группе до 13 человек. Вы сами выбираете себе наставника.\n\n"
        "Наставничество пройдет 5 октября, в последний день мероприятия, в два потока:\n"
        "▫️ Первый — с 12:00 до 13:20\n"
        "▫️ Второй — с 14:40 до 16:00\n"
        "Мероприятие состоится в зале «Панорама».\n\n"
        "Места ограничены, поэтому важно заранее выбрать своего наставника и записаться. "
        "Формат не предполагает строгого регламента, вы можете задавать вопросы и обсуждать тему с наставником."
    )
    await update.message.reply_text(
        welcome_text,
        reply_markup=reply_markup,
    )

async def handle_start_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    async with data_lock:
        data = load_data()
        mentee_info = data["mentees"].get(user_id)
        if mentee_info and mentee_info.get("mentor_id"):
            await update.message.reply_text(
                "Вы уже записаны к наставнику. Если хотите сменить его, используйте соответствующую кнопку.",
                reply_markup=get_main_keyboard(update.effective_user.id),
            )
            return

        if mentee_info and mentee_info.get("name"):
            await show_mentor_selection(update, context)
        else:
            context.user_data['awaiting_name'] = True
            await update.message.reply_text(
                "Отлично! Пожалуйста, напишите Ваши Имя и Фамилию.",
                reply_markup=ReplyKeyboardRemove(),
            )

async def handle_my_mentor_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = load_data()
    mentee_info = data["mentees"].get(user_id)

    if not mentee_info or not mentee_info.get("mentor_id"):
        await update.message.reply_text(
            "Вы еще не выбрали наставника. Нажмите 'Выбрать наставника', чтобы начать.",
            reply_markup=get_main_keyboard(update.effective_user.id),
        )
        return

    mentor_id = mentee_info.get("mentor_id")
    mentor = next((m for m in data["mentors"] if m["id"] == mentor_id), None)

    if not mentor:
        await update.message.reply_text("Произошла ошибка: Ваш наставник не найден. Попробуйте выбрать его заново.")
        return

    stream_times = {1: "12:00 - 13:20", 2: "14:40 - 16:00"}
    stream_time = stream_times.get(mentor.get("stream", 0), "Время не указано")

    await update.message.reply_text(
        f"Ваш наставник:\n\n👤 **{mentor['name']}**\n⏰ **Поток:** {mentor['stream']} ({stream_time})",
        reply_markup=get_main_keyboard(update.effective_user.id),
        parse_mode='Markdown'
    )

async def handle_name_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('awaiting_name'):
        await update.message.reply_text(
            "Я не совсем понимаю. Пожалуйста, используйте кнопки.",
            reply_markup=get_main_keyboard(update.effective_user.id),
        )
        return

    user_name = update.message.text.strip()
    user_id = str(update.effective_user.id)

    async with data_lock:
        data = load_data()
        if user_id in data["mentees"]:
            data["mentees"][user_id]["name"] = user_name
        else:
            data["mentees"][user_id] = {"name": user_name, "mentor_id": None, "question": None}
        save_data(data)

    context.user_data['awaiting_name'] = False
    await update.message.reply_text(f"Спасибо, {user_name}!")
    await show_mentor_selection(update, context)

async def show_mentor_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, is_change: bool = False):
    target_message = update.callback_query.message if update.callback_query else update.message
    query = update.callback_query
    
    data = load_data()

    mentee_counts = {m['id']: 0 for m in data['mentors']}
    for mentee in data["mentees"].values():
        mentor_id = mentee.get("mentor_id")
        if mentor_id in mentee_counts:
            mentee_counts[mentor_id] += 1

    stream_times = {1: "12:00 - 13:20", 2: "14:40 - 16:00"}

    message_text = "Пожалуйста, выберите наставника (кнопки с цифрами ниже):\n"
    keyboard_rows = []
    buttons_in_row = []
    sequential_counter = 1

    for stream_num in sorted(stream_times.keys()):
        message_text += f"\n--- **Поток {stream_num} ({stream_times[stream_num]})** ---\n"
        mentors_in_stream = [m for m in data["mentors"] if m["stream"] == stream_num]
        
        for mentor in mentors_in_stream:
            free_slots = mentor["limit"] - mentee_counts.get(mentor["id"], 0)
            
            buttons_in_row.append(InlineKeyboardButton(str(sequential_counter), callback_data=f"select_mentor_{mentor['id']}"))
            
            if free_slots > 0:
                message_text += f"\n**{sequential_counter}. 👤 {mentor['name']}**\n_(свободно: {free_slots})_\n"
            else:
                message_text += f"\n~**{sequential_counter}. 👤 {mentor['name']}**~\n_(мест нет)_\n"

            if len(buttons_in_row) == 5:
                keyboard_rows.append(buttons_in_row)
                buttons_in_row = []
            
            sequential_counter += 1

    if buttons_in_row:
        keyboard_rows.append(buttons_in_row)

    if is_change:
        keyboard_rows.append([InlineKeyboardButton("🔙 Отмена", callback_data="change_mentor_cancel")])

    reply_markup = InlineKeyboardMarkup(keyboard_rows)

    try:
        if query:
            await query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await target_message.reply_text(message_text, reply_markup=reply_markup, parse_mode='Markdown')
    except BadRequest as e:
        if "Message is not modified" in str(e):
            pass
        else:
            raise e

async def ask_question_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE, mentor: dict):
    user_id = str(update.effective_user.id)
    context.user_data['awaiting_question'] = True
    
    stream_times = {1: "12:00 - 13:20", 2: "14:40 - 16:00"}
    stream_time = stream_times.get(mentor.get("stream", 0), "Время не указано")

    confirmation_text = (
        f"Отлично! Ваша запись подтверждена.\n\n"
        f"👤 **Наставник:** {mentor['name']}\n"
        f"🗓 **Поток:** {mentor['stream']} ({stream_time})\n\n"
        "Хотите заранее задать свой вопрос? Просто напишите его в следующем сообщении. "
        "Если вопроса нет, можете проигнорировать это сообщение или выбрать другую опцию в меню."
    )

    if update.callback_query:
        await update.callback_query.edit_message_text("Выбор подтвержден!")

    await context.bot.send_message(
        chat_id=user_id,
        text=confirmation_text,
        reply_markup=get_main_keyboard(int(user_id)),
        parse_mode='Markdown'
    )

async def notify_admins_of_question(context: ContextTypes.DEFAULT_TYPE, mentee_name: str, mentor_name: str, question: str):
    message = (
        f"🔔 Новый вопрос от участника!\n\n"
        f"От: {mentee_name}\n"
        f"Кому: {mentor_name}\n"
        f"Вопрос: {question}"
    )
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(chat_id=admin_id, text=message, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление админу {admin_id}: {e}")

async def handle_question_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('awaiting_question'):
        await update.message.reply_text(
            "Я не совсем понимаю. Пожалуйста, используйте кнопки.",
            reply_markup=get_main_keyboard(update.effective_user.id),
        )
        return

    question_text = update.message.text.strip()
    user_id = str(update.effective_user.id)
    mentee_name = "N/A"
    mentor_name = "Не выбран"

    async with data_lock:
        data = load_data()
        if user_id in data["mentees"]:
            data["mentees"][user_id]["question"] = question_text
            save_data(data)
            
            mentee_name = data["mentees"][user_id].get("name", "N/A")
            mentor_id = data["mentees"][user_id].get("mentor_id")
            mentor = next((m for m in data["mentors"] if m["id"] == mentor_id), None)
            if mentor:
                mentor_name = mentor["name"]
        else:
            await update.message.reply_text("Произошла ошибка. Попробуйте зарегистрироваться заново.")
            return

    context.user_data['awaiting_question'] = False 
    await update.message.reply_text(
        "Спасибо, ваш вопрос сохранен! Наставник сможет ознакомиться с ним заранее.",
        reply_markup=get_main_keyboard(int(user_id))
    )

    await notify_admins_of_question(context, mentee_name, mentor_name, question_text)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    
    if query.data == "change_mentor_cancel":
        await query.edit_message_text("Смена наставника отменена.")
        await query.message.reply_text(
            "Вы остаётесь с вашим текущим наставником.",
            reply_markup=get_main_keyboard(int(user_id)),
        )
        return

    if query.data.startswith("select_mentor_"):
        mentor_id_to_select = int(query.data.split("_")[2])
        
        async with data_lock:
            data = load_data()
            mentee_info = data["mentees"].get(user_id)
            if not mentee_info:
                await query.answer("Ошибка: не удалось найти Вашу регистрацию. Начните заново с /start.", show_alert=True)
                return
            
            if mentee_info.get("mentor_id") == mentor_id_to_select:
                await query.answer("Вы уже записаны к этому наставнику.", show_alert=True)
                return

            mentee_counts = {m['id']: 0 for m in data['mentors']}
            for mentee in data["mentees"].values():
                m_id = mentee.get("mentor_id")
                if m_id and m_id in mentee_counts:
                    mentee_counts[m_id] += 1

            mentor_to_select = next((m for m in data["mentors"] if m["id"] == mentor_id_to_select), None)
            if not mentor_to_select:
                await query.answer("Ошибка: этот наставник больше не доступен.", show_alert=True)
                return
            
            if mentee_counts.get(mentor_id_to_select, 0) >= mentor_to_select["limit"]:
                await query.answer("У этого наставника закончились места. Пожалуйста, выберите другого.", show_alert=True)
                return
            
            data["mentees"][user_id]["mentor_id"] = mentor_id_to_select
            data["mentees"][user_id]["question"] = None
            save_data(data)
        
        await ask_question_prompt(update, context, mentor_to_select)

async def export_to_excel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("У Вас нет прав для выполнения этой команды.")
        return

    async with data_lock:
        data = load_data()

    if not data["mentees"]:
        await update.message.reply_text("Пока нет ни одного зарегистрированного участника.")
        return
        
    mentors_map = {mentor['id']: mentor for mentor in data['mentors']}
    report_data = []
    for mentee_id, mentee_info in data["mentees"].items():
        mentor_id = mentee_info.get("mentor_id")
        mentor = mentors_map.get(mentor_id)
        if mentor:
            mentor_name = mentor["name"]
            stream_info = f"Поток {mentor['stream']}"
        else:
            mentor_name = "Не выбран"
            stream_info = "N/A"

        report_data.append({
            "Имя Участника": mentee_info.get("name", "N/A"),
            "Telegram ID": mentee_id,
            "Выбранный наставник": mentor_name,
            "Поток": stream_info,
            "Заданный вопрос": mentee_info.get("question", "Нет вопроса"),
        })

    df = pd.DataFrame(report_data)
    file_path = "mentorship_report.xlsx"
    df.to_excel(file_path, index=False, engine='openpyxl')

    await update.message.reply_text("Отчет готов! Отправляю файл...")
    await context.bot.send_document(chat_id=update.effective_chat.id, document=open(file_path, 'rb'))

async def reset_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    async with data_lock:
        data = load_data()
        if user_id in data["mentees"]:
            del data["mentees"][user_id]
            save_data(data)
            refreshed_keyboard = get_main_keyboard(int(user_id))
        else:
            await update.message.reply_text("Вы еще не были зарегистрированы.")
            return

    await update.message.reply_text(
        "Ваша регистрация сброшена.",
        reply_markup=refreshed_keyboard,
    )

def main():
    """Основная функция для запуска бота."""
    if not TOKEN:
        logger.critical("TOKEN не найден! Завершение работы. Укажите его в переменных окружения.")
        return

    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("reset", reset_user))
    application.add_handler(CommandHandler("export", export_to_excel))

    application.add_handler(MessageHandler(filters.Regex(f"^{BTN_START_REG}$"), handle_start_registration))
    application.add_handler(MessageHandler(filters.Regex(f"^{BTN_MY_MENTOR}$"), handle_my_mentor_info))
    application.add_handler(MessageHandler(
        filters.Regex(f"^{BTN_CHANGE_MENTOR}$"),
        lambda u, c: show_mentor_selection(u, c, is_change=True)
    ))

    application.add_handler(CallbackQueryHandler(button_callback))

    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.UpdateType.MESSAGE,
        lambda u, c: handle_question_input(u, c) if c.user_data.get('awaiting_question') else handle_name_input(u, c)
    ))

    logger.info("Бот запускается...")
    application.run_polling()

if __name__ == "__main__":
    main()