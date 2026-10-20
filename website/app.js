// Folio website. Plain JavaScript, no libraries.
"use strict";

// When Folio is on GitHub, set live to true. That is the only change needed.
const CONFIG = { live: true, user: "MajorCoder1", repo: "folio" };

(function () {
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // ---- GitHub links ----------------------------------------------------------
  document.querySelectorAll("a.gh").forEach((a) => {
    const base = `https://github.com/${CONFIG.user}`;
    if (CONFIG.live) {
      a.href = `${base}/${CONFIG.repo}${a.dataset.path || ""}`;
    } else {
      a.href = base;
      if (a.dataset.soon) a.textContent = a.dataset.soon;
    }
  });

  // ---- reveal on scroll ---------------------------------------------------------
  const items = document.querySelectorAll(".reveal");
  if ("IntersectionObserver" in window) {
    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); }
      });
    }, { threshold: 0.12 });
    items.forEach((el, i) => {
      el.style.transitionDelay = `${(i % 4) * 60}ms`;
      io.observe(el);
    });
  } else {
    items.forEach((el) => el.classList.add("in"));
  }

  // ---- the book follows the mouse -----------------------------------------------
  const stage = document.getElementById("stage");
  const tilt = document.getElementById("tilt");
  if (stage && tilt && !reduce) {
    window.addEventListener("pointermove", (e) => {
      const r = stage.getBoundingClientRect();
      const x = (e.clientX - (r.left + r.width / 2)) / window.innerWidth;
      const y = (e.clientY - (r.top + r.height / 2)) / window.innerHeight;
      tilt.style.transform = `rotateY(${x * 40}deg) rotateX(${-y * 30}deg)`;
    });
  }

  // ---- cards tilt toward the pointer ---------------------------------------------
  if (!reduce) {
    document.querySelectorAll(".card").forEach((card) => {
      card.addEventListener("pointermove", (e) => {
        const r = card.getBoundingClientRect();
        const px = (e.clientX - r.left) / r.width;
        const py = (e.clientY - r.top) / r.height;
        card.style.setProperty("--ry", `${(px - 0.5) * 10}deg`);
        card.style.setProperty("--rx", `${(0.5 - py) * 10}deg`);
        card.style.setProperty("--mx", `${px * 100}%`);
        card.style.setProperty("--my", `${py * 100}%`);
      });
      card.addEventListener("pointerleave", () => {
        card.style.setProperty("--rx", "0deg");
        card.style.setProperty("--ry", "0deg");
      });
    });
  }

  // ---- screenshots: tabs and a tilting window ---------------------------------------
  const shot = document.getElementById("shot");
  const caption = document.getElementById("caption");
  const frame = document.getElementById("frame");
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((t) => t.setAttribute("aria-selected", "false"));
      tab.setAttribute("aria-selected", "true");
      shot.src = tab.dataset.img;
      shot.alt = tab.textContent + " screenshot of Folio";
      caption.textContent = tab.dataset.cap;
    });
  });
  if (frame && !reduce) {
    const win = frame.querySelector(".window");
    frame.addEventListener("pointermove", (e) => {
      const r = frame.getBoundingClientRect();
      const px = (e.clientX - r.left) / r.width - 0.5;
      const py = (e.clientY - r.top) / r.height - 0.5;
      win.style.setProperty("--ry", `${px * 14}deg`);
      win.style.setProperty("--rx", `${-py * 10}deg`);
    });
    frame.addEventListener("pointerleave", () => {
      win.style.setProperty("--ry", "-10deg");
      win.style.setProperty("--rx", "8deg");
    });
  }

  // ---- Q&A search ------------------------------------------------------------------------
  const search = document.getElementById("faqsearch");
  const none = document.getElementById("nofaq");
  if (search) {
    search.addEventListener("input", () => {
      const words = search.value.toLowerCase().split(/\s+/).filter(Boolean);
      let shown = 0;
      document.querySelectorAll(".faq details").forEach((d) => {
        const text = d.textContent.toLowerCase();
        const ok = words.every((w) => text.includes(w));
        d.style.display = ok ? "" : "none";
        if (ok) shown++;
      });
      none.style.display = shown ? "none" : "block";
    });
  }

  // ---- the join form opens the visitor's email program --------------------------------
  const form = document.getElementById("joinform");
  if (form) {
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const f = new FormData(form);
      const body = [
        `Name: ${f.get("name")}`,
        `Email: ${f.get("email")}`,
        `I'd like to help with: ${f.get("role")}`,
        "",
        `${f.get("about") || ""}`,
      ].join("\n");
      const subject = `Folio: I'd like to help (${f.get("role")})`;
      window.location.href = "mailto:aaron@m4j.net?subject=" + encodeURIComponent(subject) +
        "&body=" + encodeURIComponent(body);
    });
  }
})();
