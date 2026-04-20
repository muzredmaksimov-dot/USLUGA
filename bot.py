#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, re, json, logging, threading, calendar, time, requests, csv, io
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

# --- Flask ---
app = Flask(__name__, static_folder='.', static_url_path='')

# --- Глобальные переменные ---
bot = None
sheet_clients = sheet_services = sheet_appointments = sheet_settings = sheet_services_archive = None
ADMIN_ID = 0
user_state, user_data = {}, {}

# --- Вспомогательные функции API ---
def get_setting(k, d=""):
    try:
        for r in sheet_settings.get_all_values()[1:]:
            if len(r)>=2 and r[0]==k: return r[1]
    except: pass
    return d

def get_active_services():
    rows = sheet_services.get_all_values()
    if len(rows)<=1: return []
    s = []
    for r in rows[1:]:
        if len(r)>=5 and r[4]=="Да":
            s.append({"id":r[0],"name":r[1],"duration":int(r[2]) if r[2] else 120,"price":int(r[3]) if r[3] else 0})
    return s

def get_all_services():
    rows = sheet_services.get_all_values()
    if len(rows)<=1: return []
    return [{"id":r[0],"name":r[1],"duration":int(r[2]) if r[2] else 120,"price":int(r[3]) if r[3] else 0,"active":r[4]=="Да"} for r in rows[1:] if len(r)>=5]

def get_free_slots(date_str, duration):
    work_start = datetime.strptime(get_setting("work_start","10:00"), "%H:%M")
    work_end = datetime.strptime(get_setting("work_end","20:00"), "%H:%M")
    break_min = int(get_setting("break_minutes","10"))
    rows = sheet_appointments.get_all_values()
    apps = [r for r in rows[1:] if len(r)>=10 and r[1]==date_str and r[9]=="Ожидание"]
    busy = []
    for a in apps:
        s = datetime.strptime(a[2],"%H:%M")
        e = s + timedelta(minutes=int(a[3])+break_min)
        busy.append((s,e))
    busy.sort()
    free, cur = [], work_start
    for bs, be in busy:
        while cur + timedelta(minutes=duration) <= bs:
            free.append(cur.strftime("%H:%M"))
            cur += timedelta(minutes=30)
        if cur < be: cur = be
    while cur + timedelta(minutes=duration) <= work_end:
        free.append(cur.strftime("%H:%M"))
        cur += timedelta(minutes=30)
    return sorted(list(set(free)))

def add_client(name, phone, notes=""):
    rows = sheet_clients.get_all_values()
    cid = str(len(rows))
    sheet_clients.append_row([cid, name, phone, notes, "Обычный", "0", "0"])
    return cid

def get_client_by_phone(phone):
    search = re.sub(r'\D','',phone)
    for r in sheet_clients.get_all_values()[1:]:
        if len(r)>=3 and search in re.sub(r'\D','',r[2]): return {"id":r[0],"name":r[1],"phone":r[2]}
    return None

def get_client_by_id(cid):
    for r in sheet_clients.get_all_values()[1:]:
        if len(r)>0 and r[0]==str(cid): return {"id":r[0],"name":r[1],"phone":r[2],"notes":r[3],"status":r[4],"visits":r[5],"total":r[6]}
    return None

def get_all_clients():
    return [{"id":r[0],"name":r[1],"phone":r[2],"status":r[4]} for r in sheet_clients.get_all_values()[1:] if len(r)>=5]

def add_appointment(date, time_start, duration, client_id, service_id, service_text, price, notes=""):
    rows = sheet_appointments.get_all_values()
    app_id = str(len(rows))
    time_end = (datetime.strptime(time_start,"%H:%M")+timedelta(minutes=duration)).strftime("%H:%M")
    sheet_appointments.append_row([app_id, date, time_start, str(duration), time_end, str(client_id), str(service_id), service_text, str(price), "Ожидание", notes])
    update_client_stats(client_id)
    return app_id

def get_appointments_by_date(date_str):
    rows = sheet_appointments.get_all_values()
    return [r for r in rows[1:] if len(r)>=10 and r[1]==date_str and r[9]=="Ожидание"]

def get_appointment_by_id(app_id):
    for r in sheet_appointments.get_all_values()[1:]:
        if len(r)>0 and r[0]==str(app_id): return r
    return None

