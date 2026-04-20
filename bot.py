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

import logging as flask_logging
flask_logging.getLogger('werkzeug').setLevel(flask_logging.ERROR)

# ==================== FLASK ====================
app = Flask(__name__, static_folder='.', static_url_path='')

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
        if len(r) >= 3:
            client_phone = re.sub(r'\D', '', r[2])
            search_phone = re.sub(r'\D', '', phone)
            if search_phone in client_phone:
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

@app.route('/')
def home():
    return send_from_directory('.', 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    if os.path.exists(filename):
        return send_from_directory('.', filename)
    return send_from_directory('.', 'index.html')

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
        name = data.get('name')
        phone = data.get('phone')
        service_id = data.get('service_id')
        service_text = data.get('service_text', '')
        date = data.get('date')
        time = data.get('time')
        notes = data.get('notes', '')
        
        if not all([name, phone, date, time]):
            return jsonify({"error": "missing required fields"}), 400
        
        client = get_client_by_phone(phone)
        if not client:
            client_id = add_client_api(name, phone, notes)
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
        
        if ADMIN_ID:
            msg = f"🆕 Новая запись!\n👤 {name}\n📞 {phone}\n💇‍♀️ {service_text}\n📅 {date} в {time}\n💰 {price} BYN"
            if notes:
                msg += f"\n📝 {notes}"
            bot.send_message(ADMIN_ID, msg)
        
        return jsonify({"success": True, "appointment_id": app_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/appointment/find', methods=['GET'])
def api_find_appointment():
    query = request.args.get('query', '').strip()
    if not query:
        return jsonify({"error": "query required"}), 400
    
    rows = sheet_appointments.get_all_values()
    search_phone = re.sub(r'\D', '', query)
    
    for r in rows[1:]:
        if len(r) >= 10 and r[9] == "Ожидание":
            if r[0] == query:
                client = get_client_by_id_api(r[5]) if len(r) > 5 else None
                return jsonify({"appointment": {
                    "id": r[0], "date": r[1], "time": r[2], "duration": r[3],
                    "service": r[7], "price": r[8], "status": r[9],
                    "client_name": client['name'] if client else "",
                    "client_phone": client['phone'] if client else ""
                }})
            
            client = get_client_by_id_api(r[5]) if len(r) > 5 else None
            if client:
                client_phone = re.sub(r'\D', '', client['phone'])
                if search_phone in client_phone:
                    return jsonify({"appointment": {
                        "id": r[0], "date": r[1], "time": r[2], "duration": r[3],
                        "service": r[7], "price": r[8], "status": r[9],
                        "client_name": client['name'], "client_phone": client['phone']
                    }})
    
    return jsonify({"appointment": None})

@app.route('/api/appointment/cancel', methods=['POST'])
def api_cancel_appointment():
    data = request.json
    app_id = data.get('appointment_id')
    if not app_id:
        return jsonify({"error": "appointment_id required"}), 400
    
    cell = sheet_appointments.find(str(app_id), in_column=1)
    if cell:
        sheet_appointments.update_cell(cell.row, 10, "Отмена")
        if ADMIN_ID:
            bot.send_message(ADMIN_ID, f"❌ Запись #{app_id} отменена через Mini App")
        return jsonify({"success": True})
    return jsonify({"error": "Not found"}), 404

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
    raise ValueError("❌ GOOGLE_CREDENTIALS не задан")

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_dict = json.loads(GOOGLE_CREDS_JSON)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
sh = client.open_by_key(SHEET_ID)

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
    sheet_appointments = sh.worksheet("Записи")
except:
    sheet_appointments = sh.add_worksheet(title="Записи", rows=1000, cols=12)
    sheet_appointments.append_row(["ID", "Дата", "Время", "Длит", "Конец", "Клиент", "УслугаID", "Услуга", "Цена", "Статус", "Заметка"])

try:
    sheet_settings = sh.worksheet("Настройки")
except:
    sheet_settings = sh.add_worksheet(title="Настройки", rows=50, cols=2)
    sheet_settings.append_row(["Ключ", "Значение"])
    for k, v in [("business_name", "Мастер"), ("address", ""), ("work_start", "10:00"), ("work_end", "20:00"), ("break_minutes", "10"), ("default_duration", "120")]:
        sheet_settings.append_row([k, v])

bot = telebot.TeleBot(BOT_TOKEN)
scheduler = BackgroundScheduler()
user_state, user_data = {}, {}

def is_admin(msg):
    if ADMIN_ID == 0: return True
    return msg.chat.id == ADMIN_ID

def get_setting(k, d=""):
    try:
        for r in sheet_settings.get_all_values()[1:]:
            if len(r)>=2 and r[0]==k: return r[1]
    except: pass
    return d

def main_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("➕ Новая запись", "🔍 Найти клиента")
    kb.row("📅 Сегодня", "📅 Завтра")
    kb.row("📋 Все записи", "👥 Клиенты")
    kb.row("💇‍♀️ Услуги", "⚙️ Настройки")
    kb.row("📊 Таблица", "📱 Mini App")
    return kb

@bot.message_handler(commands=['start'])
def start(msg):
    if is_admin(msg):
        bot.send_message(msg.chat.id, f"🔥 CRM {get_setting('business_name')}\nВыберите действие:", reply_markup=main_menu())
    else:
        kb = types.InlineKeyboardMarkup()
        url = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME', 'your-app.onrender.com')}"
        kb.add(types.InlineKeyboardButton("📱 Записаться онлайн", web_app=types.WebAppInfo(url=url)))
        bot.send_message(msg.chat.id, f"💇‍♀️ **{get_setting('business_name')}**\n\nЗапишитесь онлайн 👇", reply_markup=kb, parse_mode='Markdown')

@bot.message_handler(func=lambda m: True)
def handle(msg):
    if not is_admin(msg):
        kb = types.InlineKeyboardMarkup()
        url = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME', 'your-app.onrender.com')}"
        kb.add(types.InlineKeyboardButton("📱 Записаться", web_app=types.WebAppInfo(url=url)))
        bot.send_message(msg.chat.id, "Нажмите кнопку ниже 👇", reply_markup=kb)
        return
    
    t = msg.text
    if t == "➕ Новая запись":
        bot.send_message(msg.chat.id, "В разработке: используйте Mini App")
    elif t == "📊 Таблица":
        bot.send_message(msg.chat.id, f"https://docs.google.com/spreadsheets/d/{SHEET_ID}")
    elif t == "📱 Mini App":
        url = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME', 'your-app.onrender.com')}"
        kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("Открыть", web_app=types.WebAppInfo(url=url)))
        bot.send_message(msg.chat.id, "Запись:", reply_markup=kb)
    else:
        bot.send_message(msg.chat.id, "Используйте Mini App для записи")

def main():
    try:
        requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook?drop_pending_updates=true", timeout=10)
    except: pass
    threading.Thread(target=run_flask, daemon=True).start()
    logger.info("🤖 Бот запущен")
    while True:
        try:
            bot.polling(none_stop=True, timeout=60)
        except Exception as e:
            logger.error(f"Polling error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
