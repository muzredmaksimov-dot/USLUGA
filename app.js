// app.js
document.addEventListener('DOMContentLoaded', async () => {
    const businessNameEl = document.getElementById('business-name');
    const businessAddressEl = document.getElementById('business-address');
    const servicesList = document.getElementById('services-list');
    const clientName = document.getElementById('client-name');
    const clientPhone = document.getElementById('client-phone');
    const clientNotes = document.getElementById('client-notes');
    const continueBtn = document.getElementById('continue-btn');
    
    let selectedService = null;
    let services = [];
    
    // Автозаполнение имени из Telegram
    const user = getUserData();
    if (user.first_name) {
        clientName.value = user.first_name;
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
        
        // Восстановление выбранной услуги
        const saved = loadData('booking');
        if (saved && saved.service_id) {
            selectedService = services.find(s => s.id === saved.service_id);
            highlightSelected();
        }
    } catch (error) {
        console.error('Ошибка загрузки:', error);
        servicesList.innerHTML = '<div class="loading">Ошибка загрузки</div>';
    }
    
    function renderServices() {
        if (services.length === 0) {
            servicesList.innerHTML = '<div class="loading">Нет доступных услуг</div>';
            return;
        }
        
        servicesList.innerHTML = services.map(service => `
            <div class="service-card" data-id="${service.id}" data-name="${service.name}" data-duration="${service.duration}" data-price="${service.price}">
                <div class="service-name">${service.name}</div>
                <div class="service-details">
                    <span>⏰ ${service.duration} мин</span>
                    <span>💰 ${service.price} BYN</span>
                </div>
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
    
    continueBtn.addEventListener('click', () => {
        const bookingData = {
            name: clientName.value.trim(),
            phone: clientPhone.value.trim(),
            service_id: selectedService.id,
            service_name: selectedService.name,
            duration: selectedService.duration,
            price: selectedService.price,
            notes: clientNotes.value.trim()
        };
        
        saveData('booking', bookingData);
        window.location.href = 'calendar.html';
    });
    
    // Обработка кнопки "Назад" в Telegram
    tg.BackButton.hide();
});