def get_all_active_appointments():
    return [r for r in sheet_appointments.get_all_values()[1:] if len(r)>=10 and r[9]=="Ожидание"]

def update_appointment_field(app_id, col, val):
    cell = sheet_appointments.find(str(app_id), in_column=1)
    if cell:
        sheet_appointments.update_cell(cell.row, col, str(val))
        return True
    return False

def update_appointment_status(app_id, status):
    if update_appointment_field(app_id, 10, status):
        app = get_appointment_by_id(app_id)
        if app and len(app)>5: update_client_stats(app[5])
        return True
    return False

def update_client_stats(cid):
    rows = sheet_appointments.get_all_values()
    visits, total = 0, 0
    for r in rows[1:]:
        if len(r)>=10 and r[5]==str(cid) and r[9]=="Выполнена":
            visits += 1
            try: total += float(r[8]) if r[8] else 0
            except: pass
    cell = sheet_clients.find(str(cid), in_column=1)
    if cell:
        sheet_clients.update_cell(cell.row, 6, str(visits))
        sheet_clients.update_cell(cell.row, 7, str(int(total)))
        status = "VIP" if visits>=10 else ("Постоянный" if visits>=5 else "Обычный")
        sheet_clients.update_cell(cell.row, 5, status)

def add_service(name, duration, price):
    rows = sheet_services.get_all_values()
    sid = str(len(rows))
    sheet_services.append_row([sid, name, str(duration), str(price), "Да"])
    if sheet_services_archive:
        sheet_services_archive.append_row([datetime.now().strftime("%d.%m.%Y %H:%M"), "Создана", sid, name, str(duration), str(price)])
    return sid

def update_service(sid, name, duration, price, active):
    cell = sheet_services.find(str(sid), in_column=1)
    if cell:
        sheet_services.update_cell(cell.row, 2, name)
        sheet_services.update_cell(cell.row, 3, str(duration))
        sheet_services.update_cell(cell.row, 4, str(price))
        sheet_services.update_cell(cell.row, 5, "Да" if active else "Нет")
        if sheet_services_archive:
            sheet_services_archive.append_row([datetime.now().strftime("%d.%m.%Y %H:%M"), "Изменена", sid, name, str(duration), str(price)])
        return True
    return False

def delete_service(sid):
    for s in get_all_services():
        if s['id']==sid:
            update_service(sid, s['name'], s['duration'], s['price'], False)
            if sheet_services_archive:
                sheet_services_archive.append_row([datetime.now().strftime("%d.%m.%Y %H:%M"), "Удалена", sid, s['name'], str(s['duration']), str(s['price'])])
            return True
    return False

def update_setting(k, v):
    cell = sheet_settings.find(k, in_column=1)
    if cell:
        sheet_settings.update_cell(cell.row, 2, str(v))
    else:
        sheet_settings.append_row([k, str(v)])
    return True

# --- API для Mini App ---
@app.route('/')
def home(): return send_from_directory('.','index.html')
@app.route('/<path:filename>')
def serve_static(filename):
    if os.path.exists(filename): return send_from_directory('.',filename)
    return send_from_directory('.','index.html')
@app.route('/api/settings')
def api_settings(): return jsonify({"business_name":get_setting("business_name","Мастер"),"address":get_setting("address","")})
@app.route('/api/services')
def api_services(): return jsonify({"services":get_active_services()})
@app.route('/api/slots')
def api_slots():
    date = request.args.get('date')
    sid = request.args.get('service_id')
    if not date: return jsonify({"error":"date required"}),400
    dur = 120
    if sid:
        for s in get_active_services():
            if s['id']==sid: dur=s['duration']; break
    return jsonify({"slots":get_free_slots(date,dur)})
@app.route('/api/appointment', methods=['POST'])
def api_appointment():
    d = request.json
    name, phone, sid, stext, date, time, notes = d.get('name'), d.get('phone'), d.get('service_id'), d.get('service_text',''), d.get('date'), d.get('time'), d.get('notes','')
    if not all([name,phone,date,time]): return jsonify({"error":"missing fields"}),400
    c = get_client_by_phone(phone)
    cid = c['id'] if c else add_client(name,phone,notes)
    price, dur = 0, int(get_setting("default_duration","120"))
    if sid:
        for s in get_active_services():
            if s['id']==sid: stext, price, dur = s['name'], s['price'], s['duration']; break
    app_id = add_appointment(date,time,dur,cid,sid or "0",stext,price,notes)
    if ADMIN_ID:
        bot.send_message(ADMIN_ID, f"🆕 Запись #{app_id}\n👤 {name}\n📞 {phone}\n💇‍♀️ {stext}\n📅 {date} {time}\n💰 {price} BYN")
    return jsonify({"success":True,"appointment_id":app_id})
