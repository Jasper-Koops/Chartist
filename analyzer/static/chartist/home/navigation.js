export function registerHomeNavigation(state, map, overview) {
  const { reducedMotion } = state;
  // A link to a chapter (/#parties): the browser jumps there before the
  // chapters above it have their content, which then pushes the target
  // down. Once everything is in, go to it again.
  Promise.allSettled([map.landscapeLoaded, overview.chaptersLoaded]).then(() => {
    const target = location.hash && document.getElementById(decodeURIComponent(location.hash.slice(1)));
    if (target) requestAnimationFrame(() => target.scrollIntoView({ behavior: "instant" }));
  });

  // "Explore the map": the change to the readable map, played at once.
  document.getElementById("map-start").addEventListener("click", () => map.setFlat(true));

  // A jump to a chapter below the map (the menu, a link): the map first
  // takes its readable form at once, out of sight, so the page has its
  // final length and the jump lands where it should.
  document.addEventListener("click", (event) => {
    const link = event.target.closest("a[href*='#']");
    if (!link || map.isFormed() || link.pathname !== location.pathname) return;
    const target = document.getElementById(decodeURIComponent(link.hash.slice(1)));
    if (!target || target.closest("#hero")) return;
    event.preventDefault();
    map.setFlat(true, { animate: false });
    history.pushState(null, "", link.hash);
    requestAnimationFrame(() => target.scrollIntoView({ behavior: reducedMotion ? "instant" : "smooth" }));
  });


  // ---------- The chapter bar: shown once the chapters are reached ----------
  // From when the content below the map reaches the middle of the window;
  // hidden again back at the map.
  (() => {
    const bar = document.getElementById("chapter-bar");
    const below = document.querySelector(".band");
    let queued = false;
    const update = () => {
      queued = false;
      bar.classList.toggle("shown", below.getBoundingClientRect().top < window.innerHeight / 2);
    };
    window.addEventListener("scroll", () => {
      if (queued) return;
      queued = true;
      requestAnimationFrame(update);
    }, { passive: true });
    update();
  })();

  // ---------- The menu slides in once the visitor scrolls (or the map has
  // formed, see morphed), and stays ----------
  (() => {
    const update = () => {
      if (window.scrollY <= 24) return;
      document.body.classList.add("scrolled");
      window.removeEventListener("scroll", update);
    };
    window.addEventListener("scroll", update, { passive: true });
    update();
  })();

  // ---------- Chapters fade in as they scroll into view ----------
  (() => {
    const sections = [...document.querySelectorAll(".band .stats, main .chapter")];
    document.body.classList.add("reveal-ready");
    const observer = new IntersectionObserver((entries) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        entry.target.classList.add("is-visible");
        observer.unobserve(entry.target);
      }
    // As soon as a section's top is a little way into the window, also for
    // tall sections like the matrix.
    }, { threshold: 0, rootMargin: "0px 0px -8% 0px" });
    sections.forEach((section) => {
      section.classList.add("reveal");
      observer.observe(section);
    });
  })();
}
