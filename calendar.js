// calendar.js
document.addEventListener('DOMContentLoaded', () => {
    const backBtn = document.getElementById('back-btn');
    const currentMonthEl = document.getElementById('current-month');
    const calendarDays = document.getElementById('calendar-days');
    const prevMonthBtn = document.getElementById('prev-month');
    const nextMonthBtn = document.getElementById('next-month');
    const timeSection = document.getElementById('time-section');
    const timeSlots = document.getElementById('time-slots');
    const continueBtn = document.getElementById('continue-calendar-btn');
    const selectedServiceName = document.getElementById('selected-service-name');
    const selectedServiceDetails = document.getElementById('selected-service-details');
    
    let currentDate = new Date();
    let selectedDate = null;
    let selectedTime = null;
    let freeSlots = [];
    
    const bookingData = loadData('booking');
    if (!bookingData) {
        showToast('Ошибка: данные не найдены');
        setTimeout(() => window.location.href = 'index.html', 1500);
        return;
    }
    
    // Отображение информации о выбранной услуге
    selectedServiceName.textContent = bookingData.service_name;
    selectedServiceDetails.textContent = `${bookingData.duration} минут · ${bookingData.price} BYN`;
    
    backBtn.addEventListener('click', () => {
        window.location.href = 'index.html';
    });
    
    function renderCalendar() {
        const year = currentDate.getFullYear();
        const month = currentDate.getMonth();
        
        const monthNames = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
                           'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'];
        currentMonthEl.textContent = `${monthNames[month]} ${year}`;
        
        const firstDay = new Date(year, month, 1);
        const lastDay = new Date(year, month + 1, 0);
        let startDay = firstDay.getDay() || 7;
        startDay = startDay === 7 ? 0 : startDay - 1;
        
        let daysHtml = '';
        
        for (let i = 0; i < startDay; i++) {
            daysHtml += '<div class="calendar-day empty"></div>';
        }
        
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        
        for (let d = 1; d <= lastDay.getDate(); d++) {
            const date = new Date(year, month, d);
            const dateStr = formatAPIDate(date);
            const isToday = date.getTime() === today.getTime();
            const isSelected = selectedDate === dateStr;
            const isPast = date < today;
            
            let classes = 'calendar-day';
            if (isToday) classes += ' today';
            if (isSelected) classes += ' selected';
            if (isPast) classes += ' disabled';
            
            if (isPast) {
                daysHtml += `<div class="${classes}">${d}</div>`;
            } else {
                daysHtml += `<div class="${classes}" data-date="${dateStr}">${d}</div>`;
            }
        }
        
        calendarDays.innerHTML = daysHtml;
        
        document.querySelectorAll('.calendar-day[data-date]').forEach(day => {
            day.addEventListener('click', () => selectDate(day.dataset.date));
        });
    }
    
    async function selectDate(dateStr) {
        selectedDate = dateStr;
        selectedTime = null;
        continueBtn.disabled = true;
        
        document.querySelectorAll('.calendar-day').forEach(d => d.classList.remove('selected'));
        document.querySelector(`[data-date="${dateStr}"]`)?.classList.add('selected');
        
        // Загрузка свободных слотов
        timeSlots.innerHTML = '<div class="loading-state"><div class="spinner"></div><span>Загрузка времени...</span></div>';
        timeSection.style.display = 'block';
        
        try {
            const response = await fetch(`${API_URL}/api/slots?date=${dateStr}&service_id=${bookingData.service_id}`);
            const data = await response.json();
            freeSlots = data.slots || [];
            
            if (freeSlots.length === 0) {
                timeSlots.innerHTML = '<div class="loading-state"><span>Нет свободного времени на эту дату</span></div>';
            } else {
                renderTimeSlots();
            }
        } catch (error) {
            console.error('Ошибка загрузки слотов:', error);
            timeSlots.innerHTML = '<div class="loading-state"><span>Ошибка загрузки</span></div>';
        }
    }
    
    function renderTimeSlots() {
        timeSlots.innerHTML = freeSlots.map(slot => `
            <div class="time-slot" data-time="${slot}">${slot}</div>
        `).join('');
        
        document.querySelectorAll('.time-slot').forEach(slot => {
            slot.addEventListener('click', () => {
                document.querySelectorAll('.time-slot').forEach(s => s.classList.remove('selected'));
                slot.classList.add('selected');
                selectedTime = slot.dataset.time;
                continueBtn.disabled = false;
            });
        });
    }
    
    prevMonthBtn.addEventListener('click', () => {
        currentDate.setMonth(currentDate.getMonth() - 1);
        renderCalendar();
        timeSection.style.display = 'none';
        selectedDate = null;
        selectedTime = null;
        continueBtn.disabled = true;
    });
    
    nextMonthBtn.addEventListener('click', () => {
        const today = new Date();
        const nextMonth = new Date(currentDate);
        nextMonth.setMonth(nextMonth.getMonth() + 1);
        
        currentDate = nextMonth;
        renderCalendar();
        timeSection.style.display = 'none';
        selectedDate = null;
        selectedTime = null;
        continueBtn.disabled = true;
    });
    
    continueBtn.addEventListener('click', () => {
        if (selectedDate && selectedTime) {
            bookingData.date = selectedDate;
            bookingData.time = selectedTime;
            saveData('booking', bookingData);
            window.location.href = 'confirm.html';
        }
    });
    
    renderCalendar();
    
    tg.BackButton.show();
    tg.BackButton.onClick(() => {
        window.location.href = 'index.html';
    });
});