@app.route('/api/appointment/find')
def api_find():
    q = request.args.get('query','').strip().replace('#','')
    if not q: return jsonify({"error":"query required"}),400
    rows = sheet_appointments.get_all_values()
    search_phone = re.sub(r'\D','',q)
    for r in rows[1:]:
        if len(r)>=10 and r[9]=="Ожидание":
            if r[0]==q:
                c = get_client_by_id(r[5]) if len(r)>5 else None
                return jsonify({"appointment":{"id":r[0],"date":r[1],"time":r[2],"service":r[7],"price":r[8],"status":r[9],"client_name":c['name'] if c else "","client_phone":c['phone'] if c else ""}})
            c = get_client_by_id(r[5]) if len(r)>5 else None
            if c and search_phone in re.sub(r'\D','',c['phone']):
                return jsonify({"appointment":{"id":r[0],"date":r[1],"time":r[2],"service":r[7],"price":r[8],"status":r[9],"client_name":c['name'],"client_phone":c['phone']}})
    return jsonify({"appointment":None})
@app.route('/api/appointment/cancel', methods=['POST'])
def api_cancel():
    app_id = request.json.get('appointment_id')
    if not app_id: return jsonify({"error":"appointment_id required"}),400
    if update_appointment_status(app_id,"Отмена"):
        if ADMIN_ID: bot.send_message(ADMIN_ID, f"❌ Запись #{app_id} отменена")
        return jsonify({"success":True})
    return jsonify({"error":"Not found"}),404

