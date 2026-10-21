// Chartist: helpers and header behaviour shared by every page.
// Loaded before each page's own script, so these are plain globals.

// ---------- Language ----------
// The page's language (Dutch by default; the header switches it). Texts
// built here are written in English and looked up in window.I18N, which the
// templates fill with their translations (base.html for these, each page for
// its own). {name} in a text is filled from `values`.
const LANG = document.documentElement.lang || "nl";
const t = (text, values = {}) =>
  (window.I18N?.[text] ?? text).replace(/\{(\w+)\}/g, (_, name) => String(values[name] ?? ""));
// A count with its singular or plural text: tn(3, "{count} party",
// "{count} parties").
const tn = (count, one, other, values = {}) =>
  t(count === 1 ? one : other, { ...values, count: number(count) });
// "FVD, PVV and Groep Markuszower", in the page's language.
const listNames = (names) =>
  names.length > 1 ? t("{a} and {b}", { a: names.slice(0, -1).join(", "), b: names.at(-1) }) : names.join("");
// Numbers as the language writes them: 36,9 in Dutch, 36.9 in English.
const number = (value, digits = 0) =>
  Number(value).toLocaleString(LANG, { minimumFractionDigits: digits, maximumFractionDigits: digits });

async function fetchJson(url) {
  const response = await fetch(url, {
    headers: { Accept: "application/json" },
    credentials: "same-origin",
  });
  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
  return response.json();
}

// Paginated and plain list responses alike.
const results = (payload) =>
  Array.isArray(payload?.results) ? payload.results : Array.isArray(payload) ? payload : [];

// Current value of a CSS custom property, e.g. css("--accent").
const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

// Create an element: el("a", { href, className }, "text", child, ...).
function el(tag, props = {}, ...children) {
  const node = Object.assign(document.createElement(tag), props);
  node.append(...children.filter((child) => child !== null && child !== undefined));
  return node;
}

// A party's logo in a fixed frame. Without a logo, `fallback` shows its
// initials in the same frame (for lists that should stay aligned) and
// otherwise nothing. Decorative: the name is always shown next to it.
function partyLogo(party, { size = "", fallback = true } = {}) {
  const className = `logo ${size}`.trim();
  if (party.logo_url) {
    return el("span", { className, ariaHidden: "true" },
      el("img", { src: party.logo_url, alt: "", loading: "lazy", decoding: "async" }));
  }
  if (!fallback) return null;
  const words = party.abbreviation.split(/\s+/);
  const initials = words.length > 1 ? words.map((w) => w[0]).join("") : party.abbreviation.slice(0, 2);
  return el("span", { className: `${className} initials`, ariaHidden: "true" }, initials.slice(0, 3));
}

// A right arrow for round buttons, drawn rather than typed: a text "→"
// sits off-centre in a circle (its glyph is not in the middle of its box).
function roundArrow(className = "round-arrow") {
  const span = el("span", { className, ariaHidden: "true" });
  span.innerHTML = '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" '
    + 'stroke-linecap="round" stroke-linejoin="round"><path d="M3.5 8h9M8.5 4l4 4-4 4"/></svg>';
  return span;
}

const pct = (value, digits = 0) => `${number(value * 100, digits)}%`;
// A share as a CSS length (always with a decimal point, unlike pct).
const cssPct = (value) => `${Number(value) * 100}%`;

// Parties on a number line by their score, as dots or as logos. Parties
// too close to share the line step aside, alternately above and below it,
// so every party stays visible. Each is a link to its page; hovering or
// focusing one gives its score. Items: { id, abbreviation, logo_url,
// value, color }; `color` is for dots.
const PARTY_LINE = {
  dots: { width: 11, gap: 3, row: 13, min: 58 },
  logos: { width: 38, gap: 6, row: 32, min: 80 },
};
function partyLine(line, items, { mode = "logos" } = {}) {
  line.classList.add("party-line");
  line.replaceChildren();
  if (!items.length) return;
  const size = PARTY_LINE[mode];
  const values = items.map((item) => item.value);
  const [lo, hi] = [Math.min(...values), Math.max(...values)];
  const share = (value) => (value - lo) / (hi - lo || 1);
  if (lo < 0 && hi > 0) {
    const zero = el("span", { className: "zero" });
    zero.style.left = `${share(0) * 100}%`;
    line.append(zero);
  }
  const tip = el("div", { className: "party-line-tip", hidden: true });
  const width = line.clientWidth || 1;
  const lastInRow = [];  // x (px) of the last mark in each row
  // Rows 0, 1, 2, ... sit on the line, above it, below it, further above...
  const offset = (row) => (row % 2 ? -1 : 1) * Math.ceil(row / 2) * size.row;
  let rows = 1;
  [...items].sort((a, b) => a.value - b.value).forEach((item) => {
    const at = share(item.value);
    const x = at * width;
    let row = lastInRow.findIndex((last) => x - last >= size.width + size.gap);
    if (row === -1) row = lastInRow.length;
    lastInRow[row] = x;
    rows = Math.max(rows, row + 1);
    const score = number(item.value, 1);
    const mark = el("a", { className: `mark ${mode}`, href: `/party/${item.id}/`, ariaLabel: `${item.abbreviation}: ${score}` },
      mode === "logos" ? partyLogo(item) : el("span", { className: "dot" }));
    if (mode === "dots") mark.firstChild.style.background = item.color || css("--accent");
    mark.dataset.party = item.id;
    mark.dataset.label = item.abbreviation;
    if (at < 0.15) mark.classList.add("near-start");
    if (at > 0.85) mark.classList.add("near-end");
    mark.style.left = `${at * 100}%`;
    mark.style.top = `calc(50% + ${offset(row)}px)`;
    const show = () => {
      tip.replaceChildren(el("strong", {}, item.abbreviation), el("span", {}, score));
      tip.style.left = mark.style.left;
      tip.style.top = mark.style.top;
      tip.hidden = false;
    };
    for (const type of ["mouseenter", "focus"]) mark.addEventListener(type, show);
    for (const type of ["mouseleave", "blur"]) mark.addEventListener(type, () => { tip.hidden = true; });
    line.append(mark);
  });
  // Tall enough for every row used, above and below the line.
  line.style.height = `${Math.max(size.min, (Math.ceil((rows - 1) / 2) * 2 + 1) * size.row + 30)}px`;
  line.append(tip);
}
// Brings one party forward on a party line and fades the rest.
function highlightOnLine(line, partyId) {
  line.classList.toggle("focusing", Boolean(partyId));
  line.querySelectorAll(".mark").forEach((mark) =>
    mark.classList.toggle("is-focus", Number(mark.dataset.party) === partyId));
}

