#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import re
import json
import logging
import threading
import calendar
import csv
import io
import time
import requests
from datetime import datetime, timedelta

from dotenv import load_dotenv
import telebot
from telebot import types
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, request, jsonify, send_from_directory

# Отключаем логирование Flask
import logging as flask_logging
flask_logging.getLogger('werkzeug').setLevel(flask_logging.ERROR)

# ==================== FLASK-СЕРВЕР ====================
app = Flask(__name__, static_folder='.', static_url_path='')

# Глобальные переменные
bot = None
sheet_clients = None
sheet_services = None
sheet_appointments = None
sheet_settings = None
sheet_services_archive = None
ADMIN_ID = 0

def get_setting_api(key, default=""):
    try:
        rows = sheet_settings.get_all_values()
        for r in rows[1:]:
            if len(r) >= 2 and r[0] == key:
                return r[1]
    except:
        pass
    return default

def get_active_services_api():
    rows = sheet_services.get_all_values()
    if len(rows) <= 1:
        return []
    services = []
    for r in rows[1:]:
        if len(r) >= 5 and r[4] == "Да":
            services.append({
                "id": r[0], 
                "name": r[1], 
                "duration": int(r[2]) if r[2] else 120, 
                "price": int(r[3]) if r[3] else 0
            })
    return services

def get_free_slots_api(date_str, duration):
    work_start = datetime.strptime(get_setting_api("work_start", "10:00"), "%H:%M")
    work_end = datetime.strptime(get_setting_api("work_end", "20:00"), "%H:%M")
    break_minutes = int(get_setting_api("break_minutes", "10"))
    
    rows = sheet_appointments.get_all_values()
    appointments = []
    for r in rows[1:]:
        if len(r) >= 10 and r[1] == date_str and r[9] == "Ожидание":
            appointments.append(r)
    
    busy_intervals = []
    for app in appointments:
        start = datetime.strptime(app[2], "%H:%M")
        end = start + timedelta(minutes=int(app[3]) + break_minutes)
        busy_intervals.append((start, end))
    
    busy_intervals.sort(key=lambda x: x[0])
    
    free_slots = []
    current_time = work_start
    
    for busy_start, busy_end in busy_intervals:
        while current_time + timedelta(minutes=duration) <= busy_start:
            free_slots.append(current_time.strftime("%H:%M"))
            current_time += timedelta(minutes=30)
        if current_time < busy_end:
            current_time = busy_end
    
    while current_time + timedelta(minutes=duration) <= work_end:
        free_slots.append(current_time.strftime("%H:%M"))
        current_time += timedelta(minutes=30)
    
    return sorted(list(set(free_slots)))

def add_client_api(name, phone, notes=""):
    rows = sheet_clients.get_all_values()
    new_id = str(len(rows))
    sheet_clients.append_row([new_id, name, phone, notes, "Обычный", "0", "0"])
    return new_id

def get_client_by_phone(phone):
    rows = sheet_clients.get_all_values()
    for r in rows[1:]:
        if len(r) >= 3 and r[2] == phone:
            return {"id": r[0], "name": r[1], "phone": r[2]}
    return None

def get_client_by_id_api(client_id):
    rows = sheet_clients.get_all_values()
    for r in rows[1:]:
        if len(r) > 0 and r[0] == str(client_id):
            return {"id": r[0], "name": r[1], "phone": r[2]}
    return None

def add_appointment_api(date, time_start, duration, client_id, service_id, service_text, price, notes=""):
    rows = sheet_appointments.get_all_values()
    app_id = str(len(rows))
    time_end = (datetime.strptime(time_start, "%H:%M") + timedelta(minutes=duration)).strftime("%H:%M")
    sheet_appointments.append_row([
        app_id, date, time_start, str(duration), time_end,
        str(client_id), str(service_id), service_text, str(price), "Ожидание", notes
    ])
    return app_id

