/* Codebyr OS — interactions du site (léger, sans dépendance) */
(function () {
  "use strict";

  var root = document.documentElement;

  /* ── Thème : mémoire locale, sinon préférence système ────────── */
  var stored = null;
  try { stored = localStorage.getItem("cb-theme"); } catch (e) {}
  if (stored === "light" || stored === "dark") {
    root.setAttribute("data-theme", stored);
  } else if (window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches) {
    root.setAttribute("data-theme", "light");
  }

  var toggle = document.getElementById("themeToggle");
  if (toggle) {
    toggle.addEventListener("click", function () {
      var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      try { localStorage.setItem("cb-theme", next); } catch (e) {}
      var meta = document.querySelector('meta[name="theme-color"]');
      if (meta) meta.setAttribute("content", next === "dark" ? "#0B1419" : "#F4F7F8");
    });
  }

  /* ── Ombre de la barre de navigation au défilement ───────────── */
  var nav = document.querySelector(".nav");
  function onScroll() {
    if (!nav) return;
    nav.classList.toggle("is-scrolled", window.scrollY > 8);
  }
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  /* ── Révélations progressives au défilement ──────────────────── */
  var reveals = document.querySelectorAll(".reveal");
  if ("IntersectionObserver" in window && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry, i) {
        if (entry.isIntersecting) {
          var el = entry.target;
          // léger décalage en cascade pour les éléments d'un même groupe
          var delay = Math.min(i * 60, 180);
          el.style.transitionDelay = delay + "ms";
          el.classList.add("is-in");
          io.unobserve(el);
        }
      });
    }, { threshold: 0.12, rootMargin: "0px 0px -8% 0px" });
    reveals.forEach(function (el) { io.observe(el); });
  } else {
    reveals.forEach(function (el) { el.classList.add("is-in"); });
  }

  /* ── Année du pied de page ───────────────────────────────────── */
  var y = document.getElementById("year");
  if (y) y.textContent = String(new Date().getFullYear());
})();