// Dates from the API are "YYYY-MM-DD" (local) or ISO timestamps.
const toDate = (value) => new Date(/^\d{4}-\d{2}-\d{2}$/.test(value) ? `${value}T00:00:00` : value);
const formatDate = (value) =>
  value
    ? toDate(value).toLocaleDateString(LANG, { day: "numeric", month: "short", year: "numeric" })
    : t("Unknown date");
const formatDateTime = (value) =>
  toDate(value).toLocaleString(LANG, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
const formatMonth = (value) =>
  toDate(value).toLocaleDateString(LANG, { month: "short", year: "numeric" });

const STATUS_CLASS = { Accepted: "accepted", Rejected: "rejected", Pending: "pending" };
// The API's values (Accepted, For, ...) are English; shown translated.
const statusLabel = (status) => t(status);
const statusBadge = (status) => el("span", { className: `badge ${STATUS_CLASS[status] || ""}` }, statusLabel(status));

const VOTE_LABEL = { For: "For", Against: "Against", Abstain: "Did not vote" };
const VOTE_CLASS = { For: "for", Against: "against" };
const voteBadge = (vote) =>
  el("span", { className: `badge ${VOTE_CLASS[vote] || ""}` }, t(VOTE_LABEL[vote] || "No vote"));

// Every calendar month from the first to the last, so a month without votes
// (e.g. the summer recess) shows as a gap instead of a skipped label.
function allMonths(months) {
  if (!months.length) return [];
  const [startYear, startMonth] = months[0].split("-").map(Number);
  const [endYear, endMonth] = months.at(-1).split("-").map(Number);
  const result = [];
  for (let y = startYear, m = startMonth; y < endYear || (y === endYear && m <= endMonth); ) {
    result.push(`${y}-${String(m).padStart(2, "0")}-01`);
    m += 1;
    if (m > 12) {
      m = 1;
      y += 1;
    }
  }
  return result;
}

// Shared Chart.js look: the page font and theme colors.
function chartDefaults() {
  if (!window.Chart) return;
  Chart.defaults.font.family = css("--font-sans");
  Chart.defaults.color = css("--ink-3");
  Object.assign(Chart.defaults.plugins.tooltip, {
    backgroundColor: css("--tooltip-bg"),
    titleColor: css("--tooltip-ink"),
    bodyColor: css("--tooltip-ink-2"),
    footerColor: css("--tooltip-ink-3"),
    padding: 10,
    cornerRadius: 8,
    boxPadding: 4,
  });
}

// ---------- Footer: sync status ----------
// One request per page; pages that show more of the status reuse it.
const statusRequest = fetchJson("/api/v1/status/");
(async () => {
  const pill = document.getElementById("status-pill");
  if (!pill) return;
  const text = pill.querySelector(".text");
  try {
    const status = await statusRequest;
    const failed = status.last_sync_failed_at;
    pill.classList.add(failed ? "failed" : status.last_synced_at ? "ok" : "none");
    text.textContent = [
      failed
        ? t("Sync failed {when}", { when: formatDateTime(failed) })
        : status.last_synced_at ? t("Synced {when}", { when: formatDateTime(status.last_synced_at) }) : t("Never synced"),
      status.latest_vote_date ? t("Votes through {date}", { date: formatDate(status.latest_vote_date) }) : null,
      status.latest_analysis_at
        ? t("Analysis {when}", { when: formatDateTime(status.latest_analysis_at) }) : t("No analysis yet"),
    ].filter(Boolean).join(" · ");
  } catch (error) {
    text.textContent = t("Status unavailable");
    pill.title = error.message;
  }
})();

// ---------- Header: mark the current page ----------
(() => {
  const current = document.body.dataset.nav;
  if (current) document.querySelector(`.nav a[data-nav="${current}"]`)?.setAttribute("aria-current", "page");
})();

// ---------- Chapter bar: mark the chapter in view ----------
// Links to a part of the page (data-section="<id>"), e.g. the home page's
// chapter bar; the one whose part is in the middle of the window is active.
(() => {
  const links = [...document.querySelectorAll("a[data-section]")].filter((link) =>
    document.getElementById(link.dataset.section)
  );
  if (!links.length) return;
  const observer = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      if (!entry.isIntersecting) continue;
      links.forEach((link) => link.classList.toggle("active", link.dataset.section === entry.target.id));
    }
  }, { rootMargin: "-40% 0px -55% 0px" });
  links.forEach((link) => observer.observe(document.getElementById(link.dataset.section)));
})();