# ==================== СТАТИЧЕСКИЕ ФАЙЛЫ ====================
@app.route('/')
def home():
    return send_from_directory('.', 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    if os.path.exists(filename):
        return send_from_directory('.', filename)
    return send_from_directory('.', 'index.html')

# ==================== API ЭНДПОИНТЫ ====================
@app.route('/api/settings', methods=['GET'])
def api_settings():
    return jsonify({
        "business_name": get_setting_api("business_name", "Мастер"),
        "address": get_setting_api("address", ""),
        "work_start": get_setting_api("work_start", "10:00"),
        "work_end": get_setting_api("work_end", "20:00")
    })

@app.route('/api/services', methods=['GET'])
def api_services():
    services = get_active_services_api()
    return jsonify({"services": services})

@app.route('/api/slots', methods=['GET'])
def api_slots():
    date = request.args.get('date')
    service_id = request.args.get('service_id')
    
    if not date:
        return jsonify({"error": "date is required"}), 400
    
    duration = 120
    if service_id:
        services = get_active_services_api()
        for s in services:
            if s['id'] == service_id:
                duration = s['duration']
                break
    
    slots = get_free_slots_api(date, duration)
    return jsonify({"slots": slots})

@app.route('/api/appointment', methods=['POST'])
def api_appointment():
    try:
        data = request.json
        logger.info(f"API appointment request: {data}")
        
        name = data.get('name')
        phone = data.get('phone')
        service_id = data.get('service_id')
        service_text = data.get('service_text', '')
        date = data.get('date')
        time = data.get('time')
        notes = data.get('notes', '')
        
        if not all([name, phone, date, time]):
            return jsonify({"error": "missing required fields"}), 400
        
        if not service_id and not service_text:
            return jsonify({"error": "service_id or service_text required"}), 400
        
        # Находим или создаём клиента
        client = get_client_by_phone(phone)
        if not client:
            client_id = add_client_api(name, phone, notes)
            client = {"id": client_id, "name": name}
        else:
            client_id = client['id']
        
        price = 0
        duration = int(get_setting_api("default_duration", "120"))
        
        if service_id:
            services = get_active_services_api()
            for s in services:
                if s['id'] == service_id:
                    service_text = s['name']
                    price = s['price']
                    duration = s['duration']
                    break
        
        app_id = add_appointment_api(date, time, duration, client_id, service_id or "0", service_text, price, notes)
        
        # Уведомление мастеру
        business_name = get_setting_api("business_name", "Мастер")
        msg = f"🆕 Новая запись через Mini App!\n\n"
        msg += f"👤 {name}\n"
        msg += f"📞 {phone}\n"
        msg += f"💇‍♀️ {service_text}\n"
        msg += f"📅 {date} в {time}\n"
        msg += f"💰 {price} BYN"
        if notes:
            msg += f"\n📝 {notes}"
        
        try:
            if ADMIN_ID:
                bot.send_message(ADMIN_ID, msg)
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления: {e}")
        
        return jsonify({
            "success": True,
            "appointment_id": app_id,
            "message": "Запись успешно создана!"
        })
    except Exception as e:
        logger.error(f"API appointment error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/appointment/find', methods=['GET'])
def api_find_appointment():
    query = request.args.get('query', '')
    if not query:
        return jsonify({"error": "query required"}), 400
    
    rows = sheet_appointments.get_all_values()
    for r in rows[1:]:
        if len(r) >= 10:
            # Поиск по ID записи или по телефону клиента
            client = get_client_by_id_api(r[5]) if len(r) > 5 else None
            if r[0] == query or (client and query in client.get('phone', '')):
                return jsonify({
                    "appointment": {
                        "id": r[0],
                        "date": r[1],
                        "time": r[2],
                        "duration": r[3],
                        "service": r[7],
                        "price": r[8],
                        "status": r[9],
                        "notes": r[10] if len(r) > 10 else "",
                        "client_name": client['name'] if client else "",
                        "client_phone": client['phone'] if client else ""
                    }
                })
    
    return jsonify({"appointment": None})

@app.route('/api/appointment/cancel', methods=['POST'])
def api_cancel_appointment():
    try:
        data = request.json
        app_id = data.get('appointment_id')
        
        if not app_id:
            return jsonify({"error": "appointment_id required"}), 400
        
        # Обновляем статус
        cell = sheet_appointments.find(str(app_id), in_column=1)
        if cell:
            sheet_appointments.update_cell(cell.row, 10, "Отмена")
            
            # Уведомление мастеру
            app = None
            for r in sheet_appointments.get_all_values()[1:]:
                if len(r) > 0 and r[0] == str(app_id):
                    app = r
                    break
            
            if app and ADMIN_ID:
                client = get_client_by_id_api(app[5]) if len(app) > 5 else None
                msg = f"❌ Запись #{app_id} отменена через Mini App\n"
                msg += f"👤 {client['name'] if client else 'Клиент'}\n"
                msg += f"📅 {app[1]} в {app[2]}"
                bot.send_message(ADMIN_ID, msg)
            
            return jsonify({"success": True})
        
        return jsonify({"error": "Appointment not found"}), 404
    except Exception as e:
        logger.error(f"API cancel error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/appointment/reschedule', methods=['POST'])
def api_reschedule_appointment():
    try:
        data = request.json
        app_id = data.get('appointment_id')
        new_date = data.get('date')
        new_time = data.get('time')
        
        if not all([app_id, new_date, new_time]):
            return jsonify({"error": "missing required fields"}), 400
        
        # Находим старую запись
        old_app = None
        for r in sheet_appointments.get_all_values()[1:]:
            if len(r) > 0 and r[0] == str(app_id):
                old_app = r
                break
        
        if not old_app:
            return jsonify({"error": "Appointment not found"}), 404
        
        # Создаём новую запись
        new_id = add_appointment_api(
            new_date, new_time, 
            int(old_app[3]), old_app[5], old_app[6], old_app[7], old_app[8],
            f"(перенесено с {old_app[1]} {old_app[2]})"
        )
        
        # Отмечаем старую как перенесённую
        cell = sheet_appointments.find(str(app_id), in_column=1)
        if cell:
            sheet_appointments.update_cell(cell.row, 10, "Перенесена")
        
        # Уведомление мастеру
        if ADMIN_ID:
            client = get_client_by_id_api(old_app[5]) if len(old_app) > 5 else None
            msg = f"🔄 Запись #{app_id} перенесена\n"
            msg += f"👤 {client['name'] if client else 'Клиент'}\n"
            msg += f"📅 {old_app[1]} {old_app[2]} → {new_date} {new_time}"
            bot.send_message(ADMIN_ID, msg)
        
        return jsonify({"success": True, "new_appointment_id": new_id})
    except Exception as e:
        logger.error(f"API reschedule error: {e}")
        return jsonify({"error": str(e)}), 500

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

# ==================== НАСТРОЙКИ ====================
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
SHEET_ID = os.getenv("SHEET_ID")
GOOGLE_CREDS_JSON = os.getenv("GOOGLE_CREDENTIALS")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

if not GOOGLE_CREDS_JSON:
    raise ValueError("❌ GOOGLE_CREDENTIALS не задан в переменных окружения")

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_dict = json.loads(GOOGLE_CREDS_JSON)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
sh = client.open_by_key(SHEET_ID)

# Листы
try:
    sheet_clients = sh.worksheet("Клиенты")
except:
    sheet_clients = sh.add_worksheet(title="Клиенты", rows=1000, cols=10)
    sheet_clients.append_row(["ID", "Имя", "Телефон", "Заметки", "Статус", "Визиты", "Сумма"])

try:
    sheet_services = sh.worksheet("Услуги")
except:
    sheet_services = sh.add_worksheet(title="Услуги", rows=100, cols=5)
    sheet_services.append_row(["ID", "Название", "Длительность (мин)", "Цена", "Активна"])

try:
    sheet_services_archive = sh.worksheet("Услуги_архив")
except:
    sheet_services_archive = sh.add_worksheet(title="Услуги_архив", rows=1000, cols=6)
    sheet_services_archive.append_row(["Дата", "Действие", "ID", "Название", "Длительность", "Цена"])

try:
    sheet_appointments = sh.worksheet("Записи")
except:
    sheet_appointments = sh.add_worksheet(title="Записи", rows=1000, cols=12)
    sheet_appointments.append_row(["ID", "Дата", "Время начала", "Длительность", "Время конца", 
                                   "Клиент ID", "Услуга ID", "Услуга (текст)", "Цена", "Статус", "Заметка"])

try:
    sheet_settings = sh.worksheet("Настройки")
except:
    sheet_settings = sh.add_worksheet(title="Настройки", rows=50, cols=2)
    sheet_settings.append_row(["Ключ", "Значение"])
    default_settings = [
        ["business_name", "Мастер"],
        ["address", ""],
        ["work_days", "Пн,Вт,Ср,Чт,Пт,Сб"],
        ["work_start", "10:00"],
        ["work_end", "20:00"],
        ["break_minutes", "10"],
        ["default_duration", "120"],
        ["reminder_client_hours", "24"],
        ["reminder_master_hours", "1"],
    ]
    for key, value in default_settings:
        sheet_settings.append_row([key, value])

bot = telebot.TeleBot(BOT_TOKEN)
scheduler = BackgroundScheduler()

user_state = {}
user_data = {}

# ==================== ПРОВЕРКА АДМИНА ====================
def is_admin(message_or_call):
    if ADMIN_ID == 0:
        return True
    if hasattr(message_or_call, 'chat'):
        user_id = message_or_call.chat.id
    elif hasattr(message_or_call, 'message'):
        user_id = message_or_call.message.chat.id
    else:
        return False
    return user_id == ADMIN_ID

# ==================== РАБОТА С НАСТРОЙКАМИ ====================
def get_setting(key, default=""):
    try:
        rows = sheet_settings.get_all_values()
        for r in rows[1:]:
            if len(r) >= 2 and r[0] == key:
                return r[1]
    except:
        pass
    return default

def update_setting(key, value):
    try:
        cell = sheet_settings.find(key, in_column=1)
        if cell:
            sheet_settings.update_cell(cell.row, 2, str(value))
            return True
    except:
        pass
    return False

# ==================== ОЧИСТКА ТЕЛЕФОНА ====================
def clean_phone(phone):
    if not phone:
        return ""
    digits = re.sub(r'\D', '', phone)
    if digits.startswith('80') and len(digits) >= 11:
        digits = '375' + digits[2:]
    elif digits.startswith('8') and len(digits) == 11:
        digits = '7' + digits[1:]
    if digits.startswith('375') and len(digits) == 12:
        display = f"+{digits[:3]} {digits[3:5]} {digits[5:8]}-{digits[8:10]}-{digits[10:12]}"
    elif digits.startswith('7') and len(digits) == 11:
        display = f"+{digits[0]} {digits[1:4]} {digits[4:7]}-{digits[7:9]}-{digits[9:11]}"
    else:
        display = digits
    return display

def format_phone_for_markdown(phone):
    if not phone or phone == "—":
        return "—"
    display = clean_phone(phone)
    if not display:
        return phone
    digits = re.sub(r'\D', '', display)
    return f"[{display}](tel:+{digits})"

# ==================== КАЛЕНДАРЬ ====================
def get_calendar_keyboard(year=None, month=None, callback_prefix="calpick"):
    now = datetime.now()
    if year is None:
        year = now.year
    if month is None:
        month = now.month
    month_names = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
                   'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь']
    kb = types.InlineKeyboardMarkup(row_width=7)
    kb.add(types.InlineKeyboardButton(f"{month_names[month-1]} {year}", callback_data="ignore"))
    days_row = [types.InlineKeyboardButton(d, callback_data="ignore") for d in ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']]
    kb.add(*days_row)
    cal = calendar.monthcalendar(year, month)
    for week in cal:
        row = []
        for day in week:
            if day == 0:
                row.append(types.InlineKeyboardButton(" ", callback_data="ignore"))
            else:
                date_str = f"{year}-{month:02d}-{day:02d}"
                row.append(types.InlineKeyboardButton(str(day), callback_data=f"{callback_prefix}_{date_str}"))
        kb.add(*row)
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1
    nav_row = [
        types.InlineKeyboardButton("<<", callback_data=f"cal_{prev_year}_{prev_month}_{callback_prefix}"),
        types.InlineKeyboardButton(">>", callback_data=f"cal_{next_year}_{next_month}_{callback_prefix}")
    ]
    kb.add(*nav_row)
    today = now.strftime("%Y-%m-%d")
    tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    quick_row = [
        types.InlineKeyboardButton("📅 Сегодня", callback_data=f"{callback_prefix}_{today}"),
        types.InlineKeyboardButton("📅 Завтра", callback_data=f"{callback_prefix}_{tomorrow}")
    ]
    kb.add(*quick_row)
    return kb

# ==================== РАБОТА С КЛИЕНТАМИ ====================
def get_next_client_id():
    rows = sheet_clients.get_all_values()
    if len(rows) <= 1:
        return 1
    ids = []
    for r in rows[1:]:
        if r and r[0] and r[0].isdigit():
            ids.append(int(r[0]))
    return max(ids) + 1 if ids else 1

def add_client(name, phone, notes=""):
    client_id = get_next_client_id()
    sheet_clients.append_row([str(client_id), name, phone, notes, "Обычный", "0", "0"])
    return client_id

def get_client_by_id(client_id):
    rows = sheet_clients.get_all_values()
    for r in rows[1:]:
        if len(r) > 0 and r[0] == str(client_id):
            while len(r) < 7:
                r.append("")
            return {"id": r[0], "name": r[1], "phone": r[2], "notes": r[3], "status": r[4], "visits": r[5], "total": r[6]}
    return None

def get_all_clients():
    rows = sheet_clients.get_all_values()
    if len(rows) <= 1:
        return []
    clients = []
    for r in rows[1:]:
        if len(r) >= 1 and r[0]:
            while len(r) < 7:
                r.append("")
            clients.append({"id": r[0], "name": r[1], "phone": r[2], "notes": r[3], "status": r[4], "visits": r[5], "total": r[6]})
    return clients

def search_clients(query):
    clients = get_all_clients()
    q = query.lower().strip()
    result = []
    for c in clients:
        if q in c["name"].lower() or q in c["phone"] or q == c["id"]:
            result.append(c)
    return result

def update_client_field(client_id, field_col, value):
    try:
        cell = sheet_clients.find(str(client_id), in_column=1)
        if cell:
            sheet_clients.update_cell(cell.row, field_col, str(value))
            return True
    except:
        pass
    return False

def update_client_stats(client_id):
    rows = sheet_appointments.get_all_values()
    visits = 0
    total = 0
    for r in rows[1:]:
        if len(r) >= 10 and r[5] == str(client_id) and r[9] == "Выполнена":
            visits += 1
            try:
                total += float(r[8]) if r[8] else 0
            except:
                pass
    update_client_field(client_id, 6, str(visits))
    update_client_field(client_id, 7, str(int(total)))
    
    if visits >= 10:
        update_client_field(client_id, 5, "VIP")
    elif visits >= 5:
        update_client_field(client_id, 5, "Постоянный")

# ==================== РАБОТА С УСЛУГАМИ ====================
def get_next_service_id():
    rows = sheet_services.get_all_values()
    if len(rows) <= 1:
        return 1
    ids = []
    for r in rows[1:]:
        if r and r[0] and r[0].isdigit():
            ids.append(int(r[0]))
    return max(ids) + 1 if ids else 1

def add_service(name, duration, price):
    service_id = get_next_service_id()
    sheet_services.append_row([str(service_id), name, str(duration), str(price), "Да"])
    sheet_services_archive.append_row([datetime.now().strftime("%d.%m.%Y %H:%M"), "Создана", str(service_id), name, str(duration), str(price)])
    return service_id

def get_active_services():
    rows = sheet_services.get_all_values()
    if len(rows) <= 1:
        return []
    services = []
    for r in rows[1:]:
        if len(r) >= 5 and r[4] == "Да":
            services.append({"id": r[0], "name": r[1], "duration": int(r[2]) if r[2] else 120, "price": int(r[3]) if r[3] else 0})
    return services

def get_all_services():
    rows = sheet_services.get_all_values()
    if len(rows) <= 1:
        return []
    services = []
    for r in rows[1:]:
        if len(r) >= 5:
            services.append({"id": r[0], "name": r[1], "duration": int(r[2]) if r[2] else 120, "price": int(r[3]) if r[3] else 0, "active": r[4] == "Да"})
    return services

def get_service_by_id(service_id):
    services = get_all_services()
    for s in services:
        if s["id"] == str(service_id):
            return s
    return None

def update_service_field(service_id, field_col, value):
    try:
        cell = sheet_services.find(str(service_id), in_column=1)
        if cell:
            sheet_services.update_cell(cell.row, field_col, str(value))
            return True
    except:
        pass
    return False

def delete_service(service_id):
    service = get_service_by_id(service_id)
    if service:
        update_service_field(service_id, 5, "Нет")
        sheet_services_archive.append_row([datetime.now().strftime("%d.%m.%Y %H:%M"), "Удалена", str(service_id), service["name"], str(service["duration"]), str(service["price"])])
        return True
    return False

def restore_services_from_archive():
    services = get_all_services()
    active_services = [s for s in services if s["active"]]
    if active_services:
        return
    
    rows = sheet_services_archive.get_all_values()
    if len(rows) <= 1:
        return
    
    latest = {}
    for r in rows[1:]:
        if len(r) >= 6:
            action = r[1]
            service_id = r[2]
            name = r[3]
            duration = r[4]
            price = r[5]
            if action in ["Создана", "Изменена"]:
                latest[service_id] = {"name": name, "duration": duration, "price": price}
            elif action == "Удалена":
                if service_id in latest:
                    del latest[service_id]
    
    for service_id, data in latest.items():
        sheet_services.append_row([service_id, data["name"], data["duration"], data["price"], "Да"])
    
    logger.info(f"Восстановлено {len(latest)} услуг из архива")

# ==================== РАБОТА С ЗАПИСЯМИ ====================
def get_next_appointment_id():
    rows = sheet_appointments.get_all_values()
    if len(rows) <= 1:
        return 1
    ids = []
    for r in rows[1:]:
        if r and r[0] and r[0].isdigit():
            ids.append(int(r[0]))
    return max(ids) + 1 if ids else 1

def add_appointment(date, time_start, duration, client_id, service_id, service_text, price, notes=""):
    app_id = get_next_appointment_id()
    time_end = (datetime.strptime(time_start, "%H:%M") + timedelta(minutes=duration)).strftime("%H:%M")
    sheet_appointments.append_row([
        str(app_id), date, time_start, str(duration), time_end,
        str(client_id), str(service_id), service_text, str(price), "Ожидание", notes
    ])
    update_client_stats(client_id)
    return app_id

def get_appointments_by_date(date_str):
    rows = sheet_appointments.get_all_values()
    if len(rows) <= 1:
        return []
    result = []
    for r in rows[1:]:
        if len(r) >= 10 and r[1] == date_str and r[9] in ["Ожидание"]:
            result.append(r)
    return result

def get_appointment_by_id(app_id):
    rows = sheet_appointments.get_all_values()
    for r in rows[1:]:
        if len(r) > 0 and r[0] == str(app_id):
            while len(r) < 11:
                r.append("")
            return r
    return None

def get_all_active_appointments():
    rows = sheet_appointments.get_all_values()
    if len(rows) <= 1:
        return []
    result = []
    for r in rows[1:]:
        if len(r) >= 10 and r[9] == "Ожидание":
            result.append(r)
    return result

def update_appointment_field(app_id, field_col, value):
    try:
        cell = sheet_appointments.find(str(app_id), in_column=1)
        if cell:
            sheet_appointments.update_cell(cell.row, field_col, str(value))
            return True
    except:
        pass
    return False

def update_appointment_status(app_id, status):
    if update_appointment_field(app_id, 10, status):
        app = get_appointment_by_id(app_id)
        if app and len(app) > 5:
            update_client_stats(app[5])
        return True
    return False

def cancel_appointment(app_id, reason=""):
    if update_appointment_status(app_id, "Отмена"):
        if reason:
            update_appointment_field(app_id, 11, f"Отмена: {reason}")
        return True
    return False

def reschedule_appointment(app_id, new_date, new_time):
    app = get_appointment_by_id(app_id)
    if not app:
        return None
    
    old_note = app[10] if len(app) > 10 else ""
    new_note = f"{old_note}\n(перенесено с {app[1]} {app[2]})".strip()
    
    new_id = add_appointment(
        new_date, new_time, int(app[3]), app[5], app[6], app[7], app[8], new_note
    )
    update_appointment_status(app_id, "Перенесена")
    return new_id

def is_time_available(date_str, time_start, duration, exclude_app_id=None):
    new_start = datetime.strptime(time_start, "%H:%M")
    new_end = new_start + timedelta(minutes=duration)
    
    work_start = datetime.strptime(get_setting("work_start", "10:00"), "%H:%M")
    work_end = datetime.strptime(get_setting("work_end", "20:00"), "%H:%M")
    
    if new_start < work_start or new_end > work_end:
        return False, "Вне рабочего времени"
    
    appointments = get_appointments_by_date(date_str)
    break_minutes = int(get_setting("break_minutes", "10"))
    
    for app in appointments:
        if exclude_app_id and app[0] == str(exclude_app_id):
            continue
        app_start = datetime.strptime(app[2], "%H:%M")
        app_end = app_start + timedelta(minutes=int(app[3]) + break_minutes)
        
        if new_start < app_end and new_end > app_start:
            return False, f"Пересекается с записью #{app[0]}"
    
    return True, None

def get_free_slots(date_str, duration):
    work_start = datetime.strptime(get_setting("work_start", "10:00"), "%H:%M")
    work_end = datetime.strptime(get_setting("work_end", "20:00"), "%H:%M")
    break_minutes = int(get_setting("break_minutes", "10"))
    
    appointments = get_appointments_by_date(date_str)
    
    busy_intervals = []
    for app in appointments:
        start = datetime.strptime(app[2], "%H:%M")
        end = start + timedelta(minutes=int(app[3]) + break_minutes)
        busy_intervals.append((start, end))
    
    busy_intervals.sort(key=lambda x: x[0])
    
    free_slots = []
    current_time = work_start
    
    for busy_start, busy_end in busy_intervals:
        while current_time + timedelta(minutes=duration) <= busy_start:
            free_slots.append(current_time.strftime("%H:%M"))
            current_time += timedelta(minutes=30)
        if current_time < busy_end:
            current_time = busy_end
    
    while current_time + timedelta(minutes=duration) <= work_end:
        free_slots.append(current_time.strftime("%H:%M"))
        current_time += timedelta(minutes=30)
    
    return sorted(list(set(free_slots)))

# ==================== ГЛАВНОЕ МЕНЮ ====================
def main_menu():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row("➕ Новая запись", "🔍 Найти клиента")
    keyboard.row("📅 Сегодня", "📅 Завтра")
    keyboard.row("📋 Все записи", "👥 Клиенты")
    keyboard.row("💇‍♀️ Мои услуги", "📊 Статистика")
    keyboard.row("⚙️ Настройки", "📊 Таблица")
    keyboard.row("📱 Mini App")
    return keyboard

# ==================== КНОПКИ ====================
def appointment_action_buttons(app_id):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("✅ Выполнена", callback_data=f"app_done_{app_id}"),
        types.InlineKeyboardButton("✏️ Ред.", callback_data=f"app_edit_{app_id}")
    )
    kb.add(
        types.InlineKeyboardButton("🔄 Перенести", callback_data=f"app_reschedule_{app_id}"),
        types.InlineKeyboardButton("❌ Отмена", callback_data=f"app_cancel_{app_id}")
    )
    kb.add(
        types.InlineKeyboardButton("📋 Сообщение клиенту", callback_data=f"app_msg_{app_id}")
    )
    return kb

def client_card_keyboard(client_id):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("📅 Новая запись", callback_data=f"client_app_{client_id}"),
        types.InlineKeyboardButton("📋 История", callback_data=f"client_history_{client_id}")
    )
    kb.add(
        types.InlineKeyboardButton("✏️ Редактировать", callback_data=f"client_edit_{client_id}"),
        types.InlineKeyboardButton("📝 Заметка", callback_data=f"client_note_{client_id}")
    )
    return kb

# ==================== УВЕДОМЛЕНИЯ ====================
def check_reminders():
    now = datetime.now()
    rows = sheet_appointments.get_all_values()
    
    for r in rows[1:]:
        if len(r) < 10 or r[9] != "Ожидание":
            continue
        
        try:
            app_date = r[1]
            app_time = r[2]
            app_datetime = datetime.strptime(f"{app_date} {app_time}", "%Y-%m-%d %H:%M")
            time_left = (app_datetime - now).total_seconds() / 3600
            
            client_id = r[5]
            client = get_client_by_id(client_id)
            
            reminder_master = int(get_setting("reminder_master_hours", "1"))
            
            if reminder_master - 0.5 < time_left <= reminder_master + 0.5:
                msg = f"🔔 Запись через {reminder_master} час!\n\n"
                msg += f"👤 {client['name'] if client else 'Клиент'}\n"
                msg += f"📞 {client['phone'] if client else ''}\n"
                msg += f"💇‍♀️ {r[7]}\n"
                msg += f"📅 Сегодня в {app_time}\n"
                msg += f"💰 {r[8]} BYN"
                bot.send_message(ADMIN_ID, msg)
                
        except:
            pass

# ==================== ОБРАБОТЧИКИ КОМАНД ====================
@bot.message_handler(commands=['start'])
def cmd_start(message):
    chat_id = message.chat.id
    user_state[chat_id] = None
    user_data[chat_id] = {}
    
    if is_admin(message):
        restore_services_from_archive()
        business_name = get_setting("business_name", "Мастер")
        bot.send_message(
            chat_id,
            f"🔥 CRM {business_name}\n\nВыберите действие:",
            reply_markup=main_menu()
        )
    else:
        business_name = get_setting("business_name", "Мастер")
        address = get_setting("address", "")
        
        msg = f"💇‍♀️ **{business_name}**\n"
        if address:
            msg += f"📍 {address}\n"
        msg += "\nДобро пожаловать! Запишитесь онлайн 👇"
        
        kb = types.InlineKeyboardMarkup()
        app_url = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME', 'your-app.onrender.com')}"
        kb.add(types.InlineKeyboardButton(
            "📱 Записаться онлайн",
            web_app=types.WebAppInfo(url=app_url)
        ))
        
        bot.send_message(chat_id, msg, reply_markup=kb, parse_mode='Markdown')

# ==================== ОБРАБОТКА СООБЩЕНИЙ ====================
@bot.message_handler(func=lambda m: True)
def handle_message(message):
    chat_id = message.chat.id
    text = message.text
    
    if chat_id not in user_state:
        user_state[chat_id] = None
        user_data[chat_id] = {}
    
    if not is_admin(message):
        business_name = get_setting("business_name", "Мастер")
        kb = types.InlineKeyboardMarkup()
        app_url = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME', 'your-app.onrender.com')}"
        kb.add(types.InlineKeyboardButton(
            "📱 Записаться онлайн",
            web_app=types.WebAppInfo(url=app_url)
        ))
        bot.send_message(
            chat_id,
            f"💇‍♀️ **{business_name}**\n\nНажмите кнопку ниже, чтобы записаться 👇",
            reply_markup=kb,
            parse_mode='Markdown'
        )
        return
    
    state = user_state.get(chat_id)
    
    if text == "➕ Новая запись":
        user_state[chat_id] = "APPT_SEARCH_CLIENT"
        bot.send_message(chat_id, "🔍 Введите имя или телефон клиента (или создайте нового):")
        return
    
    elif text == "🔍 Найти клиента":
        user_state[chat_id] = "SEARCH_CLIENT"
        bot.send_message(chat_id, "🔍 Введите имя или телефон клиента:")
        return
    
    elif text == "👥 Клиенты":
        show_all_clients(chat_id)
        return
    
    elif text == "📅 Сегодня":
        today = datetime.now().strftime("%Y-%m-%d")
        show_appointments_by_date(chat_id, today, "сегодня")
        return
    
    elif text == "📅 Завтра":
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        show_appointments_by_date(chat_id, tomorrow, "завтра")
        return
    
    elif text == "📋 Все записи":
        appointments = get_all_active_appointments()
        if not appointments:
            bot.send_message(chat_id, "📭 Нет активных записей.", reply_markup=main_menu())
        else:
            bot.send_message(chat_id, f"📋 Активных записей: {len(appointments)}")
            for app in sorted(appointments, key=lambda x: (x[1], x[2]))[:10]:
                show_appointment_card(chat_id, app)
        return
    
    elif text == "💇‍♀️ Мои услуги":
        show_services_list(chat_id)
        return
    
    elif text == "📊 Статистика":
        show_statistics(chat_id)
        return
    
    elif text == "⚙️ Настройки":
        show_settings_menu(chat_id)
        return
    
    elif text == "📊 Таблица":
        sheet_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}"
        bot.send_message(chat_id, f"📊 Ссылка на таблицу:\n{sheet_url}", reply_markup=main_menu())
        return
    
    elif text == "📱 Mini App":
        app_url = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME', 'your-app.onrender.com')}"
        bot.send_message(chat_id, "Нажмите кнопку ниже:", reply_markup=types.InlineKeyboardMarkup().add(
            types.InlineKeyboardButton("📱 Открыть запись", web_app=types.WebAppInfo(url=app_url))
        ))
        return
    
    elif text == "🏠 Главное меню":
        user_state[chat_id] = None
        bot.send_message(chat_id, "Главное меню:", reply_markup=main_menu())
        return

