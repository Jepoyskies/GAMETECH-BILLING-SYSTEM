/* Gametech portal theme toggle.
   Reuses the ADMIN mechanism verbatim (localStorage key "theme" +
   html.dark-mode class + data-bs-theme), so a user who picks dark mode in
   the main system gets dark mode in the Agent and Technician portals too.
   The customer portal uses a different key (gt-portal-theme); that is left
   alone deliberately. */
(function () {
  "use strict";

  var KEY = "theme";

  function current() {
    return localStorage.getItem(KEY) === "dark" ? "dark" : "light";
  }

  function apply(mode) {
    var html = document.documentElement;
    html.classList.toggle("dark-mode", mode === "dark");
    document.body.classList.toggle("dark-mode", mode === "dark");
    /* Keep Bootstrap's own components (modal, dropdown, form-select, table)
       in sync, otherwise they stay light inside a dark page. */
    html.setAttribute("data-bs-theme", mode);
  }

  function syncLabels(mode) {
    document.querySelectorAll("[data-pt-theme-label]").forEach(function (el) {
      el.textContent = mode === "dark" ? "LIGHT" : "DARK";
    });
  }

  window.gtPortalTheme = {
    get: current,
    set: function (mode) {
      localStorage.setItem(KEY, mode);
      apply(mode);
      syncLabels(mode);
    },
    toggle: function () {
      window.gtPortalTheme.set(current() === "dark" ? "light" : "dark");
    },
    init: function () {
      apply(current());
      syncLabels(current());
      document.addEventListener("click", function (e) {
        var btn = e.target.closest("[data-pt-theme-toggle]");
        if (btn) {
          e.preventDefault();
          window.gtPortalTheme.toggle();
        }
      });
    },
  };
})();
