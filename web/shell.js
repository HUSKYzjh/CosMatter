"use strict";

// Shared chrome for all static CosMatter bridge pages.  Themes are local UI
// preferences only; this script never reads files, keys, or network resources.
const COSMATTER_THEMES = new Set(["dark", "light", "eye"]);
const COSMATTER_THEME_KEY = "cosmatter-ui-theme";

function applyTheme(theme) {
  const selected = COSMATTER_THEMES.has(theme) ? theme : "dark";
  document.documentElement.dataset.theme = selected;
  document.querySelectorAll("[data-theme-select]").forEach((select) => { select.value = selected; });
  try { localStorage.setItem(COSMATTER_THEME_KEY, selected); } catch (_) { /* Preference persistence is optional. */ }
}

document.addEventListener("DOMContentLoaded", () => {
  let initial = "dark";
  try { initial = localStorage.getItem(COSMATTER_THEME_KEY) || initial; } catch (_) { /* Storage can be disabled. */ }
  applyTheme(initial);
  document.querySelectorAll("[data-theme-select]").forEach((select) => {
    select.addEventListener("change", () => applyTheme(select.value));
  });
});