# ==================== ФУНКЦИИ ОТОБРАЖЕНИЯ ====================
def show_all_clients(chat_id):
    clients = get_all_clients()
    if not clients:
        bot.send_message(chat_id, "📭 Нет клиентов.", reply_markup=main_menu())
        return
    
    kb = types.InlineKeyboardMarkup(row_width=1)
    for c in clients[:20]:
        btn_text = f"{c['name']} ({c['phone']}) - {c['status']}"
        kb.add(types.InlineKeyboardButton(btn_text, callback_data=f"client_view_{c['id']}"))
    
    if len(clients) > 20:
        kb.add(types.InlineKeyboardButton(f"... и ещё {len(clients)-20}", callback_data="ignore"))
    kb.add(types.InlineKeyboardButton("➕ Новый клиент", callback_data="client_new"))
    kb.add(types.InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu"))
    
    bot.send_message(chat_id, f"👥 Все клиенты ({len(clients)}):", reply_markup=kb)

def show_client_selection(chat_id, clients, for_appointment=False):
    kb = types.InlineKeyboardMarkup(row_width=1)
    for c in clients[:10]:
        prefix = "appt" if for_appointment else "client"
        kb.add(types.InlineKeyboardButton(
            f"{c['name']} ({c['phone']})",
            callback_data=f"{prefix}_select_{c['id']}"
        ))
    kb.add(types.InlineKeyboardButton("➕ Новый клиент", callback_data="appt_new_client" if for_appointment else "client_new"))
    bot.send_message(chat_id, "👥 Выберите клиента:", reply_markup=kb)

def show_client_card_by_id(chat_id, client_id):
    client = get_client_by_id(client_id)
    if client:
        show_client_card(chat_id, client)

def show_client_card(chat_id, client):
    status_emoji = {"Обычный": "⭐", "Постоянный": "⭐⭐", "VIP": "👑"}.get(client["status"], "⭐")
    
    msg = f"👤 **{client['name']}**\n"
    msg += f"📞 {format_phone_for_markdown(client['phone'])}\n"
    msg += f"{status_emoji} {client['status']}\n"
    msg += f"📋 Визитов: {client['visits']}\n"
    msg += f"💰 Сумма: {client['total']} BYN"
    if client['notes']:
        msg += f"\n\n📝 **Заметки:**\n{client['notes']}"
    
    rows = sheet_appointments.get_all_values()
    history = []
    for r in rows[1:]:
        if len(r) >= 10 and r[5] == str(client['id']):
            history.append(r)
    
    if history:
        msg += f"\n\n📋 **Последние записи:**\n"
        for app in sorted(history, key=lambda x: f"{x[1]} {x[2]}", reverse=True)[:5]:
            status_icon = {"Ожидание": "🟡", "Выполнена": "✅", "Отмена": "❌", "Перенесена": "🔄"}.get(app[9], "")
            msg += f"{status_icon} {app[1]} {app[2]} — {app[7]} ({app[8]} BYN)\n"
    
    bot.send_message(chat_id, msg, reply_markup=client_card_keyboard(client['id']), parse_mode='Markdown')

def show_appointments_by_date(chat_id, date_str, label):
    appointments = get_appointments_by_date(date_str)
    if not appointments:
        bot.send_message(chat_id, f"📭 Нет записей на {label}.", reply_markup=main_menu())
        return
    
    bot.send_message(chat_id, f"📅 Записи на {label}: {len(appointments)}")
    for app in sorted(appointments, key=lambda x: x[2]):
        show_appointment_card(chat_id, app)

def show_appointment_card(chat_id, app):
    client = get_client_by_id(app[5]) if len(app) > 5 else None
    client_name = client['name'] if client else "Клиент"
    client_phone = client['phone'] if client else ""
    
    msg = f"📋 **Запись #{app[0]}**\n"
    msg += f"👤 {client_name}\n"
    if client_phone:
        msg += f"📞 {format_phone_for_markdown(client_phone)}\n"
    msg += f"💇‍♀️ {app[7]}\n"
    msg += f"📅 {app[1]} {app[2]}\n"
    msg += f"⏰ {app[3]} минут\n"
    msg += f"💰 {app[8]} BYN\n"
    msg += f"🔄 {app[9]}"
    if len(app) > 10 and app[10]:
        msg += f"\n📝 {app[10]}"
    
    bot.send_message(chat_id, msg, reply_markup=appointment_action_buttons(app[0]), parse_mode='Markdown')

def show_services_list(chat_id):
    services = get_all_services()
    active = [s for s in services if s["active"]]
    inactive = [s for s in services if not s["active"]]
    
    msg = "💇‍♀️ **Мои услуги**\n\n"
    msg += "🟢 **Активные:**\n"
    for s in active:
        msg += f"{s['id']}. {s['name']} — {s['duration']} мин / {s['price']} BYN\n"
    
    if inactive:
        msg += "\n🔴 **Скрытые:**\n"
        for s in inactive:
            msg += f"{s['id']}. {s['name']}\n"
    
    kb = types.InlineKeyboardMarkup(row_width=1)
    for s in active:
        kb.add(types.InlineKeyboardButton(f"✏️ {s['name']}", callback_data=f"service_edit_{s['id']}"))
    kb.add(
        types.InlineKeyboardButton("➕ Добавить услугу", callback_data="service_add"),
        types.InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
    )
    
    bot.send_message(chat_id, msg, reply_markup=kb, parse_mode='Markdown')

def show_service_selection(chat_id, services):
    kb = types.InlineKeyboardMarkup(row_width=1)
    for s in services:
        kb.add(types.InlineKeyboardButton(
            f"{s['name']} — {s['duration']} мин / {s['price']} BYN",
            callback_data=f"appt_service_{s['id']}"
        ))
    kb.add(types.InlineKeyboardButton("📝 Другая услуга", callback_data="appt_service_manual"))
    bot.send_message(chat_id, "💇‍♀️ Выберите услугу:", reply_markup=kb)

def show_statistics(chat_id):
    now = datetime.now()
    month_start = now.replace(day=1).strftime("%Y-%m-%d")
    
    rows = sheet_appointments.get_all_values()
    
    today = now.strftime("%Y-%m-%d")
    today_income = 0
    today_count = 0
    month_income = 0
    month_count = 0
    cancelled = 0
    
    for r in rows[1:]:
        if len(r) < 10:
            continue
        date = r[1]
        status = r[9]
        try:
            price = float(r[8]) if r[8] else 0
        except:
            price = 0
        
        if status == "Выполнена":
            if date == today:
                today_income += price
                today_count += 1
            if date >= month_start:
                month_income += price
                month_count += 1
        elif status == "Отмена":
            cancelled += 1
    
    msg = "📊 **Статистика**\n\n"
    msg += f"📅 **Сегодня:**\n"
    msg += f"Записей: {today_count}\n"
    msg += f"Доход: {int(today_income)} BYN\n\n"
    msg += f"📆 **За месяц:**\n"
    msg += f"Записей: {month_count}\n"
    msg += f"Доход: {int(month_income)} BYN\n\n"
    msg += f"❌ Отмен за месяц: {cancelled}"
    
    bot.send_message(chat_id, msg, reply_markup=main_menu(), parse_mode='Markdown')

def show_settings_menu(chat_id):
    msg = "⚙️ **Настройки**\n\n"
    msg += f"🏷️ Название: {get_setting('business_name', 'Мастер')}\n"
    msg += f"📍 Адрес: {get_setting('address', '—')}\n"
    msg += f"⏰ Часы: {get_setting('work_start', '10:00')} — {get_setting('work_end', '20:00')}\n"
    msg += f"⏱️ Перерыв: {get_setting('break_minutes', '10')} мин\n"
    msg += f"⏰ Длительность: {get_setting('default_duration', '120')} мин\n"
    msg += f"🔔 Мастеру: за {get_setting('reminder_master_hours', '1')} ч"
    
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🏷️ Название", callback_data="setting_business_name"),
        types.InlineKeyboardButton("📍 Адрес", callback_data="setting_address"),
        types.InlineKeyboardButton("⏰ Часы", callback_data="setting_work_hours"),
        types.InlineKeyboardButton("⏱️ Перерыв", callback_data="setting_break"),
        types.InlineKeyboardButton("⏰ Длительность", callback_data="setting_duration"),
        types.InlineKeyboardButton("🔔 Мастеру", callback_data="setting_reminder_master"),
        types.InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
    )
    
    bot.send_message(chat_id, msg, reply_markup=kb, parse_mode='Markdown')

