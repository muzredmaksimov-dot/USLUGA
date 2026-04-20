// telegram.js
const tg = window.Telegram.WebApp;

tg.ready();
tg.expand();

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
}

applyTheme();
tg.onEvent('themeChanged', applyTheme);

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

function showToast(message, duration = 2000) {
    const toast = document.getElementById('toast');
    if (toast) {
        toast.textContent = message;
        toast.classList.add('show');
        setTimeout(() => {
            toast.classList.remove('show');
        }, duration);
    } else {
        alert(message);
    }
}

function saveData(key, data) {
    try {
        sessionStorage.setItem(key, JSON.stringify(data));
        console.log(`Saved ${key}:`, data);
    } catch (e) {
        console.error(`Error saving ${key}:`, e);
    }
}

function loadData(key) {
    try {
        const data = sessionStorage.getItem(key);
        const parsed = data ? JSON.parse(data) : null;
        console.log(`Loaded ${key}:`, parsed);
        return parsed;
    } catch (e) {
        console.error(`Error loading ${key}:`, e);
        return null;
    }
}

function clearData() {
    sessionStorage.clear();
}

const API_URL = window.location.origin;

function closeApp() {
    tg.close();
}

function formatDisplayDate(dateStr) {
    if (!dateStr) return '';
    const parts = dateStr.split('-');
    if (parts.length !== 3) return dateStr;
    
    const year = parts[0];
    const month = parseInt(parts[1]);
    const day = parseInt(parts[2]);
    
    const monthNames = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
                       'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'];
    return `${day} ${monthNames[month - 1]}`;
}

function formatAPIDate(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}
