import os
import logging
import tempfile
from datetime import datetime, date, timedelta
from typing import List
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)
from database import Database

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация базы данных
db = Database()

# Глобальные переменные для хранения состояния
user_states = {}
# Текущий выбранный препарат для каждого пользователя (по умолчанию id=1 — Акнекутан)
user_current_medication: dict[int, int] = {}


def get_user_medication(user_id: int) -> int:
    """Получить текущий выбранный препарат пользователя (по умолчанию 1)."""
    return user_current_medication.get(user_id, 1)


def set_user_medication(user_id: int, medication_id: int) -> None:
    """Установить текущий препарат пользователя."""
    user_current_medication[user_id] = medication_id


def get_main_menu_keyboard():
    """Создает главное меню с кнопками"""
    keyboard = [
        [KeyboardButton("💊 Добавить прием"), KeyboardButton("📅 Сегодня")],
        [KeyboardButton("📊 История"), KeyboardButton("📈 Прогресс")],
        [KeyboardButton("⚙️ Настройки"), KeyboardButton("⏰ Напоминания")],
        [KeyboardButton("🧴 Препараты"), KeyboardButton("📋 Меню")],
        [KeyboardButton("❓ Помощь")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    welcome_message = (
        "👋 Привет! Я помогу тебе отслеживать прием препарата.\n\n"
        "Используй кнопки меню ниже для навигации.\n"
        "Все команды также доступны через текстовые команды."
    )
    await update.message.reply_text(
        welcome_message,
        reply_markup=get_main_menu_keyboard()
    )


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать главное меню"""
    await update.message.reply_text(
        "📋 Главное меню",
        reply_markup=get_main_menu_keyboard()
    )


async def medications_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать список препаратов и выбрать текущий"""
    user_id = update.effective_user.id
    current_med_id = get_user_medication(user_id)
    meds = db.get_medications()
    
    if not meds:
        await update.message.reply_text(
            "Пока не добавлено ни одного препарата. Введите название нового препарата:",
        )
        user_states[user_id] = {"action": "waiting_med_name"}
        return
    
    text = "🧴 Список препаратов:\n\n"
    keyboard_rows = []
    for med_id, name, description in meds:
        mark = "✅" if med_id == current_med_id else "⚪️"
        text += f"{mark} {name} (ID: {med_id})\n"
        keyboard_rows.append(
            [
                InlineKeyboardButton(
                    f"{mark} Выбрать {name}", callback_data=f"med_select_{med_id}"
                )
            ]
        )
    
    keyboard_rows.append(
        [InlineKeyboardButton("➕ Добавить препарат", callback_data="med_add")]
    )
    
    reply_markup = InlineKeyboardMarkup(keyboard_rows)
    await update.message.reply_text(text, reply_markup=reply_markup)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    help_text = (
        "📚 Справка по командам:\n\n"
        "💊 Добавить прием - Добавить запись о приеме препарата\n"
        "   Бот попросит указать количество таблеток и дозировку\n\n"
        "📅 Сегодня - Показать все приемы за сегодня\n\n"
        "📊 История - Показать сводку за последние 7 дней по текущему препарату\n\n"
        "⚙️ Настройки - Настройки курса приема:\n"
        "   - Указать количество таблеток в день\n"
        "   - Указать дозировку таблеток\n"
        "   - Установить даты начала и окончания курса\n\n"
        "📈 Прогресс - Показать прогресс выполнения курса по текущему препарату\n\n"
        "⏰ Напоминания - Управление напоминаниями по текущему препарату:\n"
        "   - Добавить новое напоминание\n"
        "   - Просмотреть список напоминаний\n"
        "   - Удалить напоминание\n\n"
        "🧴 Препараты - Выбор и добавление препаратов\n"
        "📋 Меню - Показать главное меню с кнопками\n\n"
        "Все команды доступны через кнопки меню или текстовые команды (например, /add)"
    )
    await update.message.reply_text(help_text, reply_markup=get_main_menu_keyboard())


async def add_medication(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начать процесс добавления приема препарата"""
    user_id = update.effective_user.id
    user_states[user_id] = {'action': 'waiting_quantity', 'from_reminder': False}
    
    await update.message.reply_text(
        "💊 Добавление приема препарата\n\n"
        "Сколько таблеток вы приняли? (введите число)"
    )


async def handle_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE, quantity: int):
    """Обработка ввода количества таблеток"""
    user_id = update.effective_user.id
    user_states[user_id] = {
        'action': 'waiting_dosage',
        'quantity': quantity
    }
    
    await update.message.reply_text(
        f"✅ Количество: {quantity} таблеток\n\n"
        "Какая дозировка одной таблетки в мг? (введите число, например: 500)"
    )


async def handle_dosage(update: Update, context: ContextTypes.DEFAULT_TYPE, dosage: float):
    """Обработка ввода дозировки и сохранение записи"""
    user_id = update.effective_user.id
    state = user_states.get(user_id, {})
    quantity = state.get('quantity')
    from_reminder = state.get('from_reminder', False)
    
    if quantity is None:
        await update.message.reply_text("❌ Ошибка: не найдено количество таблеток. Начните заново с /add")
        user_states.pop(user_id, None)
        return
    
    # Сохранение в базу данных для текущего препарата
    medication_id = get_user_medication(user_id)
    success = db.add_medication(quantity, dosage, medication_id=medication_id)
    
    if success:
        total_dosage = quantity * dosage
        message = (
            f"✅ Запись добавлена!\n\n"
            f"📊 Детали:\n"
            f"• Количество таблеток: {quantity}\n"
            f"• Дозировка одной таблетки: {dosage} мг\n"
            f"• Общая дозировка: {total_dosage} мг\n"
            f"• Время: {datetime.now().strftime('%H:%M:%S')}"
        )
        if from_reminder:
            message += "\n\n✅ Прием препарата подтвержден!"
        await update.message.reply_text(message, reply_markup=get_main_menu_keyboard())
    else:
        await update.message.reply_text("❌ Ошибка при сохранении записи. Попробуйте еще раз.")
    
    user_states.pop(user_id, None)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    state = user_states.get(user_id, {})
    action = state.get('action')
    
    # Обработка нажатий на кнопки меню
    if not action:
        if text == "💊 Добавить прием" or text == "/add":
            await add_medication(update, context)
            return
        elif text == "📅 Сегодня" or text == "/today":
            await show_today(update, context)
            return
        elif text == "📊 История" or text == "/history":
            await show_history(update, context)
            return
        elif text == "📈 Прогресс" or text == "/progress":
            await progress_command(update, context)
            return
        elif text == "⚙️ Настройки" or text == "/settings":
            await settings_command(update, context)
            return
        elif text == "⏰ Напоминания" or text == "/reminder":
            await reminder_menu(update, context)
            return
        elif text == "🧴 Препараты" or text == "/medications":
            await medications_command(update, context)
            return
        elif text == "📋 Меню" or text == "/menu":
            await menu_command(update, context)
            return
        elif text == "❓ Помощь" or text == "/help":
            await help_command(update, context)
            return
    
    if action == 'waiting_quantity':
        try:
            quantity = int(text)
            if quantity <= 0:
                await update.message.reply_text("❌ Количество должно быть положительным числом. Попробуйте еще раз.")
                return
            await handle_quantity(update, context, quantity)
        except ValueError:
            await update.message.reply_text("❌ Пожалуйста, введите целое число. Попробуйте еще раз.")
    
    elif action == 'waiting_dosage':
        try:
            dosage = float(text)
            if dosage <= 0:
                await update.message.reply_text("❌ Дозировка должна быть положительным числом. Попробуйте еще раз.")
                return
            await handle_dosage(update, context, dosage)
        except ValueError:
            await update.message.reply_text("❌ Пожалуйста, введите число (можно с десятичной точкой). Попробуйте еще раз.")
    
    elif action == 'waiting_reminder_time':
        # Проверка формата времени (HH:MM)
        try:
            time_parts = text.split(':')
            if len(time_parts) != 2:
                raise ValueError
            hour = int(time_parts[0])
            minute = int(time_parts[1])
            if not (0 <= hour < 24 and 0 <= minute < 60):
                raise ValueError
            
            time_str = f"{hour:02d}:{minute:02d}"
            medication_id = get_user_medication(user_id)
            success = db.add_reminder(time_str, medication_id=medication_id)
            
            if success:
                await update.message.reply_text(
                    f"✅ Напоминание добавлено на {time_str}",
                    reply_markup=get_main_menu_keyboard()
                )
            else:
                await update.message.reply_text("❌ Ошибка при добавлении напоминания")
            
            user_states.pop(user_id, None)
        except ValueError:
            await update.message.reply_text("❌ Неверный формат времени. Используйте формат HH:MM (например, 09:30)")
    
    elif action == 'waiting_daily_quantity':
        try:
            daily_quantity = int(text)
            if daily_quantity <= 0:
                await update.message.reply_text("❌ Количество должно быть положительным числом. Попробуйте еще раз.")
                return
            user_states[user_id] = {
                'action': 'waiting_course_dosage',
                'daily_quantity': daily_quantity
            }
            await update.message.reply_text(
                f"✅ Количество таблеток в день: {daily_quantity}\n\n"
                "Какая дозировка одной таблетки в мг? (введите число, например: 500)"
            )
        except ValueError:
            await update.message.reply_text("❌ Пожалуйста, введите целое число. Попробуйте еще раз.")
    
    elif action == 'waiting_course_dosage':
        try:
            dosage = float(text)
            if dosage <= 0:
                await update.message.reply_text("❌ Дозировка должна быть положительным числом. Попробуйте еще раз.")
                return
            daily_quantity = user_states[user_id].get('daily_quantity')
            user_states[user_id] = {
                'action': 'waiting_start_date',
                'daily_quantity': daily_quantity,
                'dosage_mg': dosage
            }
            await update.message.reply_text(
                f"✅ Дозировка: {dosage} мг\n\n"
                "Введите дату начала курса в формате ГГГГ-ММ-ДД (например, 2024-01-15)\n"
                "Или отправьте 'сегодня' для использования сегодняшней даты"
            )
        except ValueError:
            await update.message.reply_text("❌ Пожалуйста, введите число (можно с десятичной точкой). Попробуйте еще раз.")
    
    elif action == 'waiting_med_name':
        # Создание нового препарата
        name = text.strip()
        if not name:
            await update.message.reply_text("❌ Название не может быть пустым. Введите название препарата.")
            return
        med_id = db.create_medication(name)
        if not med_id:
            await update.message.reply_text("❌ Не удалось создать препарат. Попробуйте ещё раз.")
        else:
            set_user_medication(user_id, med_id)
            await update.message.reply_text(
                f"✅ Препарат создан и выбран: {name}",
                reply_markup=get_main_menu_keyboard()
            )
        user_states.pop(user_id, None)

    elif action == 'waiting_start_date':
        try:
            if text.lower() in ['сегодня', 'today', 'now']:
                start_date = date.today().strftime("%Y-%m-%d")
            else:
                # Проверка формата даты
                start_date_obj = datetime.strptime(text, "%Y-%m-%d").date()
                start_date = start_date_obj.strftime("%Y-%m-%d")
            
            daily_quantity = user_states[user_id].get('daily_quantity')
            dosage_mg = user_states[user_id].get('dosage_mg')
            user_states[user_id] = {
                'action': 'waiting_end_date',
                'daily_quantity': daily_quantity,
                'dosage_mg': dosage_mg,
                'start_date': start_date
            }
            await update.message.reply_text(
                f"✅ Дата начала: {start_date}\n\n"
                "Введите дату окончания курса в формате ГГГГ-ММ-ДД\n"
                "Или отправьте 'нет' если курс без ограничения по дате"
            )
        except ValueError:
            await update.message.reply_text("❌ Неверный формат даты. Используйте формат ГГГГ-ММ-ДД (например, 2024-01-15)")
    
    elif action == 'waiting_end_date':
        try:
            daily_quantity = user_states[user_id].get('daily_quantity')
            dosage_mg = user_states[user_id].get('dosage_mg')
            start_date = user_states[user_id].get('start_date')
            medication_id = get_user_medication(user_id)
            
            if text.lower() in ['нет', 'no', 'none', '']:
                end_date = None
            else:
                end_date_obj = datetime.strptime(text, "%Y-%m-%d").date()
                end_date = end_date_obj.strftime("%Y-%m-%d")
                # Проверка, что дата окончания не раньше даты начала
                if end_date < start_date:
                    await update.message.reply_text("❌ Дата окончания не может быть раньше даты начала. Попробуйте еще раз.")
                    return
            
            # Сохраняем настройки курса для текущего препарата
            success = db.set_course_settings(
                daily_quantity, dosage_mg, start_date, end_date, medication_id=medication_id
            )
            
            if success:
                message = (
                    f"✅ Настройки курса сохранены!\n\n"
                    f"📊 Параметры курса:\n"
                    f"• Таблеток в день: {daily_quantity}\n"
                    f"• Дозировка одной таблетки: {dosage_mg} мг\n"
                    f"• Дата начала: {start_date}\n"
                )
                if end_date:
                    message += f"• Дата окончания: {end_date}\n"
                else:
                    message += "• Дата окончания: не ограничена\n"
                
                await update.message.reply_text(message, reply_markup=get_main_menu_keyboard())
            else:
                await update.message.reply_text("❌ Ошибка при сохранении настроек курса. Попробуйте еще раз.")
            
            user_states.pop(user_id, None)
        except ValueError:
            await update.message.reply_text("❌ Неверный формат даты. Используйте формат ГГГГ-ММ-ДД (например, 2024-01-15)")
    
    else:
        # Если это не команда и не ожидается ввод данных, показываем меню
        await update.message.reply_text(
            "Не понимаю эту команду. Используйте кнопки меню или /help для списка доступных команд.",
            reply_markup=get_main_menu_keyboard()
        )


async def show_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать приемы за сегодня"""
    user_id = update.effective_user.id
    medication_id = get_user_medication(user_id)
    medications = db.get_today_medications(medication_id=medication_id)
    
    message = f"📅 Приемы за сегодня ({date.today().strftime('%d.%m.%Y')}):\n\n"
    
    if not medications:
        message += "❌ Сегодня еще не было приемов препарата.\n\n"
    else:
        total_quantity = 0
        total_dosage = 0
        
        for time_str, quantity, dosage_mg in medications:
            total_dosage_single = quantity * dosage_mg
            total_quantity += quantity
            total_dosage += total_dosage_single
            message += f"🕐 {time_str}\n"
            message += f"   • Таблеток: {quantity}\n"
            message += f"   • Дозировка: {dosage_mg} мг × {quantity} = {total_dosage_single} мг\n\n"
        
        message += f"📊 Итого за день:\n"
        message += f"   • Всего таблеток: {total_quantity}\n"
        message += f"   • Общая дозировка: {total_dosage} мг\n\n"
    
    # Показываем сравнение с планом, если настройки курса установлены
    settings = db.get_active_course_settings(medication_id=medication_id)
    if settings:
        _, daily_quantity, dosage_mg, start_date_str, end_date_str, _ = settings
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        today = date.today()
        
        # Проверяем, что сегодня входит в период курса
        if today >= start_date and (not end_date_str or today <= datetime.strptime(end_date_str, "%Y-%m-%d").date()):
            planned_dosage = daily_quantity * dosage_mg
            taken_quantity = sum(qty for _, qty, _ in medications) if medications else 0
            taken_dosage = sum(qty * dmg for _, qty, dmg in medications) if medications else 0
            
            message += f"📋 План на сегодня:\n"
            message += f"   • Таблеток: {daily_quantity}\n"
            message += f"   • Дозировка: {planned_dosage} мг\n\n"
            
            if taken_quantity < daily_quantity:
                remaining = daily_quantity - taken_quantity
                message += f"⚠️ Осталось принять: {remaining} таблеток ({remaining * dosage_mg} мг)\n"
            elif taken_quantity == daily_quantity:
                message += f"✅ План выполнен!\n"
            else:
                excess = taken_quantity - daily_quantity
                message += f"⚠️ Превышение плана: +{excess} таблеток (+{excess * dosage_mg} мг)\n"
    
    await update.message.reply_text(message)


async def show_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать историю за последние 7 дней"""
    user_id = update.effective_user.id
    medication_id = get_user_medication(user_id)
    summary = db.get_medications_summary(days=7, medication_id=medication_id)
    total_stats = db.get_total_statistics(medication_id=medication_id)
    medication = db.get_medication(medication_id)
    med_name = medication[1] if medication else "Препарат"
    
    message = f"📊 История за последние 7 дней для препарата: {med_name}\n\n"
    
    if not summary:
        message += "❌ За последние 7 дней не было приемов препарата.\n\n"
    else:
        for date_str, data in summary.items():
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
            formatted_date = date_obj.strftime("%d.%m.%Y")
            message += f"📅 {formatted_date}\n"
            message += f"   • Таблеток: {data['quantity']}\n"
            message += f"   • Общая дозировка: {data['total_dosage_mg']} мг\n\n"
    
    # Добавляем общую статистику
    message += "📈 Общая статистика за все время по этому препарату:\n"
    message += f"   • Дней с приемом: {total_stats['total_days']}\n"
    message += f"   • Всего принято таблеток: {total_stats['total_quantity']}\n"
    message += f"   • Общая дозировка: {total_stats['total_dosage_mg']:.1f} мг"
    
    await update.message.reply_text(message)


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для настройки курса"""
    user_id = update.effective_user.id
    medication_id = get_user_medication(user_id)
    
    # Проверяем, есть ли уже активные настройки для текущего препарата
    current_settings = db.get_active_course_settings(medication_id=medication_id)
    
    if current_settings:
        _, daily_quantity, dosage_mg, start_date, end_date, _ = current_settings
        message = (
            "⚙️ Текущие настройки курса:\n\n"
            f"• Таблеток в день: {daily_quantity}\n"
            f"• Дозировка одной таблетки: {dosage_mg} мг\n"
            f"• Дата начала: {start_date}\n"
        )
        if end_date:
            message += f"• Дата окончания: {end_date}\n"
        else:
            message += "• Дата окончания: не ограничена\n"
        message += "\nВы хотите изменить настройки? Начните ввод заново."
        await update.message.reply_text(message)
    
    user_states[user_id] = {'action': 'waiting_daily_quantity'}
    await update.message.reply_text(
        "⚙️ Настройка курса приема препарата\n\n"
        "Сколько таблеток нужно принимать в день? (введите число)"
    )


async def progress_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать прогресс курса"""
    user_id = update.effective_user.id
    medication_id = get_user_medication(user_id)
    progress = db.get_course_progress(medication_id=medication_id)
    medication = db.get_medication(medication_id)
    med_name = medication[1] if medication else "Препарат"
    
    if not progress:
        await update.message.reply_text(
            "❌ Настройки курса не установлены.\n\n"
            "Используйте команду /settings для настройки курса."
        )
        return
    
    message = f"📊 Прогресс курса для препарата: {med_name}\n\n"
    message += f"📋 План:\n"
    message += f"• Таблеток в день: {progress['daily_quantity']}\n"
    message += f"• Дозировка одной таблетки: {progress['dosage_mg']} мг\n"
    message += f"• Дата начала: {progress['start_date']}\n"
    if progress['end_date']:
        message += f"• Дата окончания: {progress['end_date']}\n"
    else:
        message += "• Дата окончания: не ограничена\n"
    
    message += f"\n📈 Статистика:\n"
    message += f"• Дней прошло: {progress['days_passed']}\n"
    if progress['end_date']:
        message += f"• Всего дней курса: {progress['total_days']}\n"
    message += f"• Дней с приемом: {progress['days_with_medication']}\n"
    
    message += f"\n💊 Прием препарата:\n"
    message += f"• План: {progress['total_planned_quantity']} таблеток ({progress['total_planned_dosage']:.1f} мг)\n"
    message += f"• Принято: {progress['total_taken_quantity']} таблеток ({progress['total_taken_dosage']:.1f} мг)\n"
    
    completion = progress['completion_percentage']
    if completion >= 100:
        message += f"• Выполнение: ✅ {completion:.1f}%\n"
    elif completion >= 80:
        message += f"• Выполнение: 🟢 {completion:.1f}%\n"
    elif completion >= 50:
        message += f"• Выполнение: 🟡 {completion:.1f}%\n"
    else:
        message += f"• Выполнение: 🔴 {completion:.1f}%\n"
    
    await update.message.reply_text(message)


async def reminder_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню управления напоминаниями"""
    user_id = update.effective_user.id
    medication_id = get_user_medication(user_id)
    reminders = db.get_reminders(medication_id=medication_id)
    
    keyboard = []
    keyboard.append([InlineKeyboardButton("➕ Добавить напоминание", callback_data="add_reminder")])
    
    if reminders:
        message = "⏰ Активные напоминания:\n\n"
        # reminders: (id, time, medication_id)
        for reminder_id, time_str, _med_id in reminders:
            message += f"🕐 {time_str} [ID: {reminder_id}]\n"
            keyboard.append([
                InlineKeyboardButton(f"❌ Удалить {time_str}", callback_data=f"delete_reminder_{reminder_id}")
            ])
    else:
        message = "⏰ У вас пока нет активных напоминаний.\n\n"
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(message, reply_markup=reply_markup)


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на кнопки"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = query.from_user.id
    
    if data == "add_reminder":
        user_states[user_id] = {'action': 'waiting_reminder_time'}
        await query.edit_message_text(
            "⏰ Добавление напоминания\n\n"
            "Введите время в формате HH:MM (например, 09:30 или 21:00):"
        )
    
    elif data.startswith("delete_reminder_"):
        reminder_id = int(data.split("_")[2])
        success = db.delete_reminder(reminder_id)
        
        if success:
            await query.edit_message_text("✅ Напоминание удалено!")
        else:
            await query.edit_message_text("❌ Ошибка при удалении напоминания")
    
    elif data == "confirm_medication":
        # Начинаем процесс подтверждения приема из напоминания
        user_states[user_id] = {'action': 'waiting_quantity', 'from_reminder': True}
        await query.edit_message_text(
            "💊 Подтверждение приема препарата\n\n"
            "Сколько таблеток вы приняли? (введите число)"
        )
    
    elif data == "med_add":
        # Добавление нового препарата
        user_states[user_id] = {'action': 'waiting_med_name'}
        await query.edit_message_text(
            "🧴 Добавление нового препарата\n\n"
            "Введите название препарата:"
        )
    
    elif data.startswith("med_select_"):
        # Выбор текущего препарата
        try:
            med_id = int(data.split("_")[2])
            med = db.get_medication(med_id)
            if not med:
                await query.edit_message_text("❌ Препарат не найден.")
                return
            set_user_medication(user_id, med_id)
            await query.edit_message_text(
                f"✅ Текущий препарат установлен: {med[1]}"
            )
        except Exception:
            await query.edit_message_text("❌ Ошибка при выборе препарата.")


async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    """Отправка напоминания о приеме препарата"""
    user_id = int(os.getenv("USER_ID", "0"))
    if user_id == 0:
        logger.warning("USER_ID не установлен в .env файле")
        return
    
    reminders = db.get_reminders()
    current_time = datetime.now().strftime("%H:%M")
    
    # Логирование для отладки
    if reminders:
        logger.info(f"Проверка напоминаний. Текущее время: {current_time}, Напоминания: {[r[1] for r in reminders]}")
    else:
        logger.debug(f"Проверка напоминаний. Текущее время: {current_time}, Напоминаний нет")
    
    for reminder_id, time_str, medication_id in reminders:
        if time_str == current_time:
            logger.info(f"Найдено совпадение! Отправка напоминания на {time_str}")
            stats_file_path = None
            try:
                # Генерируем статистику в виде CSV файла
                with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as tmp_file:
                    stats_file_path = tmp_file.name
                
                success = db.generate_statistics_csv(
                    stats_file_path, days=30, medication_id=medication_id
                )
                
                if success and os.path.exists(stats_file_path) and os.path.getsize(stats_file_path) > 0:
                    # Проверяем, что файл не пустой (больше чем только заголовки)
                    try:
                        # Отправляем файл со статистикой
                        with open(stats_file_path, 'rb') as stats_file:
                            await context.bot.send_document(
                                chat_id=user_id,
                                document=stats_file,
                                filename=f"statistics_{datetime.now().strftime('%Y%m%d')}.csv",
                                caption="📊 Статистика приема препарата за последние 30 дней"
                            )
                    except Exception as e:
                        logger.warning(f"Не удалось отправить файл статистики: {e}")
                
                # Формируем сообщение с информацией о плане
                # Определяем название препарата
                med = db.get_medication(medication_id)
                med_name = med[1] if med else "препарат"
                
                reminder_text = f"⏰ Напоминание: пора принять {med_name}!\n\n"
                
                # Добавляем информацию о плане, если настройки курса установлены
                settings = db.get_active_course_settings(medication_id=medication_id)
                if settings:
                    _, daily_quantity, dosage_mg, start_date_str, end_date_str, _ = settings
                    start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
                    today = date.today()
                    
                    # Проверяем, что сегодня входит в период курса
                    if today >= start_date and (not end_date_str or today <= datetime.strptime(end_date_str, "%Y-%m-%d").date()):
                        # Получаем приемы за сегодня
                        today_medications = db.get_today_medications(medication_id=medication_id)
                        taken_today = sum(qty for _, qty, _ in today_medications) if today_medications else 0
                        remaining = daily_quantity - taken_today
                        
                        reminder_text += f"📋 План на сегодня: {daily_quantity} таблеток ({daily_quantity * dosage_mg} мг)\n"
                        reminder_text += f"✅ Уже принято: {taken_today} таблеток\n"
                        if remaining > 0:
                            reminder_text += f"⚠️ Осталось: {remaining} таблеток ({remaining * dosage_mg} мг)\n"
                        reminder_text += "\n"
                
                reminder_text += "Нажмите кнопку ниже, чтобы подтвердить прием."
                
                # Отправляем напоминание с кнопкой подтверждения
                keyboard = [[InlineKeyboardButton("✅ Подтвердить прием", callback_data="confirm_medication")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await context.bot.send_message(
                    chat_id=user_id,
                    text=reminder_text,
                    reply_markup=reply_markup
                )
                
                logger.info(f"✅ Отправлено напоминание на {time_str} со статистикой")
                
            except Exception as e:
                logger.error(f"Ошибка при отправке напоминания: {e}")
            finally:
                # Удаляем временный файл в любом случае
                if stats_file_path and os.path.exists(stats_file_path):
                    try:
                        os.unlink(stats_file_path)
                    except Exception as e:
                        logger.warning(f"Не удалось удалить временный файл: {e}")


def main():
    """Главная функция запуска бота"""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN не установлен в .env файле")
        return
    
    # Создание приложения
    application = Application.builder().token(token).build()
    
    # Регистрация обработчиков
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("menu", menu_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("add", add_medication))
    application.add_handler(CommandHandler("today", show_today))
    application.add_handler(CommandHandler("history", show_history))
    application.add_handler(CommandHandler("settings", settings_command))
    application.add_handler(CommandHandler("progress", progress_command))
    application.add_handler(CommandHandler("reminder", reminder_menu))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Настройка периодической проверки напоминаний
    job_queue = application.job_queue
    if job_queue:
        job_queue.run_repeating(
            send_reminder,
            interval=60,  # Проверка каждую минуту
            first=10
        )
        logger.info("✅ Периодическая проверка напоминаний настроена (каждую минуту)")
    else:
        logger.error("❌ Job queue недоступен! Напоминания не будут работать!")
    
    # Запуск бота
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"Бот запущен... Текущее время: {current_time}")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
