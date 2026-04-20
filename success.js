// success.js
document.addEventListener('DOMContentLoaded', () => {
    const closeBtn = document.getElementById('close-btn');
    const appointmentIdEl = document.getElementById('appointment-id');
    const successService = document.getElementById('success-service');
    const successDatetime = document.getElementById('success-datetime');
    const successPrice = document.getElementById('success-price');
    
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
    
    // Кнопка "Сохранить PDF"
    const pdfBtn = document.getElementById('pdf-btn');
    if (pdfBtn) {
        pdfBtn.addEventListener('click', generatePDF);
    }
    
    tg.BackButton.hide();
    
    // Добавляем кнопку PDF, если её нет
    const footer = document.querySelector('.success-screen');
    if (footer && !document.getElementById('pdf-btn')) {
        const pdfButton = document.createElement('button');
        pdfButton.id = 'pdf-btn';
        pdfButton.className = 'secondary-btn';
        pdfButton.textContent = '📄 Сохранить как PDF';
        pdfButton.style.marginTop = '12px';
        pdfButton.addEventListener('click', generatePDF);
        closeBtn.parentNode.insertBefore(pdfButton, closeBtn);
    }
});

function generatePDF() {
    const bookingData = loadData('booking');
    const appointmentData = loadData('appointment');
    
    if (!bookingData || !appointmentData) {
        showToast('Нет данных для сохранения');
        return;
    }
    
    const displayDate = formatDisplayDate(bookingData.date);
    
    // Создаём HTML для PDF
    const html = `
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Запись #${appointmentData.id}</title>
            <style>
                body {
                    font-family: -apple-system, BlinkMacSystemFont, 'Helvetica Neue', sans-serif;
                    padding: 30px;
                    max-width: 400px;
                    margin: 0 auto;
                }
                .ticket {
                    border: 2px dashed #007aff;
                    border-radius: 20px;
                    padding: 30px;
                    background: #f8f8f8;
                }
                h2 {
                    color: #007aff;
                    margin-bottom: 20px;
                }
                .row {
                    display: flex;
                    justify-content: space-between;
                    padding: 12px 0;
                    border-bottom: 1px solid #ddd;
                }
                .label {
                    color: #666;
                }
                .value {
                    font-weight: 600;
                }
                .highlight {
                    color: #007aff;
                    font-size: 1.2em;
                }
                .footer {
                    margin-top: 30px;
                    text-align: center;
                    color: #666;
                }
            </style>
        </head>
        <body>
            <div class="ticket">
                <h2>🎟️ Запись подтверждена</h2>
                <div class="row">
                    <span class="label">Номер записи:</span>
                    <span class="value">#${appointmentData.id}</span>
                </div>
                <div class="row">
                    <span class="label">Услуга:</span>
                    <span class="value">${bookingData.service_name}</span>
                </div>
                <div class="row">
                    <span class="label">Дата и время:</span>
                    <span class="value highlight">${displayDate} в ${bookingData.time}</span>
                </div>
                <div class="row">
                    <span class="label">Длительность:</span>
                    <span class="value">${bookingData.duration} минут</span>
                </div>
                <div class="row">
                    <span class="label">Стоимость:</span>
                    <span class="value">${bookingData.price} BYN</span>
                </div>
                <div class="row">
                    <span class="label">Имя:</span>
                    <span class="value">${bookingData.name}</span>
                </div>
                <div class="row">
                    <span class="label">Телефон:</span>
                    <span class="value">${bookingData.phone}</span>
                </div>
                ${bookingData.notes ? `
                <div class="row">
                    <span class="label">Пожелания:</span>
                    <span class="value">${bookingData.notes}</span>
                </div>
                ` : ''}
                <div class="footer">
                    Спасибо за запись! ❤️
                </div>
            </div>
        </body>
        </html>
    `;
    
    // Создаём Blob и скачиваем
    const blob = new Blob([html], { type: 'text/html' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `zapis_${appointmentData.id}.html`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    showToast('Файл сохранён!');
}
