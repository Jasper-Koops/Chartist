import { toPoints, mainAxisColor, displayedVariance } from "./data.js";
import { projector, sceneGeometry } from "./plotly-scene.js";
import { registerMapExport } from "./export.js";

export function createMap(state, renderAxes) {
  const { requests, onFocus, setFocus, reducedMotion } = state;
  // ---------- The map ----------
  const varianceLabel = (variance, number) =>
    Number.isFinite(variance[number]) ? `PC${number} · ${pct(variance[number], 1)}` : `PC${number}`;

  // A padded range that includes zero: the flat map lies on the zero plane.
  function paddedRange(values) {
    const lo = Math.min(0, ...values);
    const hi = Math.max(0, ...values);
    const pad = (hi - lo || 1) * 0.08;
    return [lo - pad, hi + pad];
  }

  // Camera positions as distance, compass direction and height angle, so
  // a move between two views turns smoothly instead of cutting through.
  const toSpherical = ({ x, y, z }) => {
    const r = Math.hypot(x, y, z);
    return { r, az: Math.atan2(y, x), el: Math.asin(z / r) };
  };
  const fromSpherical = ({ r, az, el }) =>
    ({ x: r * Math.cos(el) * Math.cos(az), y: r * Math.cos(el) * Math.sin(az), z: r * Math.sin(el) });

  // Far enough out that the whole cloud fits the window; further on
  // narrow screens. The flat view looks straight down, PC1 across and PC2
  // up, like a printed map.
  const START_EYE = (target) =>
    target.clientWidth < 600 ? { x: 1.2, y: 1.2, z: 0.7 } : { x: 1.02, y: 1.02, z: 0.56 };
  const FLAT_DISTANCE = (target) => (target.clientWidth < 600 ? 1.8 : 1.3);

  // Scrolling over the map scrolls the page; only fullscreen zooms. That
  // is done by `letPageScroll` below, not by turning Plotly's scrollZoom
  // off: with it off, Plotly's 3D scene leaves out the axis titles (and
  // with them the explained variance).
  // Drawn at the screen's own resolution (sharp on high-density screens,
  // up to 2x): Plotly would draw at 2x everywhere, which for a map this
  // size costs a lot of graphics memory on an ordinary screen.
  const heroConfig = () => ({
    responsive: true,
    displaylogo: false,
    displayModeBar: false,
    scrollZoom: true,
    plotGlPixelRatio: Math.min(Math.max(window.devicePixelRatio || 1, 1), 2),
  });
  // Plotly's 3D scene takes the wheel even without scroll zoom, so stop
  // the event on its way down to the scene: the page scrolls as usual.
  function letPageScroll(target, unless = () => false) {
    target.addEventListener("wheel", (event) => { if (!unless()) event.stopPropagation(); }, { capture: true });
  }
  letPageScroll(document.getElementById("plot-3d"), () => frame.classList.contains("is-fullscreen"));

  // Returns false when there is nothing to show in 3D.
  function renderPca3d(points, variance) {
    const target = document.getElementById("plot-3d");
    const usable = points.filter((p) => Number.isFinite(p.z));
    if (!usable.length) return false;
    if (!window.Plotly) {
      target.replaceChildren(el("div", { className: "placeholder" }, t("Could not load the 3D chart library.")));
      return true;
    }
    // A highlighted party keeps its color; the others fade.
    const colors = () =>
      usable.map((p) => (!state.focusedParty || p.partyId === state.focusedParty ? mainAxisColor(p.x, points) : css("--dim")));
    // Name the ends of the color scale after the parties there.
    const byX = [...usable].sort((a, b) => a.x - b.x);
    document.querySelectorAll(".legend-lo").forEach((node) => { node.textContent = byX[0].label; });
    document.querySelectorAll(".legend-hi").forEach((node) => { node.textContent = byX.at(-1).label; });
    document.querySelectorAll(".hero-legend").forEach((node) => { node.hidden = false; });
    // Fixed ranges and sides in proportion to them: one scale in every
    // direction. Flattening shrinks the box's depth, not the data.
    const ranges = [usable.map((p) => p.x), usable.map((p) => p.y), usable.map((p) => p.z)].map(paddedRange);
    const spans = ranges.map(([lo, hi]) => hi - lo);
    const longest = Math.max(...spans);
    landscape.depth = spans[2] / longest;
    Object.assign(landscape, { usable, ranges, variance });
    markerStyle(target, 0);
    // The axes are there from the start, but see-through (calm opening);
    // `showDetails` colours them in. Plotly's 3D scene only draws axis
    // titles it had when it was built, so axes are never switched off or
    // their titles blanked: hiding is done with colour (see axesStyle).
    const sceneAxis = (number) => ({
      range: ranges[number - 1],
      autorange: false,
      title: { text: varianceLabel(variance, number), font: { color: CLEAR, size: 12 } },
      gridcolor: CLEAR,
      zerolinecolor: CLEAR,
      tickfont: { color: CLEAR, size: 10 },
      backgroundcolor: CLEAR,
    });
    Plotly.newPlot(
      target,
      [{
        type: "scatter3d",
        mode: "markers+text",
        x: usable.map((p) => p.x),
        y: usable.map((p) => p.y),
        z: usable.map((p) => p.z),
        text: usable.map((p) => p.label),
        // The party, and its PC3 score for the tooltip (also once flat).
        customdata: usable.map((p) => [p.partyId, p.z]),
        textposition: "middle right",
        textfont: { family: css("--font-sans"), size: landscape.textSize, color: css("--ink") },
        marker: { size: landscape.markerSize, color: colors(), line: { width: 0 } },
        hovertemplate: "<b>%{text}</b><br>PC1 %{x:.2f} · PC2 %{y:.2f} · PC3 %{customdata[1]:.2f}<extra></extra>",
      }],
      {
        margin: { l: 0, r: 0, t: 0, b: 0 },
        paper_bgcolor: "rgba(0, 0, 0, 0)",  // the paper shows through
        scene: {
          aspectmode: "manual",
          aspectratio: { x: spans[0] / longest, y: spans[1] / longest, z: landscape.depth },
          camera: { eye: START_EYE(target), up: { x: 0, y: 0, z: 1 } },
          // On wide screens the scene takes the area right of the title,
          // so the text never covers a party.
          domain: sceneDomain(target, morph.p),
          xaxis: sceneAxis(1),
          yaxis: sceneAxis(2),
          zaxis: sceneAxis(3),
        },
      },
      heroConfig()
    );
    target.on("plotly_click", (event) => {
      const partyId = event.points?.[0]?.customdata?.[0];
      if (partyId) window.location.href = `/party/${partyId}/`;
    });
    onFocus(() => Plotly.restyle(target, { "marker.color": [colors()] }));
    buildLogos(usable);
    calmUntilGrabbed(target);
    autoRotate(target);
    return true;
  }

  // The opening shows only the parties. Moving the mouse over the map
  // shows the controls for a while; grabbing the map (or highlighting a
  // party, or flattening it) shows the axes and everything else for good.
  function calmUntilGrabbed(target) {
    const hero = document.getElementById("hero");
    landscape.showDetails = () => {
      if (!hero.classList.contains("is-calm")) return;
      hero.classList.remove("is-calm");
      Plotly.relayout(target, axesStyle(landscape.flat));
    };
    for (const type of ["pointerdown", "touchstart", "keydown"]) {
      target.addEventListener(type, landscape.showDetails, { once: true, passive: true });
    }
    onFocus((partyId) => { if (partyId) landscape.showDetails(); });

    let idle;
    hero.addEventListener("pointermove", () => {
      hero.classList.add("pointer-active");
      clearTimeout(idle);
      idle = setTimeout(() => hero.classList.remove("pointer-active"), 2500);
    });
  }

  // The opening map takes most of the screen: on wide screens everything
  // right of 30%, so the cloud sits beside the title and reaches under
  // it where the title leaves room. Once flat (p = 1) it starts where the
  // caption ends; the controls are in the left column. On narrow screens
  // below the text, above the controls docked at the bottom.
  function sceneDomain(target, p = 0) {
    const width = target.clientWidth;
    const mix = (a, b) => a + (b - a) * p;
    if (width < 1000) return { x: [0, 1], y: [0.12, mix(0.82, 0.78)] };
    const caption = document.getElementById("map-caption");
    const captionEnd = Math.min((caption.offsetLeft + caption.offsetWidth + 32) / width, 0.4);
    return { x: [mix(0.3, captionEnd), 1], y: [0.04, mix(1, 0.94)] };
  }

  // Turn the camera slowly around the vertical axis, until the visitor
  // touches the graph or changes the view; then it stays where they leave
  // it. Paused while the graph is out of view or the tab is hidden; off
  // for reduced motion.
  function autoRotate(target) {
    if (reducedMotion) return;
    const eye = START_EYE(target);
    const radius = Math.hypot(eye.x, eye.y);
    let angle = Math.atan2(eye.y, eye.x);
    const SPEED = (2 * Math.PI) / 60000;  // one turn per minute
    let running = true;
    let visible = true;
    let last = null;

    landscape.stopRotating = () => { running = false; };
    for (const type of ["pointerdown", "touchstart", "keydown"]) {
      target.addEventListener(type, landscape.stopRotating, { once: true, passive: true });
    }
    new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; }).observe(target);

    function frame(now) {
      if (!running) return;
      // At most 30 steps a second: smooth enough for a slow turn, and it
      // leaves the browser time for scrolling.
      if (last === null) last = now;
      if (now - last >= 33 && visible && !document.hidden && !landscape.fullscreenBusy) {
        angle += SPEED * Math.min(now - last, 100);
        Plotly.relayout(target, {
          "scene.camera.eye": { x: radius * Math.cos(angle), y: radius * Math.sin(angle), z: eye.z },
        });
        last = now;
      }
      requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  }

  const touchScreen = matchMedia("(pointer: coarse)").matches;
  const heroHint = (flat) => touchScreen
    ? t("Open fullscreen to explore the map.")
    : flat ? t("Click a party to open it.") : t("Drag to turn the map, click a party to open it.");
  const showHint = (flat) => {
    document.getElementById("hero-hint").textContent = heroHint(flat);
    document.getElementById("map-hint").textContent = heroHint(flat);
  };
  showHint(false);

  // Flat or in depth: the same map. Flattening presses the box flat, so
  // every party and the grid end up in one plane, while the camera rises
  // to look straight down; going back lifts them out again. A plan gives
  // the scene at any point k from 0 (now) to 1 (there), so a timer or the
  // scroll position can drive it.
  function planMorph(flat) {
    const target = document.getElementById("plot-3d");
    const camera = target.layout.scene.camera || {};
    const from = toSpherical(camera.eye || START_EYE(target));
    // Approach the top from below the map (compass -90°), so PC1 ends up
    // across and PC2 up without the picture spinning at the end.
    const to = flat
      ? { r: FLAT_DISTANCE(target), az: -Math.PI / 2, el: Math.PI / 2 - 1e-4 }
      : toSpherical(START_EYE(target));
    // The shorter way round.
    let turn = to.az - from.az;
    turn = ((turn + Math.PI) % (2 * Math.PI) + 2 * Math.PI) % (2 * Math.PI) - Math.PI;
    const FLAT = 0.002;  // depth of the pressed box (0 is not allowed)
    const fromDepth = target.layout.scene.aspectratio.z;
    const toDepth = flat ? FLAT : landscape.depth;
    const fromUp = camera.up || { x: 0, y: 0, z: 1 };
    const toUp = flat ? { x: 0, y: 1, z: 0 } : { x: 0, y: 0, z: 1 };
    // In stages, so every frame on the way reads well (scrolling can stop
    // anywhere): flattening first turns to face the map, then rises and
    // presses it flat; lifting it out goes the other way round.
    const stage = (k, a, b) => {
      const t = Math.min(Math.max((k - a) / (b - a), 0), 1);
      return t * t * (3 - 2 * t);
    };
    const fromFlatness = (landscape.depth - fromDepth) / (landscape.depth - FLAT);
    return (k) => {
      const kTurn = flat ? stage(k, 0, 0.55) : stage(k, 0.45, 1);
      const kRise = flat ? stage(k, 0.2, 1) : stage(k, 0, 0.8);
      const layout = {
        "scene.camera": {
          eye: fromSpherical({
            r: from.r + (to.r - from.r) * kRise,
            az: from.az + turn * kTurn,
            el: from.el + (to.el - from.el) * kRise,
          }),
          up: Object.fromEntries(["x", "y", "z"].map((a) => [a, fromUp[a] + (toUp[a] - fromUp[a]) * kRise])),
          center: { x: 0, y: 0, z: 0 },
        },
        "scene.aspectratio.z": fromDepth + (toDepth - fromDepth) * kRise,
      };
      // 0 in depth, 1 flat: the markers shrink as the map flattens.
      return { layout, flatness: fromFlatness + ((flat ? 1 : 0) - fromFlatness) * kRise };
    };
  }

  // Big points in depth, where the opening relies on them; small ones
  // once flat, where they must not hide each other (smaller on phones).
  const MARKERS = (target) => target.clientWidth < 600
    ? { depth: [8, 12], flat: [6, 11] }
    : { depth: [12, 15], flat: [7, 13] };
  // The size and name size for a flatness; null when they stay the same,
  // so a frame only restyles the points when they change size.
  function markerStyle(target, flatness) {
    const { depth, flat } = MARKERS(target);
    const size = Math.round(depth[0] + (flat[0] - depth[0]) * flatness);
    const text = Math.round(depth[1] + (flat[1] - depth[1]) * flatness);
    landscape.flatness = flatness;
    if (size === landscape.markerSize && text === landscape.textSize) return null;
    landscape.markerSize = size;
    landscape.textSize = text;
    return { "marker.size": size, "textfont.size": text };
  }
  // One call per frame: camera and box, plus the points when they resize.
  function applyScene(target, { layout, flatness }) {
    const style = markerStyle(target, flatness);
    return style ? Plotly.update(target, style, layout) : Plotly.relayout(target, layout);
  }

  // The switch, the URL and the hint follow the view.
  function showView(flat) {
    visit.save({ view: flat ? "flat" : "depth" });
    document.querySelectorAll("#map-controls [data-view]").forEach((button) =>
      button.setAttribute("aria-pressed", String((button.dataset.view === "flat") === flat)));
    const url = new URL(location.href);
    if (flat) url.searchParams.set("view", "flat");
    else url.searchParams.delete("view");
    history.replaceState(null, "", url);
    showHint(flat);
    renderMapShare(flat);
  }
  // The map in depth turns when dragged; the flat map stays where it is
  // (no dragging it across the screen).
  const settleScene = (flat) => Plotly.relayout(document.getElementById("plot-3d"), {
    "scene.dragmode": flat ? false : "turntable",
    ...axesStyle(flat),
  });

  // The axes' colours. In depth all three, with their titles (the share
  // each explains). Flat: the depth axis disappears, and the other two
  // titles step aside for the overlay's, which name the axes in full.
  const CLEAR = "rgba(0, 0, 0, 0)";
  function axesStyle(flat) {
    const style = {};
    for (const [axis, shown, titled] of [["xaxis", true, !flat], ["yaxis", true, !flat], ["zaxis", !flat, !flat]]) {
      style[`scene.${axis}.gridcolor`] = shown ? css("--grid") : CLEAR;
      style[`scene.${axis}.zerolinecolor`] = shown ? css("--zero") : CLEAR;
      style[`scene.${axis}.tickfont.color`] = shown ? css("--ink-3") : CLEAR;
      style[`scene.${axis}.title.font.color`] = titled ? css("--ink-2") : CLEAR;
    }
    return style;
  }

  // The switch: about a second either way. Before the scroll has
  // flattened the map, this also turns the opening into the caption.
  function setFlat(flat, { animate = true } = {}) {
    showView(flat);
    if (!landscape.has3d || !window.Plotly || landscape.flat === flat) {
      landscape.flat = flat;
      return;
    }
    landscape.flat = flat;
    landscape.stopRotating?.();
    landscape.showDetails?.();
    const target = document.getElementById("plot-3d");
    const plan = planMorph(flat);
    const fromP = morph.p;
    morphed();
    // Before the scroll got there, the map also moves to where the
    // caption leaves room.
    const at = (k) => {
      const frame = plan(k);
      if (fromP < 1 && !frameEl().classList.contains("is-fullscreen")) {
        frame.layout["scene.domain"] = sceneDomain(target, fromP + (1 - fromP) * k);
      }
      return frame;
    };
    if (!animate || reducedMotion) {
      applyScene(target, at(1)).then(() => settleScene(flat));
      return;
    }
    const DURATION = 1100;
    const started = performance.now();
    const run = (now) => {
      if (landscape.flat !== flat) return;  // changed again halfway
      const t = Math.min((now - started) / DURATION, 1);
      applyScene(target, at(t)).then(() => (t < 1 ? requestAnimationFrame(run) : settleScene(flat)));
    };
    requestAnimationFrame(run);
  }

  // ---------- Scrolling flattens the opening map ----------
  // The scroll over the pinned stage drives the plan from 0 to 1. Until it
  // reaches 1, scrolling back up lifts the map out again; at 1 the map is
  // flat for the rest of the visit, also when scrolling back up.
  // Each frame does one update and skips while the last is still drawing,
  // so a fast scroll never builds a queue. The map moves sideways (the
  // costly part) once, after the flattening.
  // The map's state for this visit (this tab): once the map has formed,
  // coming back to the page (from a motion, say) opens it formed, in the
  // view and with the marks left, instead of playing the change again.
  const visit = {
    KEY: "chartist.map",
    read() {
      try { return JSON.parse(sessionStorage.getItem(this.KEY)) || {}; } catch { return {}; }
    },
    save(change) {
      try { sessionStorage.setItem(this.KEY, JSON.stringify({ ...this.read(), ...change })); } catch { /* not kept */ }
    },
  };

  const morph = { p: 0, plan: null, done: false, queued: false, busy: false, again: false };
  function morphed({ glide = true } = {}) {
    if (morph.done) return;
    visit.save({ formed: true });
    // A formed map is past the opening: the menu is shown from here on.
    document.body.classList.add("scrolled");
    morph.done = true;
    morph.p = 1;
    const hero = document.getElementById("hero");
    // The title leaves the column, so the controls and axes below move up
    // to the caption: they glide there instead of jumping.
    const moving = [document.getElementById("map-controls"), document.getElementById("map-axes")]
      .filter((node) => node.closest("#map-info"));
    const tops = moving.map((node) => node.getBoundingClientRect().top);
    hero.classList.add("morphed");
    hero.style.setProperty("--p", 1);
    if (glide && !reducedMotion) {
      moving.forEach((node, i) => {
        const shift = tops[i] - node.getBoundingClientRect().top;
        if (shift) node.animate([{ transform: `translateY(${shift}px)` }, { transform: "none" }], { duration: 550, easing: "ease" });
      });
    }
    // The pinned stretch has done its job: remove it, and keep everything
    // on screen where it is. Without this, the flat map stays pinned for
    // another screen of scrolling, down and back up, while nothing
    // happens. The browser may already keep the content in place itself
    // (scroll anchoring), so the correction is measured, not assumed:
    // whatever the content below the map still moved is scrolled back.
    const below = document.querySelector(".band");
    const before = below.getBoundingClientRect().top;
    hero.style.setProperty("--morph", "0px");
    const moved = below.getBoundingClientRect().top - before;
    if (Math.abs(moved) > 0.5) window.scrollBy({ top: moved, behavior: "instant" });
    document.getElementById("map-caption").inert = false;
    document.getElementById("map-axes").inert = false;  // its links work from now on
    document.getElementById("map-controls").inert = false;
  }
  // Back on the page in this visit: the map is formed from the start (the
  // map itself is set to match once drawn, below).
  const returning = visit.read();
  if (returning.formed) morphed({ glide: false });

  function scheduleMorph() {
    if (morph.done || morph.queued) return;
    morph.queued = true;
    requestAnimationFrame(morphStep);
  }
  function morphStep() {
    morph.queued = false;
    if (morph.done) return;
    const hero = document.getElementById("hero");
    const distance = hero.offsetHeight - window.innerHeight;
    const p = distance > 1 ? Math.min(Math.max(window.scrollY / distance, 0), 1) : Number(window.scrollY > 0);
    hero.style.setProperty("--p", p);
    if (!landscape.has3d || !window.Plotly) return;
    if (morph.busy) {
      morph.again = true;
      return;
    }
    const target = document.getElementById("plot-3d");
    if (p > 0 && !morph.plan) {
      landscape.stopRotating?.();
      landscape.showDetails?.();
      morph.plan = planMorph(true);
    }
    if (!morph.plan) return;
    morph.busy = true;
    applyScene(target, morph.plan(p)).then(() => {
      morph.busy = false;
      if (p === 0) morph.plan = null;  // back at the start: plan again from wherever the map is turned
      if (p >= 1) finishMorph(target);
      else if (morph.again) {
        morph.again = false;
        scheduleMorph();
      }
    });
  }
  // Flat for the rest of the visit; then the map slides over to where the
  // caption leaves room, in a few frames.
  function finishMorph(target) {
    landscape.flat = true;
    showView(true);
    settleScene(true);
    morphed();
    if (frameEl().classList.contains("is-fullscreen")) return;
    const STEPS = 10;
    const slide = (i) => {
      const k = i / STEPS;
      Plotly.relayout(target, { "scene.domain": sceneDomain(target, k * k * (3 - 2 * k)) })
        .then(() => { if (i < STEPS) requestAnimationFrame(() => slide(i + 1)); });
    };
    slide(1);
  }
  window.addEventListener("scroll", scheduleMorph, { passive: true });

  document.querySelectorAll("#map-controls [data-view]").forEach((button) =>
    button.addEventListener("click", () => setFlat(button.dataset.view === "flat")));

  // ---------- Over the map: logos and axis labels ----------
  // Plotly draws no images in 3D, so the logos are a layer on top, placed
  // with the map's own projection: every frame in which the camera or the
  // box changed (turning, flattening, dragging), each party's position is
  // projected to the screen. The flat map gets its axis labels this way
  // too, with the share each axis explains.
  const frameEl = () => document.getElementById("plot-frame");
  function buildLogos(usable) {
    const layer = document.getElementById("map-logos");
    const tip = document.getElementById("map-tip");
    layer.replaceChildren(...usable.map((p) => {
      const link = el("a", { className: "map-logo", href: `/party/${p.partyId}/`, ariaLabel: p.name },
        partyLogo(p, { size: "md" }));
      link.dataset.party = p.partyId;
      const show = () => {
        tip.replaceChildren(p.name, el("span", {},
          `PC1 ${number(p.x, 1)} · PC2 ${number(p.y, 1)} · PC3 ${number(p.z, 1)}`));
        tip.hidden = false;
        const at = link.style.transform.match(/-?[\d.]+(?=px)/g) || [0, 0];
        tip.style.transform = `translate(${at[0]}px, ${at[1]}px) translate(-50%, calc(-100% - 18px))`;
      };
      for (const type of ["mouseenter", "focus"]) link.addEventListener(type, show);
      for (const type of ["mouseleave", "blur"]) link.addEventListener(type, () => { tip.hidden = true; });
      return link;
    }));
    onFocus((partyId) => {
      layer.classList.toggle("focusing", Boolean(partyId));
      layer.querySelectorAll(".map-logo").forEach((link) =>
        link.classList.toggle("is-focus", Number(link.dataset.party) === partyId));
    });
    requestAnimationFrame(drawOverlay);
  }

  let overlaySignature = "";
  function drawOverlay() {
    requestAnimationFrame(drawOverlay);
    const target = document.getElementById("plot-3d");
    if (!landscape.has3d || document.hidden || !heroInView) return;
    const project = projector(target);
    if (!project) return;
    const { view, model, box } = sceneGeometry(target);
    const flat = landscape.flatness >= 0.98;
    const signature = [...view, ...model, box.left, box.width, box.height, landscape.marks, flat].join();
    if (signature === overlaySignature) return;
    overlaySignature = signature;

    if (landscape.marks === "logos") {
      // Big in depth and bigger still once flat, where they are the map;
      // in depth, nearer parties larger than those further back.
      const base = 1.15 + 0.2 * landscape.flatness;
      const placed = landscape.usable.map((p) => project(p.x, p.y, p.z));
      const meanDistance = placed.reduce((sum, at) => sum + at.distance, 0) / placed.length;
      document.querySelectorAll("#map-logos .map-logo").forEach((link, i) => {
        const at = placed[i];
        const near = Math.min(Math.max(meanDistance / at.distance, 0.75), 1.35);
        link.style.transform =
          `translate(${at.x.toFixed(1)}px, ${at.y.toFixed(1)}px) translate(-50%, -50%) scale(${(base * near).toFixed(3)})`;
        link.style.zIndex = Math.round((1 - at.depth) * 1000);  // nearer on top
      });
    }
    // Flat: name each axis, with its share, beside the map's edge.
    const [xRange, yRange] = landscape.ranges;
    const xLabel = document.getElementById("axis-x");
    const yLabel = document.getElementById("axis-y");
    xLabel.hidden = yLabel.hidden = !flat;
    if (!flat) return;
    const share = (number) => [
      el("strong", {}, `PC${number} `),
      el("span", {}, Number.isFinite(landscape.variance[number])
        ? `· ${pct(landscape.variance[number], 1)} ${t("of the differences →")}` : t("→")),
    ];
    xLabel.replaceChildren(...share(1));
    yLabel.replaceChildren(...share(2));
    const bottom = project((xRange[0] + xRange[1]) / 2, yRange[0], 0);
    const left = project(xRange[0], (yRange[0] + yRange[1]) / 2, 0);
    xLabel.style.transform = `translate(${bottom.x}px, ${bottom.y + 14}px) translate(-50%, 0)`;
    yLabel.style.transform = `translate(${left.x - 46}px, ${left.y}px) translate(-50%, -50%) rotate(-90deg)`;
  }
  let heroInView = true;
  new IntersectionObserver(([entry]) => { heroInView = entry.isIntersecting; })
    .observe(document.getElementById("hero"));

  // Dots (Plotly's points and names) or logos (the layer above).
  function setMarks(mode) {
    landscape.marks = mode;
    visit.save({ marks: mode });
    document.querySelectorAll("#map-controls [data-marks]").forEach((button) =>
      button.setAttribute("aria-pressed", String(button.dataset.marks === mode)));
    document.getElementById("map-logos").hidden = mode !== "logos";
    document.getElementById("map-tip").hidden = true;
    overlaySignature = "";
    if (landscape.has3d && window.Plotly) {
      // Hidden, not removed: without a trace Plotly drops the scene too.
      const dots = mode === "dots";
      Plotly.restyle(document.getElementById("plot-3d"), {
        mode: dots ? "markers+text" : "markers",
        "marker.opacity": dots ? 1 : 0,
        hoverinfo: dots ? "all" : "skip",
      });
      landscape.showDetails?.();
    }
  }
  document.querySelectorAll("#map-controls [data-marks]").forEach((button) =>
    button.addEventListener("click", () => setMarks(button.dataset.marks)));

  // ---------- The map's controls: in the column, or docked ----------
  // Wide screens have the column beside the map; narrower ones dock the
  // same controls under the map. So does fullscreen, where the map should
  // get the whole window, not share it with the column.
  const wideLayout = matchMedia("(min-width: 1000px)");
  function placeControls() {
    const controls = document.getElementById("map-controls");
    const fullscreen = document.getElementById("plot-frame").classList.contains("is-fullscreen");
    if (wideLayout.matches && !fullscreen) document.getElementById("map-axes").before(controls);
    else document.getElementById("map-dock").append(controls);
  }
  wideLayout.addEventListener("change", placeControls);
  placeControls();

  // Highlight: the list holds only parties (its prompt cannot be chosen);
  // the cross next to it clears the highlight.
  const clearFocus = document.getElementById("clear-focus");
  clearFocus.addEventListener("click", () => setFocus(null));
  onFocus((partyId) => { clearFocus.hidden = !partyId; });
  clearFocus.hidden = !state.focusedParty;

  function renderMapShare(flat) {
    if (!Object.keys(landscape.variance).length) return;
    const share = displayedVariance(landscape.variance, flat);
    const caption = t("Combined, the axes explain {share} of the differences.", { share: pct(share, 1) });
    document.getElementById("map-total").textContent = caption;
    document.getElementById("stat-variance").textContent = pct(share);
    document.querySelector("#stat-variance + .label abbr").title = caption;
  }

  // Shortcuts under the map's caption: each axis, its share, its page.
  function renderMapAxes(analysis) {
    const components = [...(analysis?.components || [])].sort((a, b) => a.number - b.number);
    const role = { 1: t("across"), 2: t("up and down"), 3: t("depth") };
    const top = Math.max(0, ...components.map((c) => c.explained_variance)) || 1;
    document.getElementById("map-axes").replaceChildren(...components.map((c) => {
      const meter = el("span", { className: "meter" }, el("span"));
      meter.firstChild.style.width = `${(c.explained_variance / top) * 100}%`;
      return el("a", { href: `/component/${c.number}/`, title: t("What drives PC{number}", { number: c.number }) },
        el("span", {}, el("strong", {}, `PC${c.number}`), role[c.number] || ""),
        el("span", { className: "share" }, pct(c.explained_variance, 1)),
        roundArrow(),
        meter);
    }));
  }

  const landscapeLoaded = (async () => {
    const [parties, analysis] = await Promise.all([
      requests.parties,
      requests.analysis.catch(() => null),
    ]);
    const variance = Object.fromEntries(
      (analysis?.components || []).map((c) => [Number(c.number), Number(c.explained_variance)])
    );
    document.getElementById("stat-parties").textContent = parties.length;
    landscape.variance = variance;
    renderMapShare(landscape.flat);

    const focus = document.getElementById("focus");
    const points = toPoints(parties);
    const mappedIds = new Set(points.filter((p) => Number.isFinite(p.z)).map((p) => p.partyId));
    [...parties]
      .filter((p) => mappedIds.has(p.id))
      .sort((a, b) => a.abbreviation.localeCompare(b.abbreviation))
      .forEach((p) => focus.append(el("option", { value: p.id }, p.abbreviation)));
    if (state.focusedParty && !mappedIds.has(state.focusedParty)) setFocus(null);
    focus.value = state.focusedParty ?? "";
    focus.addEventListener("change", () => setFocus(Number(focus.value) || null));

    renderAxes(analysis, points);
    renderMapAxes(analysis);
    if (!points.length) {
      document.getElementById("plot-3d").replaceChildren(
        el("div", { className: "placeholder" }, t("No PCA scores yet. Run the analysis first."))
      );
      return;
    }
    await plotlyLoaded;
    landscape.has3d = renderPca3d(points, variance);
    if (!landscape.has3d) {
      document.getElementById("plot-3d").replaceChildren(
        el("div", { className: "placeholder" }, t("No 3D scores yet. Run the analysis first.")));
      return;
    }
    // A shared link to the flat map opens flat; back on the page in this
    // visit, the map is as it was left.
    if (new URLSearchParams(location.search).get("view") === "flat") {
      setFlat(true, { animate: false });
    } else if (returning.formed) {
      landscape.stopRotating?.();
      landscape.showDetails?.();
      if (returning.view === "depth") {
        showView(false);
        settleScene(false);
      } else {
        setFlat(true, { animate: false });
      }
    }
    if (returning.marks === "logos") setMarks("logos");
  })().catch((error) => {
    document.getElementById("plot-3d").replaceChildren(
      el("div", { className: "placeholder" }, t("Could not load the landscape: {error}", { error: error.message }))
    );
  });

  const landscape = {
    has3d: null,
    depth: null,
    flat: false,
    flatness: 0,
    marks: "dots",
    markerSize: null,
    textSize: null,
    usable: [],
    ranges: null,
    variance: {},
    fullscreenBusy: false,
    showDetails: null,
    stopRotating: null,
  };
  // Plotly loads with `defer`, which runs before DOMContentLoaded.
  const plotlyLoaded = new Promise((resolve) => {
    if (document.readyState !== "loading") resolve();
    else document.addEventListener("DOMContentLoaded", resolve, { once: true });
  });
  document.getElementById("plot-3d").replaceChildren(el("div", { className: "placeholder" }, t("Loading the map…")));

  // Fullscreen fills the browser window with the map, with its controls
  // (not the whole screen). Escape or the button closes it. Only here does
  // scrolling zoom.
  const frame = frameEl();
  const fullscreenButton = document.getElementById("fullscreen");
  function setFullscreen(on) {
    landscape.fullscreenBusy = true;
    setTimeout(() => { landscape.fullscreenBusy = false; }, 300);
    frame.classList.toggle("is-fullscreen", on);
    document.getElementById("hero").classList.toggle("fullscreen", on);
    document.body.classList.toggle("no-scroll", on);
    fullscreenButton.setAttribute("aria-pressed", String(on));
    placeControls();
    fullscreenButton.querySelector("span").textContent = fullscreenLabel(on);
    fullscreenButton.title = on ? t("Back to the page (Esc)") : t("Show the map on its own, filling the window");
    if (landscape.has3d && window.Plotly) {
      const target = document.getElementById("plot-3d");
      // The whole window, above the docked controls, and the camera that
      // much closer, so the map really grows (back out on leaving).
      const full = { x: [0, 1], y: [0.12, 0.97] };
      target.layout.scene.domain = on ? full : sceneDomain(target, morph.p);
      const camera = target.layout.scene.camera;
      if (camera?.eye && landscape.fullscreen !== on) {
        const factor = on ? 0.86 : 1 / 0.86;
        camera.eye = { x: camera.eye.x * factor, y: camera.eye.y * factor, z: camera.eye.z * factor };
      }
      landscape.fullscreen = on;
      Plotly.react(target, target.data, target.layout, heroConfig());
    }
    overlaySignature = "";
  }
  const toggleFullscreen = () => setFullscreen(!frame.classList.contains("is-fullscreen"));
  // On touch screens the map turns only in fullscreen: the button says so.
  const fullscreenLabel = (on) => (on ? t("Exit fullscreen") : touchScreen ? t("Explore") : t("Fullscreen"));
  fullscreenButton.querySelector("span").textContent = fullscreenLabel(false);
  fullscreenButton.classList.toggle("labelled", touchScreen);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && frame.classList.contains("is-fullscreen")) setFullscreen(false);
  });
  fullscreenButton.addEventListener("click", toggleFullscreen);


  registerMapExport(landscape);
  return { landscapeLoaded, setFlat, isFormed: () => morph.done };
}
