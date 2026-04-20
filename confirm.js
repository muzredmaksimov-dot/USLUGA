// confirm.js
document.addEventListener('DOMContentLoaded', () => {
    const backBtn = document.getElementById('back-btn');
    const confirmBtn = document.getElementById('confirm-btn');
    
    const bookingData = loadData('booking');
    
    if (!bookingData) {
        showToast('Ошибка: данные не найдены');
        setTimeout(() => window.location.href = 'index.html', 1500);
        return;
    }
    
    // Заполнение данных с проверкой
    const confirmService = document.getElementById('confirm-service');
    const confirmDatetime = document.getElementById('confirm-datetime');
    const confirmDuration = document.getElementById('confirm-duration');
    const confirmPrice = document.getElementById('confirm-price');
    const confirmName = document.getElementById('confirm-name');
    const confirmPhone = document.getElementById('confirm-phone');
    const notesRow = document.getElementById('notes-row');
    const confirmNotes = document.getElementById('confirm-notes');
    
    if (confirmService) confirmService.textContent = bookingData.service_name || '—';
    
    if (confirmDatetime && bookingData.date && bookingData.time) {
        const displayDate = formatDisplayDate(bookingData.date);
        confirmDatetime.textContent = `${displayDate} в ${bookingData.time}`;
    }
    
    if (confirmDuration) confirmDuration.textContent = `${bookingData.duration || 0} минут`;
    if (confirmPrice) confirmPrice.textContent = `${bookingData.price || 0} BYN`;
    if (confirmName) confirmName.textContent = bookingData.name || '—';
    if (confirmPhone) confirmPhone.textContent = bookingData.phone || '—';
    
    if (bookingData.notes) {
        if (notesRow) notesRow.style.display = 'flex';
        if (confirmNotes) confirmNotes.textContent = bookingData.notes;
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
                saveData('appointment', { 
                    id: result.appointment_id, 
                    ...bookingData 
                });
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
    
    tg.BackButton.show();
    tg.BackButton.onClick(() => {
        window.location.href = 'calendar.html';
    });
});
```

---

📄 5. success.js — Исправленное отображение

```javascript
// success.js
document.addEventListener('DOMContentLoaded', () => {
    const closeBtn = document.getElementById('close-btn');
    const appointmentIdEl = document.getElementById('appointment-id');
    const successService = document.getElementById('success-service');
    const successDatetime = document.getElementById('success-datetime');
    const successPrice = document.getElementById('success-price');
    
    const bookingData = loadData('booking');
    const appointmentData = loadData('appointment');
    
    if (appointmentIdEl && appointmentData) {
        appointmentIdEl.textContent = `#${appointmentData.id}`;
    }
    
    if (bookingData) {
        if (successService) successService.textContent = bookingData.service_name || '—';
        if (successPrice) successPrice.textContent = `${bookingData.price || 0} BYN`;
        
        if (successDatetime && bookingData.date && bookingData.time) {
            const displayDate = formatDisplayDate(bookingData.date);
            successDatetime.textContent = `${displayDate} в ${bookingData.time}`;
        }
    }
    
    closeBtn.addEventListener('click', () => {
        clearData();
        closeApp();
    });
    
    tg.BackButton.hide();
});