def run_flask():
    port = int(os.environ.get("PORT",10000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

# --- Настройки бота ---
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
SHEET_ID = os.getenv("SHEET_ID")
GOOGLE_CREDS_JSON = os.getenv("GOOGLE_CREDENTIALS")
ADMIN_ID = int(os.getenv("ADMIN_ID","0"))
if not GOOGLE_CREDS_JSON: raise ValueError("❌ GOOGLE_CREDENTIALS не задан")

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

scope = ["https://spreadsheets.google.com/feeds","https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(GOOGLE_CREDS_JSON), scope)
sh = gspread.authorize(creds).open_by_key(SHEET_ID)

def init_sheet(name, headers):
    try: return sh.worksheet(name)
    except:
        ws = sh.add_worksheet(title=name, rows=1000, cols=len(headers))
        ws.append_row(headers)
        return ws

sheet_clients = init_sheet("Клиенты", ["ID","Имя","Телефон","Заметки","Статус","Визиты","Сумма"])
sheet_services = init_sheet("Услуги", ["ID","Название","Длительность","Цена","Активна"])
sheet_services_archive = init_sheet("Услуги_архив", ["Дата","Действие","ID","Название","Длительность","Цена"])
sheet_appointments = init_sheet("Записи", ["ID","Дата","Время","Длит","Конец","Клиент","УслугаID","Услуга","Цена","Статус","Заметка"])
sheet_settings = init_sheet("Настройки", ["Ключ","Значение"])
if len(sheet_settings.get_all_values())<=1:
    for k,v in [("business_name","Мастер"),("address",""),("work_start","10:00"),("work_end","20:00"),("break_minutes","10"),("default_duration","120"),("reminder_master_hours","1")]:
        sheet_settings.append_row([k,v])

bot = telebot.TeleBot(BOT_TOKEN)
scheduler = BackgroundScheduler()

def is_admin(m): return ADMIN_ID==0 or m.chat.id==ADMIN_ID

def main_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("➕ Новая запись", "🔍 Найти клиента")
    kb.row("📅 Сегодня", "📅 Завтра", "📋 Все записи")
    kb.row("👥 Клиенты", "💇‍♀️ Услуги", "📊 Статистика")
    kb.row("⚙️ Настройки", "📊 Таблица", "📱 Mini App")
    return kb

def clean_phone(p):
    if not p: return ""
    d = re.sub(r'\D','',p)
    if d.startswith('80') and len(d)>=11: d = '375'+d[2:]
    elif d.startswith('8') and len(d)==11: d = '7'+d[1:]
    if d.startswith('375') and len(d)==12: return f"+{d[:3]} {d[3:5]} {d[5:8]}-{d[8:10]}-{d[10:12]}"
    elif d.startswith('7') and len(d)==11: return f"+{d[0]} {d[1:4]} {d[4:7]}-{d[7:9]}-{d[9:11]}"
    return d

def format_phone_md(p):
    if not p or p=="—": return "—"
    d = clean_phone(p)
    return f"[{d}](tel:+{re.sub(r'\D','',d)})" if d else p

# --- Обработчики команд ---
@bot.message_handler(commands=['start'])
def start(msg):
    chat_id = msg.chat.id
    user_state[chat_id] = None
    user_data[chat_id] = {}
    if is_admin(msg):
        bot.send_message(chat_id, f"🔥 CRM {get_setting('business_name')}", reply_markup=main_menu())
    else:
        url = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME','your-app.onrender.com')}"
        kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("📱 Записаться онлайн", web_app=types.WebAppInfo(url=url)))
        bot.send_message(chat_id, f"💇‍♀️ **{get_setting('business_name')}**\n\nЗапишитесь онлайн 👇", reply_markup=kb, parse_mode='Markdown')

@bot.message_handler(func=lambda m: True)
def handle(msg):
    chat_id = msg.chat.id
    text = msg.text
    
    if not is_admin(msg):
        url = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME','your-app.onrender.com')}"
        kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("📱 Записаться", web_app=types.WebAppInfo(url=url)))
        bot.send_message(chat_id, "Нажмите кнопку 👇", reply_markup=kb)
        return
    
    if chat_id not in user_state:
        user_state[chat_id] = None
        user_data[chat_id] = {}
    
    state = user_state.get(chat_id)
    
    # --- Главное меню ---
    if text == "➕ Новая запись":
        user_state[chat_id] = "APPT_SEARCH_CLIENT"
        bot.send_message(chat_id, "🔍 Введите имя или телефон клиента (или 'новый'):")
    elif text == "🔍 Найти клиента":
        user_state[chat_id] = "SEARCH_CLIENT"
        bot.send_message(chat_id, "🔍 Введите имя или телефон:")
    elif text == "👥 Клиенты":
        show_clients(chat_id)
    elif text == "📅 Сегодня":
        show_appointments(chat_id, datetime.now().strftime("%Y-%m-%d"), "сегодня")
    elif text == "📅 Завтра":
        show_appointments(chat_id, (datetime.now()+timedelta(days=1)).strftime("%Y-%m-%d"), "завтра")
    elif text == "📋 Все записи":
        apps = get_all_active_appointments()
        if not apps: bot.send_message(chat_id, "📭 Нет активных записей")
        else:
            for a in sorted(apps, key=lambda x:(x[1],x[2]))[:10]:
                show_appointment_card(chat_id, a)
    elif text == "💇‍♀️ Услуги":
        show_services_menu(chat_id)
    elif text == "📊 Статистика":
        show_stats(chat_id)
    elif text == "⚙️ Настройки":
        show_settings(chat_id)
    elif text == "📊 Таблица":
        bot.send_message(chat_id, f"https://docs.google.com/spreadsheets/d/{SHEET_ID}")
    elif text == "📱 Mini App":
        url = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME','your-app.onrender.com')}"
        kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("Открыть", web_app=types.WebAppInfo(url=url)))
        bot.send_message(chat_id, "Запись:", reply_markup=kb)
    elif text == "🏠 Главное меню":
        user_state[chat_id] = None
        bot.send_message(chat_id, "Главное меню:", reply_markup=main_menu())
    
    # --- Состояния ---
    elif state == "APPT_SEARCH_CLIENT":
        if text.lower() == 'новый':
            user_state[chat_id] = "APPT_NEW_NAME"
            bot.send_message(chat_id, "👤 Введите имя:")
        else:
            clients = [c for c in get_all_clients() if text.lower() in c['name'].lower() or text in c['phone']]
            if clients:
                kb = types.InlineKeyboardMarkup(row_width=1)
                for c in clients[:5]:
                    kb.add(types.InlineKeyboardButton(f"{c['name']} ({c['phone']})", callback_data=f"appt_client_{c['id']}"))
                kb.add(types.InlineKeyboardButton("➕ Новый клиент", callback_data="appt_new"))
                bot.send_message(chat_id, "Выберите клиента:", reply_markup=kb)
            else:
                bot.send_message(chat_id, "Не найден. Введите 'новый' или другое имя:")
    
    elif state == "APPT_NEW_NAME":
        user_data[chat_id] = {"new_name": text}
        user_state[chat_id] = "APPT_NEW_PHONE"
        bot.send_message(chat_id, "📞 Введите телефон:")
    elif state == "APPT_NEW_PHONE":
        name = user_data[chat_id].get("new_name","")
        cid = add_client(name, text)
        user_data[chat_id]["appt_client"] = cid
        show_service_selection(chat_id)
    elif state == "APPT_MANUAL_SERVICE":
        user_data[chat_id]["appt_service_text"] = text
        user_data[chat_id]["appt_service_id"] = "0"
        user_state[chat_id] = "APPT_DURATION"
        bot.send_message(chat_id, f"⏰ Длительность (мин, по умолч. {get_setting('default_duration','120')}):")
    elif state == "APPT_DURATION":
        try: dur = int(text) if text.strip() else int(get_setting("default_duration","120"))
        except: dur = int(get_setting("default_duration","120"))
        user_data[chat_id]["appt_duration"] = dur
        user_state[chat_id] = "APPT_PRICE"
        bot.send_message(chat_id, "💰 Стоимость:")
    elif state == "APPT_PRICE":
        try: price = int(text) if text.strip() else 0
        except: price = 0
        user_data[chat_id]["appt_price"] = price
        user_state[chat_id] = "APPT_DATE"
        kb = get_calendar_keyboard("appt_date")
        bot.send_message(chat_id, "📅 Выберите дату:", reply_markup=kb)
    elif state == "APPT_NOTES":
        user_data[chat_id]["appt_notes"] = text if text != '-' else ""
        create_appointment_from_data(chat_id)
    elif state == "SEARCH_CLIENT":
        clients = [c for c in get_all_clients() if text.lower() in c['name'].lower() or text in c['phone']]
        if clients:
            for c in clients[:5]: show_client_card(chat_id, c)
        else:
            bot.send_message(chat_id, "Не найдено")
        user_state[chat_id] = None
    elif state == "ADD_SERVICE_NAME":
        user_data[chat_id]["new_srv_name"] = text
        user_state[chat_id] = "ADD_SERVICE_DURATION"
        bot.send_message(chat_id, "⏰ Длительность (мин):")
    elif state == "ADD_SERVICE_DURATION":
        try: user_data[chat_id]["new_srv_dur"] = int(text)
        except: bot.send_message(chat_id, "Введите число"); return
        user_state[chat_id] = "ADD_SERVICE_PRICE"
        bot.send_message(chat_id, "💰 Стоимость:")
    elif state == "ADD_SERVICE_PRICE":
        try: price = int(text)
        except: bot.send_message(chat_id, "Введите число"); return
        add_service(user_data[chat_id]["new_srv_name"], user_data[chat_id]["new_srv_dur"], price)
        bot.send_message(chat_id, "✅ Услуга добавлена")
        show_services_menu(chat_id)
        user_state[chat_id] = None
    elif state and state.startswith("EDIT_SERVICE_"):
        _, _, sid, field = state.split("_")
        if field == "NAME": update_service(sid, text, None, None, True)
        elif field == "DURATION":
            try: update_service(sid, None, int(text), None, True)
            except: pass
        elif field == "PRICE":
            try: update_service(sid, None, None, int(text), True)
            except: pass
        bot.send_message(chat_id, "✅ Изменено")
        show_services_menu(chat_id)
        user_state[chat_id] = None
    elif state and state.startswith("SETTING_"):
        key = state.replace("SETTING_","")
        update_setting(key, text)
        bot.send_message(chat_id, "✅ Сохранено")
        show_settings(chat_id)
        user_state[chat_id] = None

