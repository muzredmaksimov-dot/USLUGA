// app.js
document.addEventListener('DOMContentLoaded', async () => {
    const businessNameEl = document.getElementById('business-name');
    const businessAddressEl = document.getElementById('business-address');
    const servicesList = document.getElementById('services-list');
    const clientName = document.getElementById('client-name');
    const clientPhone = document.getElementById('client-phone');
    const clientNotes = document.getElementById('client-notes');
    const continueBtn = document.getElementById('continue-btn');
    const userAvatar = document.getElementById('user-avatar');
    
    let selectedService = null;
    let services = [];
    
    // Заполнение данных из Telegram
    const user = getUserData();
    if (user.first_name) {
        const fullName = user.last_name ? `${user.first_name} ${user.last_name}` : user.first_name;
        clientName.value = fullName;
    }
    
    // Аватар пользователя
    if (user.first_name) {
        userAvatar.textContent = user.first_name.charAt(0).toUpperCase();
    } else {
        userAvatar.textContent = '👤';
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
        } else {
            businessAddressEl.style.display = 'none';
        }
        
        services = servicesData.services || [];
        renderServices();
        
        // Восстановление выбранной услуги
        const saved = loadData('booking');
        if (saved && saved.service_id) {
            selectedService = services.find(s => s.id === saved.service_id);
            highlightSelected();
        }
    } catch (error) {
        console.error('Ошибка загрузки:', error);
        servicesList.innerHTML = '<div class="loading-state"><span>Ошибка загрузки</span></div>';
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
        
        highlightSelected();
    }
    
    function highlightSelected() {
        if (selectedService) {
            document.querySelectorAll('.service-card').forEach(card => {
                if (card.dataset.id === selectedService.id) {
                    card.classList.add('selected');
                }
            });
        }
        validateForm();
    }
    
    function validateForm() {
        const isValid = clientName.value.trim() && 
                       clientPhone.value.trim() && 
                       selectedService;
        continueBtn.disabled = !isValid;
    }
    
    clientName.addEventListener('input', validateForm);
    clientPhone.addEventListener('input', validateForm);
    
    // Форматирование телефона
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
    
    // Кнопка "Назад" в Telegram
    tg.BackButton.hide();
    
    // Восстановление из sessionStorage
    const saved = loadData('booking');
    if (saved) {
        clientName.value = saved.name || '';
        clientPhone.value = saved.phone || '';
        clientNotes.value = saved.notes || '';
        validateForm();
    }
});