// ---------- Header: global search (parties and motions) ----------
(() => {
  const input = document.getElementById("search");
  if (!input) return;
  const box = document.getElementById("search-results");
  const combo = input.closest(".search");
  let parties = null;
  let active = -1;
  let request = 0;
  let debounce;

  const loadParties = () => {
    parties ??= fetchJson("/api/v1/parties/?limit=500").then(results).catch(() => []);
    return parties;
  };
  const options = () => [...box.querySelectorAll("a")];
  function open(show) {
    box.hidden = !show;
    combo.setAttribute("aria-expanded", String(show));
  }
  function select(index) {
    const all = options();
    active = Math.max(-1, Math.min(index, all.length - 1));
    all.forEach((option, i) => option.setAttribute("aria-selected", String(i === active)));
    all[active]?.scrollIntoView({ block: "nearest" });
  }
  function option(href, label, sub, className = "") {
    const link = el("a", { href, className, role: "option" }, label);
    if (sub) link.append(el("span", { className: "sub" }, sub));
    return link;
  }

  async function render(query) {
    const current = ++request;
    const q = query.toLowerCase();
    const matches = (await loadParties())
      .filter((p) => p.name.toLowerCase().includes(q) || p.abbreviation.toLowerCase().includes(q))
      .slice(0, 5);
    if (current !== request) return;
    const nodes = [];
    if (matches.length) {
      nodes.push(el("div", { className: "group" }, t("Parties")));
      matches.forEach((p) => {
        const link = el("a", { href: `/party/${p.id}/`, className: "party", role: "option" },
          partyLogo(p, { size: "sm" }),
          el("span", {}, p.abbreviation, p.name !== p.abbreviation ? el("span", { className: "sub" }, p.name) : null));
        nodes.push(link);
      });
    }
    const status = el("div", { className: "empty" }, t("Searching..."));
    box.replaceChildren(...nodes, el("div", { className: "group" }, t("Motions")), status);
    open(true);
    select(matches.length ? 0 : -1);
    if (query.length < 3) {
      status.textContent = t("Type at least 3 letters to search motions.");
      return;
    }
    try {
      const data = await fetchJson(`/api/v1/items/?${new URLSearchParams({ search: query, limit: 6 })}`);
      if (current !== request) return;
      const motions = data.results.map((m) =>
        option(`/motion/${m.id}/`, m.title, `${formatDate(m.vote_date)} · ${statusLabel(m.status)}`)
      );
      status.remove();
      if (motions.length) box.append(...motions);
      else box.append(el("div", { className: "empty" }, t("No motions found.")));
      if (data.count > motions.length) {
        box.append(option(
          `/motions/?${new URLSearchParams({ search: query })}`,
          t("Show all {count} matching motions", { count: number(data.count) }), "", "all"
        ));
      }
      if (active === -1) select(0);
    } catch (error) {
      if (current === request) status.textContent = t("Could not search motions: {error}", { error: error.message });
    }
  }

  input.addEventListener("input", () => {
    clearTimeout(debounce);
    const query = input.value.trim();
    if (!query) {
      request++;
      open(false);
      return;
    }
    debounce = setTimeout(() => render(query), 200);
  });
  input.addEventListener("keydown", (event) => {
    if (event.key === "ArrowDown") { event.preventDefault(); select(active + 1); }
    else if (event.key === "ArrowUp") { event.preventDefault(); select(active - 1); }
    else if (event.key === "Enter") {
      event.preventDefault();
      if (active >= 0) options()[active].click();
      else if (input.value.trim()) location.href = `/motions/?${new URLSearchParams({ search: input.value.trim() })}`;
    }
    else if (event.key === "Escape") { open(false); input.blur(); }
  });
  input.addEventListener("focus", () => {
    loadParties();
    if (input.value.trim() && box.childElementCount) open(true);
  });
  document.addEventListener("click", (event) => { if (!combo.contains(event.target)) open(false); });
  document.addEventListener("keydown", (event) => {
    if (event.key === "/" && !/^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName)) {
      event.preventDefault();
      input.focus();
    }
  });
})();