# --- Вспомогательные функции бота ---
def get_calendar_keyboard(prefix, y=None, m=None):
    now = datetime.now()
    y, m = y or now.year, m or now.month
    kb = types.InlineKeyboardMarkup(row_width=7)
    kb.add(types.InlineKeyboardButton(f"{['Январь','Февраль','Март','Апрель','Май','Июнь','Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь'][m-1]} {y}", callback_data="ignore"))
    kb.add(*[types.InlineKeyboardButton(d, callback_data="ignore") for d in ['Пн','Вт','Ср','Чт','Пт','Сб','Вс']])
    cal = calendar.monthcalendar(y,m)
    for w in cal:
        row = []
        for d in w:
            if d==0: row.append(types.InlineKeyboardButton(" ", callback_data="ignore"))
            else: row.append(types.InlineKeyboardButton(str(d), callback_data=f"{prefix}_{y}-{m:02d}-{d:02d}"))
        kb.add(*row)
    pm, py = (m-1, y) if m>1 else (12, y-1)
    nm, ny = (m+1, y) if m<12 else (1, y+1)
    kb.add(types.InlineKeyboardButton("<<", callback_data=f"cal_{py}_{pm}_{prefix}"), types.InlineKeyboardButton(">>", callback_data=f"cal_{ny}_{nm}_{prefix}"))
    return kb

