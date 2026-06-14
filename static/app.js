// Close flash messages when clicking the close button
document.querySelectorAll('.close-flash').forEach(btn => {
    btn.addEventListener('click', function() {
        this.parentElement.style.display = 'none';
    });
});

// Auto-hide flash messages after 5 seconds
document.querySelectorAll('.flash').forEach(flash => {
    setTimeout(() => {
        flash.style.display = 'none';
    }, 5000);
});

// Form submission confirmation for delete actions
document.querySelectorAll('form').forEach(form => {
    if (form.querySelector('button[onclick*="confirm"]')) {
        form.addEventListener('submit', function(e) {
            if (!confirm('Are you sure?')) {
                e.preventDefault();
            }
        });
    }
});

// Prevent accidental prediction changes for locked fixtures
const lockedCards = document.querySelectorAll('.fixture-card.locked');
lockedCards.forEach(card => {
    const form = card.querySelector('.prediction-form');
    if (form) {
        form.style.pointerEvents = 'none';
        form.style.opacity = '0.5';
    }
});
