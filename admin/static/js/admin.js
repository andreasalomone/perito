window.addEventListener('DOMContentLoaded', event => {
    // Toggle the side navigation
    const menuToggle = document.body.querySelector('#menu-toggle');
    if (menuToggle) {
        menuToggle.addEventListener('click', event => {
            event.preventDefault();
            document.body.querySelector('#wrapper').classList.toggle('toggled');
        });
    }
});
