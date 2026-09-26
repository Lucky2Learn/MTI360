(function () {
  "use strict";

  var root = document.documentElement;
  var THEME_KEY = "mti360-theme";

  // ---------- Theme ----------
  var themeToggle = document.getElementById("theme-toggle");

  function applyTheme(theme) {
    var isDark = theme === "dark";
    root.setAttribute("data-theme", isDark ? "dark" : "light");
    if (themeToggle) {
      themeToggle.setAttribute("aria-pressed", String(isDark));
      var label = isDark ? "Switch to light mode" : "Switch to dark mode";
      themeToggle.setAttribute("aria-label", label);
      themeToggle.setAttribute("title", label);
    }
  }

  var storedTheme = null;
  try { storedTheme = localStorage.getItem(THEME_KEY); } catch (e) {}
  if (!storedTheme) {
    storedTheme = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  applyTheme(storedTheme);

  if (themeToggle) {
    themeToggle.addEventListener("click", function () {
      var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
      applyTheme(next);
      try { localStorage.setItem(THEME_KEY, next); } catch (e) {}
    });
  }

  // ---------- Mobile nav drawer ----------
  var menuToggle = document.getElementById("menu-toggle");
  var menuClose = document.getElementById("menu-close");
  var drawer = document.getElementById("mobile-drawer");

  function openDrawer() {
    if (!drawer) return;
    drawer.classList.add("open");
    drawer.setAttribute("aria-hidden", "false");
    if (menuToggle) menuToggle.setAttribute("aria-expanded", "true");
  }
  function closeDrawer() {
    if (!drawer) return;
    drawer.classList.remove("open");
    drawer.setAttribute("aria-hidden", "true");
    if (menuToggle) menuToggle.setAttribute("aria-expanded", "false");
  }

  if (menuToggle) menuToggle.addEventListener("click", openDrawer);
  if (menuClose) menuClose.addEventListener("click", closeDrawer);
  if (drawer) {
    drawer.querySelectorAll("a").forEach(function (link) {
      link.addEventListener("click", closeDrawer);
    });
  }
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") closeDrawer();
  });

  // ---------- Lifecycle stepper ----------
  var pad = function (i) { return String(i + 1).padStart(2, "0"); };
  var STAGES = [
    { k: "Acquire", p: "GROW", d: "Capture enquiries from your website, campaigns, education fairs, walk-ins and referrals — every source tracked to the lead.", m: ["Website", "Campaigns", "Lead capture", "Source tracking"], stat: "248", sl: "new leads this month" },
    { k: "Convert", p: "GROW", d: "Score, assign and follow up automatically so no enquiry goes cold. Counsellors see who to call next and why.", m: ["CRM", "Lead scoring", "Counselling", "WhatsApp"], stat: "< 2h", sl: "median first response" },
    { k: "Admit", p: "ADMIT", d: "Applications, eligibility, document collection and verification in one workflow — from interest to confirmed seat.", m: ["Applications", "Documents", "Verification", "Student 360"], stat: "42", sl: "admissions confirmed" },
    { k: "Train", p: "RUN", d: "Courses, batches, timetables, simulators, faculty, attendance and examinations — scheduled and tracked.", m: ["Courses", "Batches", "Timetable", "Attendance", "Exams"], stat: "18", sl: "active batches" },
    { k: "Collect", p: "RUN", d: "Fee plans, invoices, online payments, reminders and refunds linked to every admission.", m: ["Invoices", "Payments", "Reminders", "Refunds"], stat: "₹24.8L", sl: "collected this quarter" },
    { k: "Communicate", p: "AUTOMATE", d: "WhatsApp, email, SMS and voice from one inbox, with templates, automation and human handover.", m: ["WhatsApp", "Email", "SMS", "Voice"], stat: "3,410", sl: "messages this month" },
    { k: "Comply", p: "COMPLY", d: "Approvals, certificates, faculty competencies, inspection evidence and corrective actions — tracked with expiry alerts.", m: ["Compliance", "Inspections", "Corrective actions", "Audit trail"], stat: "87%", sl: "inspection readiness" },
    { k: "Place", p: "GROW", d: "Readiness, opportunities, interviews and selections tracked from classroom to first contract.", m: ["Readiness", "Opportunities", "Interviews", "Placement"], stat: "82%", sl: "placement rate" },
    { k: "Grow", p: "GROW", d: "Close the loop: see which sources, courses and campuses perform — and reinvest where it works.", m: ["Analytics", "Course performance", "Revenue", "AI insights"], stat: "6", sl: "decisions surfaced this week" }
  ];

  var lcWide = document.getElementById("lc-wide");
  var lcNarrow = document.getElementById("lc-narrow");
  var lcPanel = document.getElementById("lc-panel");
  var lcProgress = document.getElementById("lc-progress");

  if (lcWide && lcNarrow && lcPanel) {
    var stage = 0;
    var autoplay = true;
    var timer = null;
    var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    function buildWideButtons() {
      STAGES.forEach(function (s, i) {
        var btn = document.createElement("button");
        btn.type = "button";
        btn.setAttribute("role", "tab");
        btn.dataset.stage = i;
        btn.style.cssText = "position:relative;background:none;border:0;padding:0 2px;cursor:pointer;display:flex;flex-direction:column;align-items:center;gap:12px";
        btn.innerHTML =
          '<span class="lc-dot" style="width:44px;height:44px;border-radius:50%;display:grid;place-items:center;font-family:\'JetBrains Mono\',monospace;font-size:12px;font-weight:600;transition:.3s">' + pad(i) + '</span>' +
          '<span class="lc-label" style="font-size:clamp(11px,1.1vw,13px);letter-spacing:.12em;text-transform:uppercase">' + s.k + '</span>';
        btn.addEventListener("click", function () { setStage(i, false); });
        lcWide.appendChild(btn);
      });
    }
    function buildNarrowButtons() {
      STAGES.forEach(function (s, i) {
        var btn = document.createElement("button");
        btn.type = "button";
        btn.setAttribute("role", "tab");
        btn.dataset.stage = i;
        btn.style.cssText = "min-height:52px;border-radius:10px;border:1px solid var(--ln);font-size:11.5px;font-weight:700;letter-spacing:.08em;cursor:pointer;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px";
        btn.innerHTML = '<span style="font-family:\'JetBrains Mono\',monospace;font-size:10px;opacity:.75">' + pad(i) + '</span>' + s.k;
        btn.addEventListener("click", function () { setStage(i, false); });
        lcNarrow.appendChild(btn);
      });
    }
    buildWideButtons();
    buildNarrowButtons();

    function renderPanel(i) {
      var s = STAGES[i];
      var modules = s.m.map(function (m) {
        return '<span style="padding:7px 12px;border-radius:8px;background:var(--seaS);color:var(--seaT);font-size:13.5px;font-weight:600">' + m + '</span>';
      }).join("");
      lcPanel.innerHTML =
        '<div style="background:var(--sf);padding:clamp(20px,3vw,32px)">' +
          '<div style="font-family:\'JetBrains Mono\',monospace;font-size:11.5px;color:var(--ink3);letter-spacing:.1em">WAYPOINT ' + pad(i) + ' / 09 · PILLAR: <span style="color:var(--seaT);font-weight:600">' + s.p + '</span></div>' +
          '<div style="font-size:clamp(26px,3vw,36px);font-weight:800;letter-spacing:-0.02em;margin-top:10px">' + s.k + '</div>' +
          '<p style="margin:10px 0 0;font-size:16px;line-height:1.6;color:var(--ink2)">' + s.d + '</p>' +
        '</div>' +
        '<div style="background:var(--sf);padding:clamp(20px,3vw,32px)">' +
          '<div style="font-size:12px;font-weight:700;color:var(--ink3);text-transform:uppercase;letter-spacing:.1em">Modules at work</div>' +
          '<div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:14px">' + modules + '</div>' +
        '</div>' +
        '<div style="background:var(--sf);padding:clamp(20px,3vw,32px)">' +
          '<div style="font-size:12px;font-weight:700;color:var(--ink3);text-transform:uppercase;letter-spacing:.1em">In the dashboard</div>' +
          '<div style="font-size:40px;font-weight:800;letter-spacing:-0.03em;margin-top:8px;font-variant-numeric:tabular-nums">' + s.stat + '</div>' +
          '<div style="font-size:14.5px;color:var(--ink2)">' + s.sl + '</div>' +
          '<div style="font-size:11px;color:var(--ink3);margin-top:12px">Illustrative demo data</div>' +
        '</div>';
    }

    function setStage(i, isAuto) {
      stage = i;
      if (!isAuto) autoplay = false;
      [lcWide, lcNarrow].forEach(function (container) {
        container.querySelectorAll("[role=tab]").forEach(function (btn) {
          var idx = Number(btn.dataset.stage);
          var on = idx === stage;
          var past = idx < stage;
          btn.setAttribute("aria-selected", String(on));
          if (container === lcWide) {
            var dot = btn.querySelector(".lc-dot");
            var label = btn.querySelector(".lc-label");
            btn.style.color = on ? "var(--ink)" : "var(--ink3)";
            dot.style.background = on ? "var(--seaT)" : "var(--sf)";
            dot.style.border = "2px solid " + (on || past ? "var(--seaT)" : "var(--ln)");
            dot.style.color = on ? "var(--onSea)" : (past ? "var(--seaT)" : "var(--ink3)");
            dot.style.boxShadow = on ? "0 0 0 6px var(--seaS)" : "none";
            label.style.fontWeight = on ? "800" : "600";
          } else {
            btn.style.background = on ? "var(--seaT)" : "var(--sf)";
            btn.style.color = on ? "var(--onSea)" : "var(--ink)";
            btn.style.borderColor = on || past ? "var(--seaT)" : "var(--ln)";
          }
        });
      });
      if (lcProgress) lcProgress.style.width = (stage / 8 * 89) + "%";
      renderPanel(stage);
    }

    setStage(0, true);

    if (!reduceMotion) {
      timer = setInterval(function () {
        if (autoplay) setStage((stage + 1) % 9, true);
      }, 3200);
    }
  }

  // ---------- Demo form ----------
  var demoForm = document.querySelector('form[aria-label="Book a demo"]');
  var demoFields = document.getElementById("demo-form-fields");
  var demoSent = document.getElementById("demo-form-sent");
  if (demoForm && demoFields && demoSent) {
    demoForm.addEventListener("submit", function (e) {
      e.preventDefault();
      demoFields.style.display = "none";
      demoSent.style.display = "block";
    });
  }

  // ---------- Scroll reveal ----------
  var reduceMotionReveal = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var revealTargets = document.querySelectorAll("[data-reveal]");
  if (reduceMotionReveal || !("IntersectionObserver" in window)) {
    revealTargets.forEach(function (el) { el.classList.add("in-view"); });
  } else {
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add("in-view");
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.1 });
    revealTargets.forEach(function (el) { observer.observe(el); });
  }

  // ---------- Back to top ----------
  var backToTop = document.getElementById("back-to-top");
  if (backToTop) {
    var toggleBackToTop = function () {
      backToTop.classList.toggle("visible", window.scrollY > 600);
    };
    window.addEventListener("scroll", toggleBackToTop, { passive: true });
    toggleBackToTop();
    backToTop.addEventListener("click", function () {
      window.scrollTo({ top: 0, behavior: reduceMotionReveal ? "auto" : "smooth" });
    });
  }
})();