def show_appointments(chat_id, date, label):
    apps = get_appointments_by_date(date)
    if not apps: bot.send_message(chat_id, f"📭 Нет записей на {label}")
    else:
        for a in sorted(apps, key=lambda x:x[2]): show_appointment_card(chat_id, a)

def show_appointment_card(chat_id, a):
    c = get_client_by_id(a[5]) if len(a)>5 else None
    msg = f"📋 #{a[0]} | {a[2]}\n👤 {c['name'] if c else '—'}\n📞 {format_phone_md(c['phone']) if c else '—'}\n💇‍♀️ {a[7]}\n💰 {a[8]} BYN"
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(types.InlineKeyboardButton("✅ Выполнена", callback_data=f"done_{a[0]}"), types.InlineKeyboardButton("❌ Отмена", callback_data=f"cancel_{a[0]}"))
    bot.send_message(chat_id, msg, reply_markup=kb, parse_mode='Markdown')

def show_clients(chat_id):
    clients = get_all_clients()
    if not clients: bot.send_message(chat_id, "📭 Нет клиентов")
    else:
        msg = "👥 Клиенты:\n" + "\n".join([f"{c['id']}. {c['name']} ({c['phone']}) [{c['status']}]" for c in clients[:20]])
        bot.send_message(chat_id, msg)

def show_client_card(chat_id, c):
    c = get_client_by_id(c['id']) if isinstance(c, dict) else c
    msg = f"👤 {c['name']}\n📞 {format_phone_md(c['phone'])}\n📋 Визитов: {c['visits']} | Сумма: {c['total']} BYN"
    if c.get('notes'): msg += f"\n📝 {c['notes']}"
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("📅 Записать", callback_data=f"appt_client_{c['id']}"))
    bot.send_message(chat_id, msg, reply_markup=kb, parse_mode='Markdown')

def show_services_menu(chat_id):
    services = get_all_services()
    active = [s for s in services if s['active']]
    msg = "💇‍♀️ Активные услуги:\n" + "\n".join([f"{s['id']}. {s['name']} — {s['duration']}мин / {s['price']}BYN" for s in active])
    kb = types.InlineKeyboardMarkup(row_width=2)
    for s in active:
        kb.add(types.InlineKeyboardButton(f"✏️ {s['name']}", callback_data=f"editsrv_{s['id']}"))
    kb.add(types.InlineKeyboardButton("➕ Добавить", callback_data="addsrv"))
    bot.send_message(chat_id, msg or "Нет услуг", reply_markup=kb)

def show_service_selection(chat_id):
    services = get_active_services()
    kb = types.InlineKeyboardMarkup(row_width=1)
    for s in services:
        kb.add(types.InlineKeyboardButton(f"{s['name']} — {s['duration']}мин / {s['price']}BYN", callback_data=f"selsrv_{s['id']}"))
    kb.add(types.InlineKeyboardButton("📝 Другая", callback_data="selsrv_manual"))
    bot.send_message(chat_id, "Выберите услугу:", reply_markup=kb)
    user_state[chat_id] = "APPT_SELECT_SERVICE"

def show_stats(chat_id):
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    rows = sheet_appointments.get_all_values()
    today_inc, today_cnt, month_inc, month_cnt = 0,0,0,0
    for r in rows[1:]:
        if len(r)>=10 and r[9]=="Выполнена":
            try: p = float(r[8]) if r[8] else 0
            except: p = 0
            if r[1]==today: today_inc += p; today_cnt += 1
            if r[1]>=now.replace(day=1).strftime("%Y-%m-%d"): month_inc += p; month_cnt += 1
    bot.send_message(chat_id, f"📊 Сегодня: {today_cnt} записей, {int(today_inc)} BYN\n📆 Месяц: {month_cnt} записей, {int(month_inc)} BYN")

