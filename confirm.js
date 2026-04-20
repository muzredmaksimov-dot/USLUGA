// confirm.js
document.addEventListener('DOMContentLoaded', () => {
    console.log('Confirm page loaded');
    
    const backBtn = document.getElementById('back-btn');
    const confirmBtn = document.getElementById('confirm-btn');
    
    // Загружаем данные
    const bookingData = loadData('booking');
    console.log('Booking data:', bookingData);
    
    if (!bookingData) {
        console.error('No booking data found');
        showToast('Ошибка: данные не найдены');
        setTimeout(() => window.location.href = 'index.html', 1500);
        return;
    }
    
    // Заполняем поля
    const fields = {
        'confirm-service': bookingData.service_name || '—',
        'confirm-duration': `${bookingData.duration || 0} минут`,
        'confirm-price': `${bookingData.price || 0} BYN`,
        'confirm-name': bookingData.name || '—',
        'confirm-phone': bookingData.phone || '—'
    };
    
    // Дата и время
    if (bookingData.date && bookingData.time) {
        const displayDate = formatDisplayDate(bookingData.date);
        fields['confirm-datetime'] = `${displayDate} в ${bookingData.time}`;
    }
    
    // Заполняем все поля
    for (const [id, value] of Object.entries(fields)) {
        const el = document.getElementById(id);
        if (el) {
            el.textContent = value;
            console.log(`Set ${id} = ${value}`);
        } else {
            console.error(`Element #${id} not found`);
        }
    }
    
    // Заметки
    if (bookingData.notes) {
        const notesRow = document.getElementById('notes-row');
        const confirmNotes = document.getElementById('confirm-notes');
        if (notesRow) notesRow.style.display = 'flex';
        if (confirmNotes) confirmNotes.textContent = bookingData.notes;
    }
    
    // Кнопка Назад
    backBtn.addEventListener('click', () => {
        window.location.href = 'calendar.html';
    });
    
    // Кнопка Подтвердить
    confirmBtn.addEventListener('click', async () => {
        console.log('Confirm button clicked');
        confirmBtn.disabled = true;
        confirmBtn.textContent = 'Отправка...';
        
        try {
            const user = getUserData();
            console.log('User data:', user);
            
            const requestData = {
                name: bookingData.name,
                phone: bookingData.phone,
                service_id: bookingData.service_id,
                date: bookingData.date,
                time: bookingData.time,
                notes: bookingData.notes || '',
                telegram_id: user.id || null
            };
            
            console.log('Sending request:', requestData);
            
            const response = await fetch(`${API_URL}/api/appointment`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(requestData)
            });
            
            const result = await response.json();
            console.log('Response:', result);
            
            if (result.success) {
                saveData('appointment', { 
                    id: result.appointment_id, 
                    ...bookingData 
                });
                showToast('Запись создана!');
                window.location.href = 'success.html';
            } else {
                showToast(result.error || 'Ошибка создания записи');
                confirmBtn.disabled = false;
                confirmBtn.textContent = 'Подтвердить запись';
            }
        } catch (error) {
            console.error('Fetch error:', error);
            showToast('Ошибка соединения с сервером');
            confirmBtn.disabled = false;
            confirmBtn.textContent = 'Подтвердить запись';
        }
    });
    
    tg.BackButton.show();
    tg.BackButton.onClick(() => {
        window.location.href = 'calendar.html';
    });
});
