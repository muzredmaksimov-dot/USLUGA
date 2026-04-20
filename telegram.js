const tg=window.Telegram.WebApp;tg.ready();tg.expand();
function applyTheme(){const p=tg.themeParams;if(p.bg_color)document.documentElement.style.setProperty('--bg-primary',p.bg_color);if(p.secondary_bg_color)document.documentElement.style.setProperty('--bg-secondary',p.secondary_bg_color);if(p.text_color)document.documentElement.style.setProperty('--text-primary',p.text_color);if(p.hint_color)document.documentElement.style.setProperty('--text-secondary',p.hint_color);if(p.button_color)document.documentElement.style.setProperty('--primary',p.button_color)}
applyTheme();tg.onEvent('themeChanged',applyTheme);
function getUserData(){const u=tg.initDataUnsafe?.user;return{id:u?.id||null,first_name:u?.first_name||'',last_name:u?.last_name||''}}
function showToast(m,d=2000){const t=document.getElementById('toast');if(t){t.textContent=m;t.classList.add('show');setTimeout(()=>t.classList.remove('show'),d)}}
function saveData(k,d){sessionStorage.setItem(k,JSON.stringify(d))}
function loadData(k){const d=sessionStorage.getItem(k);return d?JSON.parse(d):null}
function clearData(){sessionStorage.clear()}
const API_URL=window.location.origin;
function closeApp(){tg.close()}
function formatDisplayDate(s){if(!s)return'';const p=s.split('-');if(p.length!==3)return s;const m=['января','февраля','марта','апреля','мая','июня','июля','августа','сентября','октября','ноября','декабря'];return parseInt(p[2])+' '+m[parseInt(p[1])-1]}
function formatAPIDate(d){return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0')}
