// add event listeners for various site/page features
document.addEventListener('DOMContentLoaded', () => {
  setupExpansionLabel();
  setupColorSchemeControls();
});


// configure expansion label to close vertical lang menu with mouse and kbd
function setupExpansionLabel() {
  const label = document.querySelector('.lang-nav-expansion-label');
  if (!label) return;

  // ensure label can get focus
  if (!label.hasAttribute('tabindex')) label.setAttribute('tabindex', '0');

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
    if (label.dataset.open === 'true') label.blur();
    else label.focus();
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


// update <meta name="theme-color"> to match effective theme
function updateMetaThemeColorFromCSS() {
  try {
    const meta = document.getElementById('meta-theme-color');
    if (!meta) return;
    
    // get --bg property for the doc; fallback to white if --bg is not set or empty
    const cs = getComputedStyle(document.documentElement);
    let bg = cs.getPropertyValue('--bg').trim();
    if (!bg) bg = '#ffffff';

    meta.setAttribute('content', bg);
  } catch (e) {}
}


// manage color scheme: Dark, Light, System
function setupColorSchemeControls() {
  const cfg = window.__GEETAA_SAMEEKSHAA_COLOR_SCHEME; //injected already
  if (!cfg) return;

  const status = document.getElementById('colorSchemeStatus');
  const fixDarkModeOrToggleUserModeBtn = document.getElementById('fixDarkModeOrToggleUserMode');
  const fixLightModeOrFollowSystemBtn = document.getElementById('fixLightModeOrFollowSystem');
  if (!status || !fixDarkModeOrToggleUserModeBtn || !fixLightModeOrFollowSystemBtn) return;

  // read stored preference: 'Dark' | 'Light' (default = 'System')
  function readColorScheme() {
    try {
      const val = localStorage.getItem(cfg.STORAGE_KEY);
      if (val === cfg.NAME_DARK || val === cfg.NAME_LIGHT) return val;
    } catch (e) {}
    return cfg.NAME_SYSTEM;
  }

  // store preference if dark or light; otherwise remove any stored pref
  // return true only if storage op does not throw
  function storeColorScheme(val) {
    try {
      if (val === cfg.NAME_DARK || val === cfg.NAME_LIGHT) localStorage.setItem(cfg.STORAGE_KEY, val);
      else localStorage.removeItem(cfg.STORAGE_KEY);
      return true;
    } catch (e) {}
     return false;
  }

  // in-memory color-scheme preference: 'Dark' | 'Light' | 'System'
  let currentScheme = readColorScheme();

  // listener for system color-scheme pref
  const mq = window.matchMedia && window.matchMedia(cfg.MQ_QUERY);
  
  // reflect currentScheme in DOM
  const VALID_SCHEMES = new Set([cfg.NAME_DARK, cfg.NAME_LIGHT, cfg.NAME_SYSTEM]);
  function applyToDOM() {
    if (!VALID_SCHEMES.has(currentScheme)) return; //early return if bad scheme (check because value comes from localstorage)

    const systemScheme = (mq?.matches ?? false) ? cfg.NAME_DARK : cfg.NAME_LIGHT; // light is default
    const effectiveScheme = currentScheme === cfg.NAME_SYSTEM ? systemScheme : currentScheme;
    const effectiveDark = effectiveScheme === cfg.NAME_DARK;

    document.documentElement.classList.toggle(cfg.DARK_MODE_CLASS, effectiveDark);
    updateMetaThemeColorFromCSS();

    if (currentScheme === cfg.NAME_SYSTEM) { // following system, show: Fix Dark | Fix Light
      status.textContent = `In ${systemScheme} Mode (${cfg.NAME_SYSTEM})`;
      fixDarkModeOrToggleUserModeBtn.textContent = `Fix ${cfg.NAME_DARK}`;
      fixLightModeOrFollowSystemBtn.textContent = `Fix ${cfg.NAME_LIGHT}`;
    } else { // not following system, show: Switch to [Dark/Light, opposite of current] | Follow System
      status.textContent = `In ${currentScheme} Mode`;
      fixDarkModeOrToggleUserModeBtn.textContent = `Switch to ${currentScheme === cfg.NAME_DARK ? cfg.NAME_LIGHT : cfg.NAME_DARK}`;
      fixLightModeOrFollowSystemBtn.textContent = `Follow ${cfg.NAME_SYSTEM} (${systemScheme})`;
    }
  }

  // use the apply function as mq listener: add once and keep it for the page lifetime
  // the typeof alternative paths exist to use whichever browser capability is available
  if (mq)
    try {
      if (typeof mq.addEventListener === 'function') mq.addEventListener('change', applyToDOM);
      else if (typeof mq.addListener === 'function') mq.addListener(applyToDOM);
    } catch (e) {}


  // sync cross-window storage change
  const onStorage = (e) => {
    try {
      if (e?.key !== cfg.STORAGE_KEY) return; // some other key changed

      const raw = e.newValue; // string or null (null if key removed)
      const newScheme = (raw === null) ? cfg.NAME_SYSTEM : raw;
      if (newScheme === currentScheme) return; // no actual change

      currentScheme = newScheme;
      applyToDOM();
    } catch (e) { /* ignore */ }
  };
  window.addEventListener('storage', onStorage);
    
  
  // fixDarkModeOrToggleUserModeBtn: if following system, make the dark mode permanent
  // if not following system, toggle current mode: dark to light; light to dark
  fixDarkModeOrToggleUserModeBtn.onclick = () => {
    const storedScheme = readColorScheme();

    let newScheme;
    if (storedScheme === cfg.NAME_SYSTEM) newScheme = cfg.NAME_DARK;                   // following system: fix dark mode as user mode
    else newScheme = storedScheme === cfg.NAME_DARK ? cfg.NAME_LIGHT : cfg.NAME_DARK;  // not following system: toggle user mode

    // store new pref; remove system-pref listener; reflect in DOM if successfully stored
    if (storeColorScheme(newScheme)) {
      currentScheme = newScheme;
      applyToDOM();
    }
  };

  // fixLightModeOrFollowSystemBtn: if following system, make the light mode permanent
  // if not following system, subscribe to system pref
  fixLightModeOrFollowSystemBtn.onclick = () => {
    const storedScheme = readColorScheme();

    let newScheme;
    if (storedScheme === cfg.NAME_SYSTEM) newScheme = cfg.NAME_LIGHT; // following system: fix light mode as user mode
    else newScheme = cfg.NAME_SYSTEM;                                 // not following system: follow system
    
    if (storeColorScheme(newScheme)) {
      currentScheme = newScheme;
      applyToDOM();
    }
  };

  // initial DOM state
  applyToDOM();
}
