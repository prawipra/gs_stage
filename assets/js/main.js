// add event listeners for various site/page features
document.addEventListener('DOMContentLoaded', () => {
  setupExpansionLabel();
  setupDisplayModeControls();
});


// configure expansion label to close vertical lang menu with mouse and kbd
function setupExpansionLabel() {
  const label = document.querySelector('.lang-nav-expansion-label');
  if (!label) return;

  // ensure label can get focus
  if (!label.hasAttribute('tabindex')) {
    label.setAttribute('tabindex', '0');
  }

  // initialize tracking flags
  label.dataset.open = 'false';
  label.setAttribute('aria-expanded', 'false');

  // track when label gains and loses focus
  label.addEventListener('focus', () => {
    label.dataset.open = 'true';
    label.setAttribute('aria-expanded', 'true');
  });

  label.addEventListener('blur', () => {
    label.dataset.open = 'false';
    label.setAttribute('aria-expanded', 'false');
  });

  // helper to toggle the focus on/off the label
  function toggleFocus() {
    if (label.dataset.open === 'true') {
      label.blur();
    } else {
      label.focus();
    }
  }

  // toggle on pointerdown (click/tap/pen)
  label.addEventListener('pointerdown', (event) => {
    event.preventDefault(); // stop automatic focus
    toggleFocus();
  });

  // accessibility: manage focus when certain keys are pressed
  // close on Esc; toggle on Enter and Space
  label.addEventListener('keydown', (event) => {
    const within = label.parentElement.matches(':focus-within');

    if (event.key === 'Escape' && within) {
      label.blur(); // no need to prevent default
    } else if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault(); // prevent scrolling or accidental form submit
      toggleFocus();
    }
  });
}


// handle light and dark display modes
function setupDisplayModeControls() {
  const status = document.getElementById('modeStatus');
  const switchBtn = document.getElementById('modeSwitch');
  const systemBtn = document.getElementById('modeSystem');
  if (!status || !switchBtn || !systemBtn) return;

  const key = 'geetaasameekshaa.in-display-mode';
  const mq = window.matchMedia('(prefers-color-scheme: dark)');

  const readPref = () => {
    try {
      const v = localStorage.getItem(key);
      if (v === '1') return true;
      if (v === '0') return false;
    } catch (e) {}
    return null; // null = follow system
  };

  const writePref = (val) => {
    try {
      if (val === null) localStorage.removeItem(key);
      else localStorage.setItem(key, val ? '1' : '0');
    } catch (e) {}
  };

  let pref = readPref();

  const apply = () => {
    const systemDark = mq.matches;
    const effectiveDark = pref !== null ? pref : systemDark;
    document.body.classList.toggle('dark-mode', effectiveDark);

    if (pref === null) {
      // following system
      status.textContent = `In ${systemDark ? 'Dark' : 'Light'} Mode (System)`;
      switchBtn.textContent = 'Force Dark';
      systemBtn.textContent = 'Force Light';

      switchBtn.onclick = () => {
        pref = true;
        writePref(pref);
        apply();
      };
      systemBtn.onclick = () => {
        pref = false;
        writePref(pref);
        apply();
      };
    } else {
      // explicit override
      status.textContent = `In ${pref ? 'Dark' : 'Light'} Mode`;
      switchBtn.textContent = `Switch to ${pref ? 'Light' : 'Dark'}`;
      systemBtn.textContent = `Follow System (${systemDark ? 'Dark' : 'Light'})`;

      switchBtn.onclick = () => {
        pref = !pref;
        writePref(pref);
        apply();
      };
      systemBtn.onclick = () => {
        pref = null;
        writePref(pref);
        apply();
      };
    }
  };

  apply();

  // update automatically if following system and OS theme changes
  if (pref === null) {
    const handler = () => apply();
    if (mq.addEventListener) mq.addEventListener('change', handler);
    else if (mq.addListener) mq.addListener(handler);
  }
}
