// success.js
document.addEventListener('DOMContentLoaded', () => {
    const closeBtn = document.getElementById('close-btn');
    const pdfBtn = document.getElementById('pdf-btn');
    const bookingData = loadData('booking');
    const appointmentData = loadData('appointment');
    
    console.log('Success - booking:', bookingData);
    console.log('Success - appointment:', appointmentData);
    
    // Заполняем данные
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
    
    // Кнопка "Закрыть"
    if (closeBtn) {
        closeBtn.addEventListener('click', () => {
            clearData();
            closeApp();
        });
    }
    
    // Кнопка "Сохранить PDF" — генерация реального PDF
    if (pdfBtn) {
        pdfBtn.addEventListener('click', generatePDF);
    }
    
    tg.BackButton.hide();
});

async function generatePDF() {
    const bookingData = loadData('booking');
    const appointmentData = loadData('appointment');
    
    if (!bookingData || !appointmentData) {
        showToast('Нет данных для сохранения');
        return;
    }
    
    showToast('Создание PDF...');
    
    // Динамически загружаем библиотеки
    await loadScript('https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js');
    await loadScript('https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js');
    
    const { jsPDF } = window.jspdf;
    
    // Создаём временный элемент для рендера
    const ticket = document.createElement('div');
    ticket.style.cssText = `
        position: fixed;
        left: -9999px;
        width: 400px;
        padding: 30px;
        background: white;
        font-family: -apple-system, BlinkMacSystemFont, 'Helvetica Neue', sans-serif;
        color: #000;
    `;
    
    const displayDate = formatDisplayDate(bookingData.date);
    
    ticket.innerHTML = `
        <div style="border: 2px dashed #007aff; border-radius: 20px; padding: 30px; background: #f8f8f8;">
            <h2 style="color: #007aff; margin-bottom: 20px; text-align: center;">🎟️ Запись подтверждена</h2>
            <div style="border-bottom: 1px solid #ddd; padding: 12px 0; display: flex; justify-content: space-between;">
                <span style="color: #666;">Номер записи:</span>
                <span style="font-weight: 600;">#${appointmentData.id}</span>
            </div>
            <div style="border-bottom: 1px solid #ddd; padding: 12px 0; display: flex; justify-content: space-between;">
                <span style="color: #666;">Услуга:</span>
                <span style="font-weight: 600;">${bookingData.service_name}</span>
            </div>
            <div style="border-bottom: 1px solid #ddd; padding: 12px 0; display: flex; justify-content: space-between;">
                <span style="color: #666;">Дата и время:</span>
                <span style="font-weight: 600; color: #007aff; font-size: 1.1em;">${displayDate} в ${bookingData.time}</span>
            </div>
            <div style="border-bottom: 1px solid #ddd; padding: 12px 0; display: flex; justify-content: space-between;">
                <span style="color: #666;">Длительность:</span>
                <span style="font-weight: 600;">${bookingData.duration} минут</span>
            </div>
            <div style="border-bottom: 
