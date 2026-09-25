(function () {
  "use strict";

  // ---------- Theme ----------
  var root = document.documentElement;
  var themeToggle = document.getElementById("theme-toggle");
  var THEME_KEY = "mti360-theme";

  function applyTheme(theme) {
    if (theme === "dark" || theme === "light") {
      root.setAttribute("data-theme", theme);
    } else {
      root.removeAttribute("data-theme");
    }
    if (themeToggle) {
      var isDark = theme === "dark" || (theme !== "light" && window.matchMedia("(prefers-color-scheme: dark)").matches);
      themeToggle.setAttribute("aria-pressed", String(isDark));
      themeToggle.setAttribute("aria-label", isDark ? "Switch to light theme" : "Switch to dark theme");
    }
  }

  var stored = null;
  try { stored = localStorage.getItem(THEME_KEY); } catch (e) {}
  applyTheme(stored);

  if (themeToggle) {
    themeToggle.addEventListener("click", function () {
      var current = root.getAttribute("data-theme");
      var isDark = current === "dark" || (!current && window.matchMedia("(prefers-color-scheme: dark)").matches);
      var next = isDark ? "light" : "dark";
      applyTheme(next);
      try { localStorage.setItem(THEME_KEY, next); } catch (e) {}
    });
  }

  // ---------- Mobile navigation drawer ----------
  var menuToggle = document.getElementById("menu-toggle");
  var drawer = document.getElementById("mobile-drawer");

  function closeDrawer() {
    if (!drawer) return;
    drawer.classList.remove("open");
    drawer.setAttribute("aria-hidden", "true");
    if (menuToggle) menuToggle.setAttribute("aria-expanded", "false");
  }

  if (menuToggle && drawer) {
    menuToggle.addEventListener("click", function () {
      var isOpen = drawer.classList.toggle("open");
      drawer.setAttribute("aria-hidden", String(!isOpen));
      menuToggle.setAttribute("aria-expanded", String(isOpen));
    });

    drawer.querySelectorAll("a").forEach(function (link) {
      link.addEventListener("click", closeDrawer);
    });

    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") closeDrawer();
    });
  }

  // ---------- Scroll reveal ----------
  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var revealTargets = document.querySelectorAll(".reveal");

  if (reduceMotion || !("IntersectionObserver" in window)) {
    revealTargets.forEach(function (el) { el.classList.add("in-view"); });
  } else {
    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add("in-view");
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.15 }
    );
    revealTargets.forEach(function (el) { observer.observe(el); });
  }

  // ---------- AI demo "View Actions" ----------
  var viewActionsBtn = document.querySelector(".ai-answer .btn");
  if (viewActionsBtn) {
    viewActionsBtn.addEventListener("click", function () {
      viewActionsBtn.textContent = "Opening action queue…";
      window.setTimeout(function () {
        viewActionsBtn.textContent = "View Actions";
      }, 1600);
    });
  }
})();