def show_settings(chat_id):
    msg = f"🏷️ Название: {get_setting('business_name')}\n📍 Адрес: {get_setting('address')}\n⏰ Работа: {get_setting('work_start')}-{get_setting('work_end')}\n⏱️ Перерыв: {get_setting('break_minutes')}мин"
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(types.InlineKeyboardButton("🏷️ Название", callback_data="set_business_name"), types.InlineKeyboardButton("📍 Адрес", callback_data="set_address"))
    kb.add(types.InlineKeyboardButton("⏰ Часы", callback_data="set_work_hours"), types.InlineKeyboardButton("⏱️ Перерыв", callback_data="set_break"))
    bot.send_message(chat_id, msg, reply_markup=kb)

def create_appointment_from_data(chat_id):
    d = user_data.get(chat_id, {})
    cid = d.get("appt_client")
    sid = d.get("appt_service_id","0")
    stext = d.get("appt_service_text","")
    dur = d.get("appt_duration",120)
    price = d.get("appt_price",0)
    date = d.get("appt_date")
    time = d.get("appt_time")
    notes = d.get("appt_notes","")
    app_id = add_appointment(date, time, dur, cid, sid, stext, price, notes)
    c = get_client_by_id(cid)
    msg = f"✅ Запись #{app_id}\n👤 {c['name']}\n💇‍♀️ {stext}\n📅 {date} {time}\n💰 {price} BYN"
    bot.send_message(chat_id, msg)
    if ADMIN_ID: bot.send_message(ADMIN_ID, f"🆕 #{app_id}\n👤 {c['name']}\n📞 {c['phone']}\n💇‍♀️ {stext}\n📅 {date} {time}")
    user_state[chat_id] = None
    user_data[chat_id] = {}

