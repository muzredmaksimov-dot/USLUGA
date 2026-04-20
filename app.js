document.addEventListener('DOMContentLoaded',async()=>{
    const screenAction=document.getElementById('screen-action'),screenBooking=document.getElementById('screen-booking'),screenFind=document.getElementById('screen-find');
    const progressBar=document.querySelector('.progress-bar');
    const businessNameEl=document.getElementById('business-name'),businessAddressEl=document.getElementById('business-address');
    const servicesList=document.getElementById('services-list');
    const clientName=document.getElementById('client-name'),clientPhone=document.getElementById('client-phone'),clientNotes=document.getElementById('client-notes');
    const continueBtn=document.getElementById('continue-btn'),userAvatar=document.getElementById('user-avatar');
    const searchQuery=document.getElementById('search-query'),searchBtn=document.getElementById('search-btn'),searchResult=document.getElementById('search-result'),findTitle=document.getElementById('find-title');
    
    let selectedService=null,services=[],currentAction='book',foundAppointment=null;
    const user=getUserData();
    if(user.first_name){clientName.value=user.last_name?user.first_name+' '+user.last_name:user.first_name;userAvatar.textContent=user.first_name.charAt(0).toUpperCase()}
    
    try{
        const[settingsRes,servicesRes]=await Promise.all([fetch(API_URL+'/api/settings'),fetch(API_URL+'/api/services')]);
        const settings=await settingsRes.json(),servicesData=await servicesRes.json();
        businessNameEl.textContent=settings.business_name||'Запись на услугу';
        if(settings.address)businessAddressEl.textContent='📍 '+settings.address;
        services=servicesData.services||[];
        renderServices();
    }catch(e){console.error(e)}
    
    function renderServices(){
        if(!services.length){servicesList.innerHTML='<div class="loading-state"><span>Нет услуг</span></div>';return}
        servicesList.innerHTML=services.map(s=>`<div class="service-card" data-id="${s.id}" data-name="${s.name}" data-duration="${s.duration}" data-price="${s.price}"><div class="service-card-header"><span class="service-name">${s.name}</span><span class="service-price">${s.price} BYN</span></div><div class="service-duration">⏰ ${s.duration} мин</div></div>`).join('');
        document.querySelectorAll('.service-card').forEach(c=>c.addEventListener('click',()=>{document.querySelectorAll('.service-card').forEach(x=>x.classList.remove('selected'));c.classList.add('selected');selectedService={id:c.dataset.id,name:c.dataset.name,duration:parseInt(c.dataset.duration),price:parseInt(c.dataset.price)};validate()}))
    }
    function validate(){continueBtn.disabled=!(clientName.value.trim()&&clientPhone.value.trim()&&selectedService)}
    clientName.addEventListener('input',validate);clientPhone.addEventListener('input',validate);
    clientPhone.addEventListener('input',e=>{let v=e.target.value.replace(/\D/g,'');if(v.length){if(v.startsWith('80'))v='+375 '+v.slice(2,4)+' '+v.slice(4,7)+'-'+v.slice(7,9)+'-'+v.slice(9,11);else if(v.startsWith('375'))v='+'+v.slice(0,3)+' '+v.slice(3,5)+' '+v.slice(5,8)+'-'+v.slice(8,10)+'-'+v.slice(10,12);e.target.value=v.slice(0,20)}});
    
    document.querySelectorAll('.action-card').forEach(c=>c.addEventListener('click',()=>{
        currentAction=c.dataset.action;
        if(currentAction==='book'){progressBar.style.display='flex';screenAction.classList.remove('active');screenBooking.classList.add('active')}
        else{findTitle.textContent=currentAction==='reschedule'?'Перенести запись':'Отменить запись';progressBar.style.display='none';screenAction.classList.remove('active');screenFind.classList.add('active')}
    }));
    
    document.getElementById('back-from-booking').addEventListener('click',()=>{screenBooking.classList.remove('active');screenAction.classList.add('active')});
    document.getElementById('back-from-find').addEventListener('click',()=>{screenFind.classList.remove('active');screenAction.classList.add('active');searchQuery.value='';searchResult.style.display='none';searchBtn.disabled=true});
    
    searchQuery.addEventListener('input',()=>searchBtn.disabled=!searchQuery.value.trim());
    searchBtn.addEventListener('click',async()=>{
        const q=searchQuery.value.trim();searchBtn.disabled=true;searchBtn.textContent='Поиск...';searchResult.style.display='none';
        try{
            const r=await fetch(API_URL+'/api/appointment/find?query='+encodeURIComponent(q));const d=await r.json();
            if(d.appointment){foundAppointment=d.appointment;displayAppointment(d.appointment)}
            else{searchResult.innerHTML='<div class="error-message">Запись не найдена</div>';searchResult.style.display='block'}
        }catch(e){searchResult.innerHTML='<div class="error-message">Ошибка</div>';searchResult.style.display='block'}
        finally{searchBtn.disabled=false;searchBtn.textContent='Найти'}
    });
    
    function displayAppointment(a){
        searchResult.innerHTML=`<div class="appointment-card"><div class="appointment-header"><span class="appointment-id">#${a.id}</span><span>${a.status}</span></div><div class="appointment-details"><div class="detail-row"><span>Услуга:</span><span>${a.service}</span></div><div class="detail-row"><span>Дата:</span><span>${a.date} в ${a.time}</span></div></div><div class="appointment-actions">${currentAction==='reschedule'?'<button class="primary-btn" id="reschedule-btn">Перенести</button>':'<button class="danger-btn" id="cancel-btn">Отменить</button>'}</div></div>`;
        searchResult.style.display='block';
        if(currentAction==='reschedule')document.getElementById('reschedule-btn').addEventListener('click',()=>{saveData('reschedule_appointment',foundAppointment);window.location.href='calendar.html?mode=reschedule'});
        else document.getElementById('cancel-btn').addEventListener('click',async()=>{if(confirm('Отменить запись?')){await fetch(API_URL+'/api/appointment/cancel',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({appointment_id:foundAppointment.id})});showToast('Запись отменена');setTimeout(closeApp,1500)}});
    }
    
    continueBtn.addEventListener('click',()=>{saveData('booking',{name:clientName.value.trim(),phone:clientPhone.value.trim().replace(/\D/g,''),service_id:selectedService.id,service_name:selectedService.name,duration:selectedService.duration,price:selectedService.price,notes:clientNotes.value.trim()});window.location.href='calendar.html'});
    tg.BackButton.hide();
});
