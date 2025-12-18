// Add event listeners for various site/page features
document.addEventListener('DOMContentLoaded', () => {
  setupExpansionLabel();
});

// configure the expansion label to access vertical language menu
function setupExpansionLabel() {
  const label = document.querySelector('.lang-nav-expansion-label');
  if (!label) return; // early exit if label not present

  label.addEventListener('click', () => {
    if (label.dataset.open === 'true') {
      label.blur();
      label.dataset.open = 'false';
    } else {
      label.focus();
      label.dataset.open = 'true';
    }
  });

  label.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && label.parentElement.matches(':focus-within')) {
      label.blur();
    }
  });
}
