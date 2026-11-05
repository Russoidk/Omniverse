function openSettings() {
    const overlay = document.getElementById('settings-overlay');
    showSettingsPanel('settings-main');
    overlay.classList.add('open');
}


function closeSettings() {
    const overlay = document.getElementById('settings-overlay');

    overlay.classList.remove('open');
}


document.addEventListener('click', function(event) {

    const overlay = document.getElementById('settings-overlay');

    if (event.target === overlay) {
        closeSettings();
    }

});


document.addEventListener('keydown', function(event) {

    if (event.key === 'Escape') {
        closeSettings();
    }

});

function showSettingsPanel(panelId) {

    const panels = document.querySelectorAll('.settings-panel');

    panels.forEach(function(panel) {

        panel.style.display = 'none';

    });


    const panel = document.getElementById(panelId);

    if (panel) {

        panel.style.display = 'block';

    }

}
// Ajusta la altura de los campos de texto al contenido.
function resizeTextarea(field) {
    if (!field || field.tagName !== 'TEXTAREA') return;
    field.style.height = 'auto';
    field.style.height = Math.max(field.scrollHeight, 74) + 'px';
}

document.querySelectorAll('textarea').forEach(function (field) {
    resizeTextarea(field);
    field.addEventListener('input', function () { resizeTextarea(field); });
});


// Muestra u oculta el menú lateral.
(function () {
    const app = document.querySelector('.app');
    const button = document.getElementById('sidebar-toggle');
    if (!app || !button) return;
    const STORAGE_KEY = 'omniverse-sidebar-collapsed';
    function applySidebarState(collapsed) {
        app.classList.toggle('sidebar-collapsed', collapsed);
        button.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
        button.setAttribute('aria-label', collapsed ? 'Mostrar barra lateral' : 'Ocultar barra lateral');
        button.title = collapsed ? 'Mostrar barra lateral' : 'Ocultar barra lateral';
        button.innerHTML = collapsed ? '☰ <span>Mostrar menú</span>' : '× <span>Ocultar menú</span>';
        try { localStorage.setItem(STORAGE_KEY, collapsed ? '1' : '0'); } catch (_) {}
    }
    let collapsed = false;
    try { collapsed = localStorage.getItem(STORAGE_KEY) === '1'; } catch (_) {}
    applySidebarState(collapsed);
    button.addEventListener('click', function () {
        applySidebarState(!app.classList.contains('sidebar-collapsed'));
    });
})();
