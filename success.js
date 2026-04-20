document.addEventListener('DOMContentLoaded',()=>{
    const closeBtn=document.getElementById('close-btn'),pdfBtn=document.getElementById('pdf-btn');
    const bookingData=loadData('booking'),appointmentData=loadData('appointment');
    
    if(appointmentData)document.getElementById('appointment-id').textContent='#'+appointmentData.id;
    if(bookingData){
        document.getElementById('success-service').textContent=bookingData.service_name;
        document.getElementById('success-datetime').textContent=formatDisplayDate(bookingData.date)+' в '+bookingData.time;
        document.getElementById('success-price').textContent=bookingData.price+' BYN';
    }
    
    closeBtn.addEventListener('click',()=>{clearData();closeApp()});
    pdfBtn.addEventListener('click',()=>{
        const d=bookingData,a=appointmentData,date=formatDisplayDate(d.date);
        const html=`<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Запись #${a.id}</title><style>body{font-family:sans-serif;padding:30px;max-width:400px;margin:0 auto}.ticket{border:2px dashed #007aff;border-radius:20px;padding:30px;background:#f8f8f8}h2{color:#007aff}.row{display:flex;justify-content:space-between;padding:12px 0;border-bottom:1px solid #ddd}.label{color:#666}.value{font-weight:600}.highlight{color:#007aff;font-size:1.2em}</style></head><body><div class="ticket"><h2>🎟️ Запись #${a.id}</h2><div class="row"><span class="label">Услуга:</span><span class="value">${d.service_name}</span></div><div class="row"><span class="label">Дата и время:</span><span class="value highlight">${date} в ${d.time}</span></div><div class="row"><span class="label">Длительность:</span><span class="value">${d.duration} мин</span></div><div class="row"><span class="label">Стоимость:</span><span class="value">${d.price} BYN</span></div><div class="row"><span class="label">Имя:</span><span class="value">${d.name}</span></div><div class="row"><span class="label">Телефон:</span><span class="value">${d.phone}</span></div>${d.notes?`<div class="row"><span class="label">Пожелания:</span><span class="value">${d.notes}</span></div>`:''}</div></body></html>`;
        const blob=new Blob([html],{type:'text/html'});const aEl=document.createElement('a');aEl.href=URL.createObjectURL(blob);aEl.download='zapis_'+a.id+'.html';aEl.click();showToast('Сохранено')
    });
    tg.BackButton.hide();
});
