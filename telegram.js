// telegram.js
const tg = window.Telegram.WebApp;

// Инициализация
tg.ready();
tg.expand();

// Настройка темы
function applyTheme() {
    const theme = tg.colorScheme || 'light';
    document.documentElement.style.setProperty('--tg-theme-bg-color', tg.backgroundColor || (theme === 'dark' ? '#1c1c1e' : '#ffffff'));
    document.documentElement.style.setProperty('--tg-theme-text-color', tg.textColor || (theme === 'dark' ? '#ffffff' : '#000000'));
    document.documentElement.style.setProperty('--tg-theme-hint-color', tg.hintColor || '#8e8e93');
    document.documentElement.style.setProperty('--tg-theme-link-color', tg.linkColor || (theme === 'dark' ? '#0a84ff' : '#007aff'));
    document.documentElement.style.setProperty('--tg-theme-button-color', tg.buttonColor || (theme === 'dark' ? '#0a84ff' : '#007aff'));
    document.documentElement.style.setProperty('--tg-theme-button-text-color', tg.buttonTextColor || '#ffffff');
    document.documentElement.style.setProperty('--tg-theme-secondary-bg-color', tg.secondaryBackgroundColor || (theme === 'dark' ? '#2c2c2e' : '#f2f2f7'));
}

applyTheme();
tg.onEvent('themeChanged', applyTheme);

// Получение данных пользователя
function getUserData() {
    return {
        id: tg.initDataUnsafe?.user?.id || null,
        first_name: tg.initDataUnsafe?.user?.first_name || '',
        username: tg.initDataUnsafe?.user?.username || ''
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
