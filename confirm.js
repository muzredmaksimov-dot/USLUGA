document.addEventListener('DOMContentLoaded',()=>{
    const backBtn=document.getElementById('back-btn'),confirmBtn=document.getElementById('confirm-btn');
    const bookingData=loadData('booking');
    if(!bookingData){showToast('Ошибка');setTimeout(()=>window.location.href='index.html',1500);return}
    
    document.getElementById('confirm-service').textContent=bookingData.service_name;
    document.getElementById('confirm-datetime').textContent=formatDisplayDate(bookingData.date)+' в '+bookingData.time;
    document.getElementById('confirm-duration').textContent=bookingData.duration+' минут';
    document.getElementById('confirm-price').textContent=bookingData.price+' BYN';
    document.getElementById('confirm-name').textContent=bookingData.name;
    document.getElementById('confirm-phone').textContent=bookingData.phone;
    if(bookingData.notes){document.getElementById('notes-row').style.display='flex';document.getElementById('confirm-notes').textContent=bookingData.notes}
    
    backBtn.addEventListener('click',()=>window.location.href='calendar.html');
    confirmBtn.addEventListener('click',async()=>{
        confirmBtn.disabled=true;confirmBtn.textContent='Отправка...';
        try{
            const r=await fetch(API_URL+'/api/appointment',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:bookingData.name,phone:bookingData.phone,service_id:bookingData.service_id,date:bookingData.date,time:bookingData.time,notes:bookingData.notes})});
            const d=await r.json();
            if(d.success){saveData('appointment',{id:d.appointment_id,...bookingData});window.location.href='success.html'}
            else{showToast(d.error||'Ошибка');confirmBtn.disabled=false;confirmBtn.textContent='Подтвердить запись'}
        }catch(e){showToast('Ошибка соединения');confirmBtn.disabled=false;confirmBtn.textContent='Подтвердить запись'}
    });
    tg.BackButton.show();tg.BackButton.onClick(()=>window.location.href='calendar.html');
});
