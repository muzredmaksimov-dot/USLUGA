// app.js
document.addEventListener('DOMContentLoaded', async () => {
    // Элементы
    const screenAction = document.getElementById('screen-action');
    const screenBooking = document.getElementById('screen-booking');
    const screenFind = document.getElementById('screen-find');
    const progressBar = document.getElementById('progress-bar');
    const businessNameEl = document.getElementById('business-name');
    const businessAddressEl = document.getElementById('business-address');
    const bookingTitle = document.getElementById('booking-title');
    const findTitle = document.getElementById('find-title');
    const servicesList = document.getElementById('services-list');
    const clientName = document.getElementById('client-name');
    const clientPhone = document.getElementById('client-phone');
    const clientNotes = document.getElementById('client-notes');
    const continueBtn = document.getElementById('continue-btn');
    const userAvatar = document.getElementById('user-avatar');
    const searchQuery = document.getElementById('search-query');
    const searchBtn = document.getElementById('search-btn');
    const searchResult = document.getElementById('search-result');
    
    let selectedService = null;
    let services = [];
    let currentAction = 'book'; // book, reschedule, cancel
    let foundAppointment = null;
    
    // Заполнение данных из Telegram
    const user = getUserData();
    if (user.first_name) {
        const fullName = user.last_name ? `${user.first_name} ${user.last_name}` : user.first_name;
        clientName.value = fullName;
        userAvatar.textContent = user.first_name.charAt(0).toUpperCase();
    }
    
    // Загрузка настроек и услуг
    try {
        const [settingsRes, servicesRes] = await Promise.all([
            fetch(`${API_URL}/api/settings`),
            fetch(`${API_URL}/api/services`)
        ]);
        
        const settings = await settingsRes.json();
        const servicesData = await servicesRes.json();
        
        businessNameEl.textContent = settings.business_name || 'Запись на услугу';
        if (settings.address) {
            businessAddressEl.textContent = `📍 ${settings.address}`;
        }
        
        services = servicesData.services || [];
        renderServices();
    } catch (error) {
        console.error('Ошибка загрузки:', error);
    }
    
    // Обработчики выбора действия
    document.querySelectorAll('.action-card').forEach(card => {
        card.addEventListener('click', () => {
            const action = card.dataset.action;
            currentAction = action;
            
            if (action === 'book') {
                // Новая запись
                bookingTitle.textContent = 'Новая запись';
                progressBar.style.display = 'flex';
                screenAction.classList.remove('active');
                screenBooking.classList.add('active');
            } else {
                // Перенос или отмена
                findTitle.textContent = action === 'reschedule' ? 'Перенести запись' : 'Отменить запись';
                progressBar.style.display = 'none';
                screenAction.classList.remove('active');
                screenFind.classList.add('active');
            }
        });
    });
    
    // Кнопки "Назад"
    document.getElementById('back-from-booking').addEventListener('click', () => {
        screenBooking.classList.remove('active');
        screenAction.classList.add('active');
        progressBar.style.display = 'flex';
    });
    
    document.getElementById('back-from-find').addEventListener('click', () => {
        screenFind.classList.remove('active');
        screenAction.classList.add('active');
        searchQuery.value = '';
        searchResult.style.display = 'none';
        searchBtn.disabled = true;
    });
    
    // Поиск записи
    searchQuery.addEventListener('input', () => {
        searchBtn.disabled = !searchQuery.value.trim();
    });
    
    searchBtn.addEventListener('click', async () => {
        const query = searchQuery.value.trim();
        searchBtn.disabled = true;
        searchBtn.textContent = 'Поиск...';
        
        try {
            const response = await fetch(`${API_URL}/api/appointment/find?query=${encodeURIComponent(query)}`);
            const data = await response.json();
            
            if (data.appointment) {
                foundAppointment = data.appointment;
                displayAppointment(data.appointment);
            } else {
                searchResult.innerHTML = '<div class="error-message">Запись не найдена</div>';
                searchResult.style.display = 'block';
            }
        } catch (error) {
            showToast('Ошибка поиска');
        } finally {
            searchBtn.disabled = false;
            searchBtn.textContent = 'Найти';
        }
    });
    
    function displayAppointment(app) {
        const statusColors = {
            'Ожидание': '🟡',
            'Выполнена': '✅',
            'Отмена': '❌',
            'Перенесена': '🔄'
        };
        
        searchResult.innerHTML = `
            <div class="appointment-card">
                <div class="appointment-header">
                    <span class="appointment-id">Запись #${app.id}</span>
                    <span class="appointment-status">${statusColors[app.status] || ''} ${app.status}</span>
                </div>
                <div class="appointment-details">
                    <div class="detail-row"><span>Услуга:</span> <span>${app.service}</span></div>
                    <div class="detail-row"><span>Дата:</span> <span>${app.date} в ${app.time}</span></div>
                    <div class="detail-row"><span>Клиент:</span> <span>${app.client_name}</span></div>
                </div>
                <div class="appointment-actions">
                    ${currentAction === 'reschedule' ? 
                        '<button class="primary-btn" id="reschedule-btn">Перенести</button>' : 
                        '<button class="danger-btn" id="cancel-btn">Отменить запись</button>'
                    }
                </div>
            </div>
        `;
        searchResult.style.display = 'block';
        
        if (currentAction === 'reschedule') {
            document.getElementById('reschedule-btn').addEventListener('click', () => {
                saveData('reschedule_appointment', foundAppointment);
                window.location.href = 'calendar.html?mode=reschedule';
            });
        } else {
            document.getElementById('cancel-btn').addEventListener('click', async () => {
                if (confirm('Вы уверены, что хотите отменить запись?')) {
                    try {
                        const response = await fetch(`${API_URL}/api/appointment/cancel`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ appointment_id: foundAppointment.id })
                        });
                        const data = await response.json();
                        if (data.success) {
                            showToast('Запись отменена');
                            setTimeout(() => closeApp(), 1500);
                        }
                    } catch (error) {
                        showToast('Ошибка');
                    }
                }
            });
        }
    }
    
    function renderServices() {
        if (services.length === 0) {
            servicesList.innerHTML = '<div class="loading-state"><span>Нет доступных услуг</span></div>';
            return;
        }
        
        servicesList.innerHTML = services.map(service => `
            <div class="service-card" data-id="${service.id}" data-name="${service.name}" data-duration="${service.duration}" data-price="${service.price}">
                <div class="service-card-header">
                    <span class="service-name">${service.name}</span>
                    <span class="service-price">${service.price} BYN</span>
                </div>
                <div class="service-duration">⏰ ${service.duration} минут</div>
            </div>
        `).join('');
        
        document.querySelectorAll('.service-card').forEach(card => {
            card.addEventListener('click', () => {
                document.querySelectorAll('.service-card').forEach(c => c.classList.remove('selected'));
                card.classList.add('selected');
                selectedService = {
                    id: card.dataset.id,
                    name: card.dataset.name,
                    duration: parseInt(card.dataset.duration),
                    price: parseInt(card.dataset.price)
                };
                validateForm();
            });
        });
    }
    
    function validateForm() {
        const isValid = clientName.value.trim() && 
                       clientPhone.value.trim() && 
                       selectedService;
        continueBtn.disabled = !isValid;
    }
    
    clientName.addEventListener('input', validateForm);
    clientPhone.addEventListener('input', validateForm);
    
    clientPhone.addEventListener('input', (e) => {
        let value = e.target.value.replace(/\D/g, '');
        if (value.length > 0) {
            if (value.startsWith('80')) {
                value = '+375 ' + value.slice(2, 4) + ' ' + value.slice(4, 7) + '-' + value.slice(7, 9) + '-' + value.slice(9, 11);
            } else if (value.startsWith('375')) {
                value = '+' + value.slice(0, 3) + ' ' + value.slice(3, 5) + ' ' + value.slice(5, 8) + '-' + value.slice(8, 10) + '-' + value.slice(10, 12);
            }
            e.target.value = value.slice(0, 20);
        }
    });
    
    continueBtn.addEventListener('click', () => {
        const bookingData = {
            name: clientName.value.trim(),
            phone: clientPhone.value.trim().replace(/\D/g, ''),
            service_id: selectedService.id,
            service_name: selectedService.name,
            duration: selectedService.duration,
            price: selectedService.price,
            notes: clientNotes.value.trim()
        };
        
        saveData('booking', bookingData);
        window.location.href = 'calendar.html';
    });
    
    tg.BackButton.hide();
});
