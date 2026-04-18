document.addEventListener('DOMContentLoaded', () => {
    const backBtn = document.getElementById('back-btn');
    const confirmBtn = document.getElementById('confirm-btn');
    
    const bookingData = loadData('booking');
    if (!bookingData) {
        showToast('Ошибка: данные не найдены');
        setTimeout(() => window.location.href = 'index.html', 1500);
        return;
    }
    
    // Заполнение данных
    document.getElementById('confirm-service').textContent = bookingData.service_name;
    
    const displayDate = formatDisplayDate(bookingData.date);
    document.getElementById('confirm-datetime').textContent = `${displayDate} в ${bookingData.time}`;
    document.getElementById('confirm-duration').textContent = `${bookingData.duration} минут`;
    document.getElementById('confirm-price').textContent = `${bookingData.price} BYN`;
    document.getElementById('confirm-name').textContent = bookingData.name;
    document.getElementById('confirm-phone').textContent = bookingData.phone;
    
    if (bookingData.notes) {
        document.getElementById('notes-row').style.display = 'flex';
        document.getElementById('confirm-notes').textContent = bookingData.notes;
    }
    
    backBtn.addEventListener('click', () => {
        window.location.href = 'calendar.html';
    });
    
    confirmBtn.addEventListener('click', async () => {
        confirmBtn.disabled = true;
        confirmBtn.textContent = 'Отправка...';
        
        try {
            const user = getUserData();
            
            const response = await fetch(`${API_URL}/api/appointment`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name: bookingData.name,
                    phone: bookingData.phone,
                    service_id: bookingData.service_id,
                    date: bookingData.date,
                    time: bookingData.time,
                    notes: bookingData.notes,
                    telegram_id: user.id
                })
            });
            
            const result = await response.json();
            
            if (result.success) {
                saveData('appointment', { id: result.appointment_id, ...bookingData });
                window.location.href = 'success.html';
            } else {
                showToast(result.error || 'Ошибка создания записи');
                confirmBtn.disabled = false;
                confirmBtn.textContent = 'Подтвердить запись';
            }
        } catch (error) {
            console.error('Ошибка:', error);
            showToast('Ошибка соединения');
            confirmBtn.disabled = false;
            confirmBtn.textContent = 'Подтвердить запись';
        }
    });
    
    function formatDisplayDate(dateStr) {
        const [year, month, day] = dateStr.split('-');
        const monthNames = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
                           'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'];
        return `${parseInt(day)} ${monthNames[parseInt(month) - 1]}`;
    }
    
    tg.BackButton.show();
    tg.BackButton.onClick(() => {
        window.location.href = 'calendar.html';
    });
});
