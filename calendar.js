document.addEventListener('DOMContentLoaded',()=>{
    const backBtn=document.getElementById('back-btn'),currentMonthEl=document.getElementById('current-month'),calendarDays=document.getElementById('calendar-days');
    const prevMonth=document.getElementById('prev-month'),nextMonth=document.getElementById('next-month');
    const timeSection=document.getElementById('time-section'),timeSlots=document.getElementById('time-slots'),continueBtn=document.getElementById('continue-calendar-btn');
    const selectedServiceName=document.getElementById('selected-service-name'),selectedServiceDetails=document.getElementById('selected-service-details');
    
    let currentDate=new Date(),selectedDate=null,selectedTime=null,freeSlots=[];
    const bookingData=loadData('booking');
    if(!bookingData){showToast('Ошибка');setTimeout(()=>window.location.href='index.html',1500);return}
    
    selectedServiceName.textContent=bookingData.service_name;
    selectedServiceDetails.textContent=bookingData.duration+' мин · '+bookingData.price+' BYN';
    backBtn.addEventListener('click',()=>window.location.href='index.html');
    
    function render(){
        const y=currentDate.getFullYear(),m=currentDate.getMonth();
        currentMonthEl.textContent=['Январь','Февраль','Март','Апрель','Май','Июнь','Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь'][m]+' '+y;
        const first=new Date(y,m,1),last=new Date(y,m+1,0);let start=first.getDay()||7;start=start===7?0:start-1;
        let h='';for(let i=0;i<start;i++)h+='<div class="calendar-day empty"></div>';
        const today=new Date();today.setHours(0,0,0,0);
        for(let d=1;d<=last.getDate();d++){const date=new Date(y,m,d),dateStr=formatAPIDate(date),isToday=date.getTime()===today.getTime(),isSelected=selectedDate===dateStr,isPast=date<today;
            let cls='calendar-day';if(isToday)cls+=' today';if(isSelected)cls+=' selected';if(isPast)cls+=' disabled';
            h+=isPast?`<div class="${cls}">${d}</div>`:`<div class="${cls}" data-date="${dateStr}">${d}</div>`}
        calendarDays.innerHTML=h;
        document.querySelectorAll('.calendar-day[data-date]').forEach(d=>d.addEventListener('click',()=>selectDate(d.dataset.date)))
    }
    
    async function selectDate(d){selectedDate=d;selectedTime=null;continueBtn.disabled=true;
        document.querySelectorAll('.calendar-day').forEach(x=>x.classList.remove('selected'));document.querySelector(`[data-date="${d}"]`)?.classList.add('selected');
        timeSlots.innerHTML='<div class="loading-state"><div class="spinner"></div></div>';timeSection.style.display='block';
        try{const r=await fetch(API_URL+'/api/slots?date='+d+'&service_id='+bookingData.service_id);const data=await r.json();freeSlots=data.slots||[];
            if(!freeSlots.length)timeSlots.innerHTML='<div class="loading-state"><span>Нет времени</span></div>';
            else{timeSlots.innerHTML=freeSlots.map(s=>`<div class="time-slot" data-time="${s}">${s}</div>`).join('');document.querySelectorAll('.time-slot').forEach(s=>s.addEventListener('click',()=>{document.querySelectorAll('.time-slot').forEach(x=>x.classList.remove('selected'));s.classList.add('selected');selectedTime=s.dataset.time;continueBtn.disabled=false}))}
        }catch(e){timeSlots.innerHTML='<div class="loading-state"><span>Ошибка</span></div>'}
    }
    
    prevMonth.addEventListener('click',()=>{currentDate.setMonth(currentDate.getMonth()-1);render();timeSection.style.display='none';continueBtn.disabled=true});
    nextMonth.addEventListener('click',()=>{currentDate.setMonth(currentDate.getMonth()+1);render();timeSection.style.display='none';continueBtn.disabled=true});
    continueBtn.addEventListener('click',()=>{if(selectedDate&&selectedTime){bookingData.date=selectedDate;bookingData.time=selectedTime;saveData('booking',bookingData);window.location.href='confirm.html'}});
    render();tg.BackButton.show();tg.BackButton.onClick(()=>window.location.href='index.html');
});
