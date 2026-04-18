// success.js
document.addEventListener('DOMContentLoaded', () => {
    const closeBtn = document.getElementById('close-btn');
    const successDetails = document.getElementById('success-details');
    
    const bookingData = loadData('booking');
    const appointmentData = loadData('appointment');
    
    if (bookingData && appointmentData) {
        const displayDate = formatDisplayDate(bookingData.date);
        
        successDetails.innerHTML = `
            <div class="detail-row">
                <span class="detail-label">Номер записи</span>
                <span class="detail-value">#${appointmentData.id}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Услуга</span>
                <span class="detail-value">${bookingData.service_name}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Дата и время</span>
                <span class="detail-value">${displayDate} в ${bookingData.time}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Стоимость</span>
                <span class="detail-value">${bookingData.price} BYN</span>
            </div>
        `;
    }
    
    closeBtn.addEventListener('click', () => {
        clearData();
        closeApp();
    });
    
    function formatDisplayDate(dateStr) {
        const [year, month, day] = dateStr.split('-');
        const monthNames = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
                           'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'];
        return `${parseInt(day)} ${monthNames[parseInt(month) - 1]}`;
    }
    
    tg.BackButton.hide();
});