# ==================== INLINE-КНОПКИ ====================
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    chat_id = call.message.chat.id
    data = call.data
    
    if data == "main_menu":
        bot.edit_message_text("🏠 Главное меню", chat_id, call.message.message_id)
        bot.send_message(chat_id, "Выберите действие:", reply_markup=main_menu())
        bot.answer_callback_query(call.id)
        return
    
    elif data.startswith("client_view_"):
        client_id = data.split("_")[2]
        client = get_client_by_id(client_id)
        if client:
            show_client_card(chat_id, client)
        bot.answer_callback_query(call.id)
    
    elif data == "client_new":
        user_state[chat_id] = "APPT_NEW_CLIENT_NAME"
        bot.edit_message_text("👤 Введите имя клиента:", chat_id, call.message.message_id)
        bot.answer_callback_query(call.id)
    
    elif data.startswith("client_edit_"):
        client_id = data.split("_")[2]
        kb = types.InlineKeyboardMarkup(row_width=1)
        kb.add(
            types.InlineKeyboardButton("👤 Изменить имя", callback_data=f"client_editname_{client_id}"),
            types.InlineKeyboardButton("📞 Изменить телефон", callback_data=f"client_editphone_{client_id}"),
            types.InlineKeyboardButton("📝 Изменить заметку", callback_data=f"client_editnote_{client_id}")
        )
        bot.edit_message_text("✏️ Что изменить?", chat_id, call.message.message_id, reply_markup=kb)
        bot.answer_callback_query(call.id)
    
    elif data.startswith("client_editname_"):
        client_id = data.split("_")[2]
        user_state[chat_id] = "EDIT_CLIENT_NAME"
        user_data[chat_id] = {"edit_client_id": client_id}
        bot.edit_message_text("👤 Введите новое имя:", chat_id, call.message.message_id)
        bot.answer_callback_query(call.id)
    
    elif data.startswith("client_editphone_"):
        client_id = data.split("_")[2]
        user_state[chat_id] = "EDIT_CLIENT_PHONE"
        user_data[chat_id] = {"edit_client_id": client_id}
        bot.edit_message_text("📞 Введите новый телефон:", chat_id, call.message.message_id)
        bot.answer_callback_query(call.id)
    
    elif data.startswith("client_editnote_"):
        client_id = data.split("_")[2]
        user_state[chat_id] = "EDIT_CLIENT_NOTE"
        user_data[chat_id] = {"edit_client_id": client_id}
        bot.edit_message_text("📝 Введите заметку (или '-' чтобы очистить):", chat_id, call.message.message_id)
        bot.answer_callback_query(call.id)
    
    elif data.startswith("client_note_"):
        client_id = data.split("_")[2]
        user_state[chat_id] = "EDIT_CLIENT_NOTE"
        user_data[chat_id] = {"edit_client_id": client_id}
        bot.edit_message_text("📝 Введите заметку:", chat_id, call.message.message_id)
        bot.answer_callback_query(call.id)
    
    elif data.startswith("client_history_"):
        client_id = data.split("_")[2]
        client = get_client_by_id(client_id)
        if client:
            rows = sheet_appointments.get_all_values()
            msg = f"📋 История {client['name']}:\n\n"
            count = 0
            for r in rows[1:]:
                if len(r) >= 10 and r[5] == client_id:
                    status_icon = {"Ожидание": "🟡", "Выполнена": "✅", "Отмена": "❌"}.get(r[9], "")
                    msg += f"{status_icon} {r[1]} {r[2]} — {r[7]} ({r[8]} BYN)\n"
                    count += 1
                    if count >= 15:
                        break
            if count == 0:
                msg += "Нет записей"
            bot.send_message(chat_id, msg)
        bot.answer_callback_query(call.id)
    
    elif data.startswith("client_app_"):
        client_id = data.split("_")[2]
        user_data[chat_id] = {"appt_client_id": client_id}
        services = get_active_services()
        if services:
            show_service_selection(chat_id, services)
            bot.edit_message_text("💇‍♀️ Выберите услугу:", chat_id, call.message.message_id)
        else:
            user_state[chat_id] = "APPT_MANUAL_SERVICE"
            bot.edit_message_text("💇‍♀️ Введите название услуги:", chat_id, call.message.message_id)
        bot.answer_callback_query(call.id)
    
    elif data.startswith("appt_select_"):
        client_id = data.split("_")[2]
        user_data[chat_id] = {"appt_client_id": client_id}
        services = get_active_services()
        if services:
            show_service_selection(chat_id, services)
            bot.edit_message_text("💇‍♀️ Выберите услугу:", chat_id, call.message.message_id)
        else:
            user_state[chat_id] = "APPT_MANUAL_SERVICE"
            bot.edit_message_text("💇‍♀️ Введите название услуги:", chat_id, call.message.message_id)
        bot.answer_callback_query(call.id)
    
    elif data == "appt_new_client":
        user_state[chat_id] = "APPT_NEW_CLIENT_NAME"
        bot.edit_message_text("👤 Введите имя клиента:", chat_id, call.message.message_id)
        bot.answer_callback_query(call.id)
    
    elif data.startswith("appt_service_"):
        service_id = data.split("_")[2]
        service = get_service_by_id(service_id)
        if service:
            user_data[chat_id]["appt_service_id"] = service_id
            user_data[chat_id]["appt_service_text"] = service['name']
            user_data[chat_id]["appt_duration"] = service['duration']
            user_data[chat_id]["appt_price"] = service['price']
            user_state[chat_id] = "APPT_DATE"
            kb = get_calendar_keyboard(callback_prefix="appt_date")
            bot.edit_message_text("📅 Выберите дату:", chat_id, call.message.message_id, reply_markup=kb)
        bot.answer_callback_query(call.id)
    
    elif data == "appt_service_manual":
        user_state[chat_id] = "APPT_MANUAL_SERVICE"
        bot.edit_message_text("💇‍♀️ Введите название услуги:", chat_id, call.message.message_id)
        bot.answer_callback_query(call.id)
    
    elif data.startswith("appt_date_"):
        date_str = data.split("_", 2)[2]
        user_data[chat_id]["appt_date"] = date_str
        duration = user_data[chat_id].get("appt_duration", 120)
        free_slots = get_free_slots(date_str, duration)
        
        if free_slots:
            kb = types.InlineKeyboardMarkup(row_width=3)
            for slot in free_slots[:9]:
                kb.add(types.InlineKeyboardButton(slot, callback_data=f"appt_time_{slot}"))
            if len(free_slots) > 9:
                kb.add(types.InlineKeyboardButton("Другое время", callback_data="appt_time_manual"))
            bot.edit_message_text(f"🟢 Свободное время на {date_str}:", chat_id, call.message.message_id, reply_markup=kb)
        else:
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("Ввести время вручную", callback_data="appt_time_manual"))
            kb.add(types.InlineKeyboardButton("🔙 Выбрать другую дату", callback_data="appt_back_to_cal"))
            bot.edit_message_text(f"🟡 Нет свободных слотов.", chat_id, call.message.message_id, reply_markup=kb)
        bot.answer_callback_query(call.id)
    
    elif data == "appt_back_to_cal":
        kb = get_calendar_keyboard(callback_prefix="appt_date")
        bot.edit_message_text("📅 Выберите дату:", chat_id, call.message.message_id, reply_markup=kb)
        bot.answer_callback_query(call.id)
    
    elif data == "appt_time_manual":
        user_state[chat_id] = "APPT_TIME_MANUAL"
        bot.edit_message_text("⏰ Введите время (ЧЧ:ММ):", chat_id, call.message.message_id)
        bot.answer_callback_query(call.id)
    
    elif data.startswith("appt_time_"):
        time_str = data.split("_")[2]
        date_str = user_data[chat_id].get("appt_date")
        duration = user_data[chat_id].get("appt_duration", 120)
        
        available, reason = is_time_available(date_str, time_str, duration)
        if available:
            user_data[chat_id]["appt_time"] = time_str
            user_state[chat_id] = "APPT_NOTES"
            bot.edit_message_text("📝 Введите заметку (или '-'):", chat_id, call.message.message_id)
        else:
            bot.answer_callback_query(call.id, f"⛔ {reason}", show_alert=True)
        bot.answer_callback_query(call.id)
    
    elif data.startswith("app_done_"):
        app_id = data.split("_")[2]
        if update_appointment_status(app_id, "Выполнена"):
            bot.edit_message_text(f"✅ Запись #{app_id} выполнена!", chat_id, call.message.message_id)
        bot.answer_callback_query(call.id)
    
    elif data.startswith("app_cancel_"):
        app_id = data.split("_")[2]
        user_state[chat_id] = "CANCEL_REASON"
        user_data[chat_id] = {"cancel_appt_id": app_id}
        
        kb = types.InlineKeyboardMarkup(row_width=1)
        kb.add(
            types.InlineKeyboardButton("👤 Клиент отказался", callback_data=f"cancel_reason_Клиент"),
            types.InlineKeyboardButton("😷 Мастер не может", callback_data=f"cancel_reason_Мастер")
        )
        bot.edit_message_text("❌ Причина отмены:", chat_id, call.message.message_id, reply_markup=kb)
        bot.answer_callback_query(call.id)
    
    elif data.startswith("cancel_reason_"):
        reason = data.split("_")[2]
        app_id = user_data[chat_id].get("cancel_appt_id")
        if cancel_appointment(app_id, reason):
            bot.edit_message_text(f"✅ Запись #{app_id} отменена", chat_id, call.message.message_id)
        user_state[chat_id] = None
        bot.answer_callback_query(call.id)
    
    elif data.startswith("app_edit_"):
        app_id = data.split("_")[2]
        user_data[chat_id] = {"edit_appt_id": app_id}
        
        kb = types.InlineKeyboardMarkup(row_width=1)
        kb.add(
            types.InlineKeyboardButton("💇‍♀️ Услуга", callback_data=f"app_edit_service_{app_id}"),
            types.InlineKeyboardButton("💰 Стоимость", callback_data=f"app_edit_price_{app_id}"),
            types.InlineKeyboardButton("📝 Заметка", callback_data=f"app_edit_notes_{app_id}")
        )
        bot.edit_message_text("✏️ Что изменить?", chat_id, call.message.message_id, reply_markup=kb)
        bot.answer_callback_query(call.id)
    
    elif data.startswith("app_edit_service_"):
        app_id = data.split("_")[3]
        user_state[chat_id] = "EDIT_APPT_SERVICE"
        user_data[chat_id] = {"edit_appt_id": app_id}
        bot.edit_message_text("💇‍♀️ Введите новое название:", chat_id, call.message.message_id)
        bot.answer_callback_query(call.id)
    
    elif data.startswith("app_edit_price_"):
        app_id = data.split("_")[3]
        user_state[chat_id] = "EDIT_APPT_PRICE"
        user_data[chat_id] = {"edit_appt_id": app_id}
        bot.edit_message_text("💰 Введите новую стоимость:", chat_id, call.message.message_id)
        bot.answer_callback_query(call.id)
    
    elif data.startswith("app_edit_notes_"):
        app_id = data.split("_")[3]
        user_state[chat_id] = "EDIT_APPT_NOTES"
        user_data[chat_id] = {"edit_appt_id": app_id}
        bot.edit_message_text("📝 Введите новую заметку:", chat_id, call.message.message_id)
        bot.answer_callback_query(call.id)
    
    elif data.startswith("app_reschedule_"):
        app_id = data.split("_")[2]
        user_data[chat_id] = {"reschedule_appt_id": app_id}
        user_state[chat_id] = "RESCHEDULE_DATE"
        kb = get_calendar_keyboard(callback_prefix="reschedule_date")
        bot.edit_message_text("📅 Выберите новую дату:", chat_id, call.message.message_id, reply_markup=kb)
        bot.answer_callback_query(call.id)
    
    elif data.startswith("reschedule_date_"):
        date_str = data.split("_", 2)[2]
        user_data[chat_id]["reschedule_date"] = date_str
        
        app_id = user_data[chat_id].get("reschedule_appt_id")
        app = get_appointment_by_id(app_id)
        duration = int(app[3]) if app else 120
        
        free_slots = get_free_slots(date_str, duration)
        if free_slots:
            kb = types.InlineKeyboardMarkup(row_width=3)
            for slot in free_slots[:9]:
                kb.add(types.InlineKeyboardButton(slot, callback_data=f"reschedule_time_{slot}"))
            bot.edit_message_text(f"🟢 Свободное время:", chat_id, call.message.message_id, reply_markup=kb)
        else:
            bot.edit_message_text(f"🟡 Нет свободных слотов.", chat_id, call.message.message_id)
        bot.answer_callback_query(call.id)
    
    elif data.startswith("reschedule_time_"):
        time_str = data.split("_")[2]
        date_str = user_data[chat_id].get("reschedule_date")
        app_id = user_data[chat_id].get("reschedule_appt_id")
        
        new_id = reschedule_appointment(app_id, date_str, time_str)
        if new_id:
            bot.edit_message_text(f"✅ Перенесено! Новый # {new_id}", chat_id, call.message.message_id)
        else:
            bot.edit_message_text(f"❌ Ошибка", chat_id, call.message.message_id)
        user_state[chat_id] = None
        user_data[chat_id] = {}
        bot.answer_callback_query(call.id)
    
    elif data.startswith("app_msg_"):
        app_id = data.split("_")[2]
        app = get_appointment_by_id(app_id)
        if app:
            client = get_client_by_id(app[5])
            business_name = get_setting("business_name", "Мастер")
            address = get_setting("address", "")
            
            msg = f"✅ Вы записаны!\n\n"
            msg += f"📅 {app[1]} в {app[2]}\n"
            msg += f"💇‍♀️ {app[7]}\n"
            msg += f"⏰ {app[3]} минут\n"
            msg += f"💰 {app[8]} BYN\n"
            if address:
                msg += f"📍 {address}\n"
            msg += f"\n{business_name}"
            
            bot.send_message(chat_id, f"<pre>{msg}</pre>", parse_mode='HTML')
        bot.answer_callback_query(call.id)
    
    elif data == "service_add":
        user_state[chat_id] = "ADD_SERVICE_NAME"
        bot.edit_message_text("💇‍♀️ Введите название:", chat_id, call.message.message_id)
        bot.answer_callback_query(call.id)
    
    elif data.startswith("service_dur_"):
        if data == "service_dur_manual":
            user_state[chat_id] = "ADD_SERVICE_DURATION_MANUAL"
            bot.edit_message_text("⏰ Введите минуты:", chat_id, call.message.message_id)
        else:
            duration = int(data.split("_")[2])
            user_data[chat_id]["new_service_duration"] = duration
            user_state[chat_id] = "ADD_SERVICE_PRICE"
            bot.edit_message_text("💰 Введите стоимость:", chat_id, call.message.message_id)
        bot.answer_callback_query(call.id)
    
    elif data.startswith("service_edit_"):
        service_id = data.split("_")[2]
        service = get_service_by_id(service_id)
        if service:
            kb = types.InlineKeyboardMarkup(row_width=1)
            kb.add(
                types.InlineKeyboardButton("✏️ Название", callback_data=f"service_editname_{service_id}"),
                types.InlineKeyboardButton("💰 Цена", callback_data=f"service_editprice_{service_id}"),
                types.InlineKeyboardButton("🗑️ Удалить", callback_data=f"service_delete_{service_id}")
            )
            msg = f"✏️ {service['name']}\n⏰ {service['duration']} мин\n💰 {service['price']} BYN"
            bot.edit_message_text(msg, chat_id, call.message.message_id, reply_markup=kb)
        bot.answer_callback_query(call.id)
    
    elif data.startswith("service_editname_"):
        service_id = data.split("_")[2]
        user_state[chat_id] = "EDIT_SERVICE_NAME"
        user_data[chat_id] = {"edit_service_id": service_id}
        bot.edit_message_text("✏️ Введите название:", chat_id, call.message.message_id)
        bot.answer_callback_query(call.id)
    
    elif data.startswith("service_editprice_"):
        service_id = data.split("_")[2]
        user_state[chat_id] = "EDIT_SERVICE_PRICE"
        user_data[chat_id] = {"edit_service_id": service_id}
        bot.edit_message_text("💰 Введите цену:", chat_id, call.message.message_id)
        bot.answer_callback_query(call.id)
    
    elif data.startswith("service_delete_"):
        service_id = data.split("_")[2]
        service = get_service_by_id(service_id)
        if service:
            kb = types.InlineKeyboardMarkup()
            kb.add(
                types.InlineKeyboardButton("✅ Да", callback_data=f"service_delete_confirm_{service_id}"),
                types.InlineKeyboardButton("❌ Нет", callback_data="service_add")
            )
            bot.edit_message_text(f"🗑️ Удалить '{service['name']}'?", chat_id, call.message.message_id, reply_markup=kb)
        bot.answer_callback_query(call.id)
    
    elif data.startswith("service_delete_confirm_"):
        service_id = data.split("_")[3]
        if delete_service(service_id):
            bot.edit_message_text("✅ Удалено", chat_id, call.message.message_id)
            show_services_list(chat_id)
        bot.answer_callback_query(call.id)
    
    elif data.startswith("setting_"):
        key = data.replace("setting_", "")
        user_state[chat_id] = "SETTING_VALUE"
        user_data[chat_id] = {"setting_key": key}
        
        prompts = {
            "business_name": "🏷️ Название:",
            "address": "📍 Адрес:",
            "work_hours": "⏰ Часы (10:00-20:00):",
            "break": "⏱️ Перерыв (мин):",
            "duration": "⏰ Длительность (мин):",
            "reminder_master": "🔔 Напоминание мастеру (часов):",
        }
        
        prompt = prompts.get(key, "Введите значение:")
        bot.edit_message_text(prompt, chat_id, call.message.message_id)
        bot.answer_callback_query(call.id)
    
    elif data.startswith("cal_"):
        parts = data.split("_")
        if len(parts) >= 4:
            year = int(parts[1])
            month = int(parts[2])
            prefix = parts[3]
            kb = get_calendar_keyboard(year, month, prefix)
            bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=kb)
        bot.answer_callback_query(call.id)
    
    elif data == "ignore":
        bot.answer_callback_query(call.id)

# ==================== ЗАПУСК ====================
def main():
    scheduler.add_job(check_reminders, 'interval', minutes=15)
    scheduler.start()
    
    max_retries = 3
    for i in range(max_retries):
        try:
            requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook?drop_pending_updates=true", timeout=10)
            logger.info("✅ Вебхуки очищены")
            time.sleep(2)
            break
        except Exception as e:
            logger.warning(f"⚠️ Попытка {i+1}/{max_retries}: {e}")
            time.sleep(3)
    
    threading.Thread(target=run_flask, daemon=True).start()
    logger.info("🌐 API и статика запущены")
    logger.info("🤖 Бот запущен...")
    
    while True:
        try:
            bot.polling(none_stop=True, timeout=60, long_polling_timeout=60)
        except Exception as e:
            error_str = str(e)
            logger.error(f"❌ Ошибка: {e}")
            
            if "409" in error_str or "Conflict" in error_str:
                logger.info("🔄 Конфликт, очищаем...")
                try:
                    requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook?drop_pending_updates=true", timeout=10)
                    time.sleep(5)
                except:
                    pass
            else:
                time.sleep(5)

if __name__ == "__main__":
    main()
