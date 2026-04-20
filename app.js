// В app.js, функция поиска
searchBtn.addEventListener('click', async () => {
    const query = searchQuery.value.trim();
    if (!query) return;
    
    searchBtn.disabled = true;
    searchBtn.textContent = 'Поиск...';
    searchResult.style.display = 'none';
    
    try {
        // Исправленный URL
        const url = `${API_URL}/api/appointment/find?query=${encodeURIComponent(query)}`;
        console.log('Search URL:', url);
        
        const response = await fetch(url);
        const data = await response.json();
        console.log('Search result:', data);
        
        if (data.appointment) {
            foundAppointment = data.appointment;
            displayAppointment(data.appointment);
        } else {
            searchResult.innerHTML = '<div class="error-message">Запись не найдена</div>';
            searchResult.style.display = 'block';
        }
    } catch (error) {
        console.error('Search error:', error);
        searchResult.innerHTML = '<div class="error-message">Ошибка поиска</div>';
        searchResult.style.display = 'block';
    } finally {
        searchBtn.disabled = false;
        searchBtn.textContent = 'Найти';
    }
});
