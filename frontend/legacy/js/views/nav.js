export function nav(){document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>window.dispatchEvent(new CustomEvent('navigate',{detail:b.dataset.view})));}