# --- Callback-обработчики ---
@bot.callback_query_handler(func=lambda c: True)
def callback(call):
    chat_id = call.message.chat.id
    data = call.data
    
    if data == "ignore": bot.answer_callback_query(call.id); return
    if data == "appt_new":
        user_state[chat_id] = "APPT_NEW_NAME"
        bot.edit_message_text("👤 Введите имя:", chat_id, call.message.message_id)
    elif data.startswith("appt_client_"):
        cid = data.split("_")[2]
        user_data[chat_id] = {"appt_client": cid}
        show_service_selection(chat_id)
        bot.edit_message_text("Выберите услугу:", chat_id, call.message.message_id)
    elif data.startswith("selsrv_"):
        sid = data.split("_")[1]
        if sid == "manual":
            user_state[chat_id] = "APPT_MANUAL_SERVICE"
            bot.edit_message_text("💇‍♀️ Введите название:", chat_id, call.message.message_id)
        else:
            s = next((x for x in get_active_services() if x['id']==sid), None)
            if s:
                user_data[chat_id]["appt_service_id"] = sid
                user_data[chat_id]["appt_service_text"] = s['name']
                user_data[chat_id]["appt_duration"] = s['duration']
                user_data[chat_id]["appt_price"] = s['price']
                user_state[chat_id] = "APPT_DATE"
                kb = get_calendar_keyboard("appt_date")
                bot.edit_message_text("📅 Выберите дату:", chat_id, call.message.message_id, reply_markup=kb)
    elif data.startswith("appt_date_"):
        date = data.split("_",2)[2]
        user_data[chat_id]["appt_date"] = date
        dur = user_data[chat_id].get("appt_duration",120)
        slots = get_free_slots(date, dur)
        if slots:
            kb = types.InlineKeyboardMarkup(row_width=3)
            for s in slots[:9]: kb.add(types.InlineKeyboardButton(s, callback_data=f"appt_time_{s}"))
            bot.edit_message_text("⏰ Выберите время:", chat_id, call.message.message_id, reply_markup=kb)
        else:
            bot.edit_message_text("Нет свободного времени", chat_id, call.message.message_id)
    elif data.startswith("appt_time_"):
        time = data.split("_",2)[2]
        user_data[chat_id]["appt_time"] = time
        user_state[chat_id] = "APPT_NOTES"
        bot.edit_message_text("📝 Заметка ('-' если нет):", chat_id, call.message.message_id)
    elif data.startswith("done_"):
        app_id = data.split("_")[1]
        update_appointment_status(app_id, "Выполнена")
        bot.edit_message_text(f"✅ #{app_id} выполнена", chat_id, call.message.message_id)
    elif data.startswith("cancel_"):
        app_id = data.split("_")[1]
        update_appointment_status(app_id, "Отмена")
        bot.edit_message_text(f"❌ #{app_id} отменена", chat_id, call.message.message_id)
    elif data == "addsrv":
        user_state[chat_id] = "ADD_SERVICE_NAME"
        bot.edit_message_text("💇‍♀️ Название услуги:", chat_id, call.message.message_id)
    elif data.startswith("editsrv_"):
        sid = data.split("_")[1]
        s = next((x for x in get_all_services() if x['id']==sid), None)
        if s:
            kb = types.InlineKeyboardMarkup(row_width=1)
            kb.add(types.InlineKeyboardButton("✏️ Название", callback_data=f"edt_name_{sid}"), types.InlineKeyboardButton("⏰ Длительность", callback_data=f"edt_dur_{sid}"))
            kb.add(types.InlineKeyboardButton("💰 Цена", callback_data=f"edt_price_{sid}"), types.InlineKeyboardButton("🗑️ Удалить", callback_data=f"delsrv_{sid}"))
            bot.edit_message_text(f"{s['name']} — {s['duration']}мин / {s['price']}BYN", chat_id, call.message.message_id, reply_markup=kb)
    elif data.startswith("edt_name_"):
        sid = data.split("_")[2]
        user_state[chat_id] = f"EDIT_SERVICE_{sid}_NAME"
        bot.edit_message_text("Введите новое название:", chat_id, call.message.message_id)
    elif data.startswith("edt_dur_"):
        sid = data.split("_")[2]
        user_state[chat_id] = f"EDIT_SERVICE_{sid}_DURATION"
        bot.edit_message_text("Введите длительность (мин):", chat_id, call.message.message_id)
    elif data.startswith("edt_price_"):
        sid = data.split("_")[2]
        user_state[chat_id] = f"EDIT_SERVICE_{sid}_PRICE"
        bot.edit_message_text("Введите стоимость:", chat_id, call.message.message_id)
    elif data.startswith("delsrv_"):
        sid = data.split("_")[1]
        delete_service(sid)
        bot.edit_message_text("✅ Удалено", chat_id, call.message.message_id)
        show_services_menu(chat_id)
    elif data.startswith("set_"):
        key = data.replace("set_","")
        user_state[chat_id] = f"SETTING_{key}"
        prompts = {"business_name":"🏷️ Название:","address":"📍 Адрес:","work_hours":"⏰ Часы (10:00-20:00):","break":"⏱️ Перерыв (мин):"}
        bot.edit_message_text(prompts.get(key,"Введите:"), chat_id, call.message.message_id)
    elif data.startswith("cal_"):
        parts = data.split("_")
        if len(parts)>=4:
            y, m, p = int(parts[1]), int(parts[2]), parts[3]
            kb = get_calendar_keyboard(p, y, m)
            bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

# --- Проверка напоминаний ---
def check_reminders():
    now = datetime.now()
    for r in sheet_appointments.get_all_values()[1:]:
        if len(r)>=10 and r[9]=="Ожидание":
            try:
                dt = datetime.strptime(f"{r[1]} {r[2]}", "%Y-%m-%d %H:%M")
                if timedelta(hours=0) < (dt - now) <= timedelta(hours=int(get_setting("reminder_master_hours","1"))):
                    c = get_client_by_id(r[5])
                    bot.send_message(ADMIN_ID, f"🔔 Через час: #{r[0]}\n👤 {c['name'] if c else '—'}\n💇‍♀️ {r[7]}")
            except: pass

def main():
    scheduler.add_job(check_reminders, 'interval', minutes=15)
    scheduler.start()
    try: requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook?drop_pending_updates=true", timeout=10)
    except: pass
    threading.Thread(target=run_flask, daemon=True).start()
    logger.info("🤖 Бот запущен")
    while True:
        try: bot.polling(none_stop=True, timeout=60)
        except Exception as e:
            logger.error(f"Polling error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
