// telegram.js
const tg = window.Telegram.WebApp;

// Инициализация
tg.ready();
tg.expand();

// Настройка темы
function applyTheme() {
    const themeParams = tg.themeParams;
    
    if (themeParams.bg_color) {
        document.documentElement.style.setProperty('--bg-primary', themeParams.bg_color);
    }
    if (themeParams.secondary_bg_color) {
        document.documentElement.style.setProperty('--bg-secondary', themeParams.secondary_bg_color);
    }
    if (themeParams.text_color) {
        document.documentElement.style.setProperty('--text-primary', themeParams.text_color);
    }
    if (themeParams.hint_color) {
        document.documentElement.style.setProperty('--text-secondary', themeParams.hint_color);
    }
    if (themeParams.button_color) {
        document.documentElement.style.setProperty('--primary', themeParams.button_color);
    }
    if (themeParams.button_text_color) {
        document.documentElement.style.setProperty('--button-text', themeParams.button_text_color);
    }
}

applyTheme();
tg.onEvent('themeChanged', applyTheme);

// Получение данных пользователя
function getUserData() {
    const user = tg.initDataUnsafe?.user;
    return {
        id: user?.id || null,
        first_name: user?.first_name || '',
        last_name: user?.last_name || '',
        username: user?.username || '',
        photo_url: user?.photo_url || ''
    };
}

// Показ toast-уведомления
function showToast(message, duration = 2000) {
    const toast = document.getElementById('toast');
    if (toast) {
        toast.textContent = message;
        toast.classList.add('show');
        setTimeout(() => {
            toast.classList.remove('show');
        }, duration);
    }
}

// Сохранение данных в sessionStorage
function saveData(key, data) {
    sessionStorage.setItem(key, JSON.stringify(data));
}

function loadData(key) {
    const data = sessionStorage.getItem(key);
    return data ? JSON.parse(data) : null;
}

function clearData() {
    sessionStorage.clear();
}

// API URL
const API_URL = window.location.origin;

// Закрытие Mini App
function closeApp() {
    tg.close();
}

// Форматирование даты для отображения
function formatDisplayDate(dateStr) {
    const [year, month, day] = dateStr.split('-');
    const monthNames = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
                       'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'];
    return `${parseInt(day)} ${monthNames[parseInt(month) - 1]}`;
}

// Форматирование даты для API
function formatAPIDate(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}
