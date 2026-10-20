// Chartist: helpers and header behaviour shared by every page.
// Loaded before each page's own script, so these are plain globals.

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

const pct = (value, digits = 0) => `${(value * 100).toFixed(digits)}%`;

// Dates from the API are "YYYY-MM-DD" (local) or ISO timestamps.
const toDate = (value) => new Date(/^\d{4}-\d{2}-\d{2}$/.test(value) ? `${value}T00:00:00` : value);
const formatDate = (value) =>
  value
    ? toDate(value).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" })
    : "Unknown date";
const formatDateTime = (value) =>
  toDate(value).toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
const formatMonth = (value) =>
  toDate(value).toLocaleDateString(undefined, { month: "short", year: "numeric" });

const STATUS_CLASS = { Accepted: "accepted", Rejected: "rejected", Pending: "pending" };
const statusBadge = (status) => el("span", { className: `badge ${STATUS_CLASS[status] || ""}` }, status);

const VOTE_LABEL = { For: "For", Against: "Against", Abstain: "Did not vote" };
const VOTE_CLASS = { For: "for", Against: "against" };
const voteBadge = (vote) =>
  el("span", { className: `badge ${VOTE_CLASS[vote] || ""}` }, VOTE_LABEL[vote] || "No vote");

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
    backgroundColor: "#111827",
    titleColor: "#ffffff",
    bodyColor: "#e5e7eb",
    footerColor: "#9ca3af",
    padding: 10,
    cornerRadius: 8,
    boxPadding: 4,
  });
}

// ---------- Header: sync status ----------
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
    text.textContent = failed
      ? `Sync failed ${formatDateTime(failed)}`
      : status.last_synced_at ? `Synced ${formatDateTime(status.last_synced_at)}` : "Never synced";
    const details = [
      status.last_synced_at ? `Last sync: ${new Date(status.last_synced_at).toLocaleString()}` : "Never synced",
      status.latest_vote_date ? `Votes through ${formatDate(status.latest_vote_date)}` : null,
      status.latest_analysis_at ? `Analysis: ${new Date(status.latest_analysis_at).toLocaleString()}` : "No analysis yet",
    ].filter(Boolean);
    pill.title = details.join("\n");
    const footer = document.getElementById("footer-status");
    if (footer) footer.textContent = details.join(" · ");
  } catch (error) {
    text.textContent = "Status unavailable";
    pill.title = error.message;
  }
})();

// ---------- Header: mark the current page ----------
(() => {
  const current = document.body.dataset.nav;
  if (current) document.querySelector(`.nav a[data-nav="${current}"]`)?.setAttribute("aria-current", "page");
})();

// ---------- Header: highlight the section in view (overview anchors) ----------
(() => {
  if (document.body.dataset.nav !== "overview") return;
  const links = [...document.querySelectorAll(".nav a[data-section]")].filter((link) =>
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
      nodes.push(el("div", { className: "group" }, "Parties"));
      matches.forEach((p) => {
        const link = el("a", { href: `/party/${p.id}/`, className: "party", role: "option" },
          partyLogo(p, { size: "sm" }),
          el("span", {}, p.abbreviation, p.name !== p.abbreviation ? el("span", { className: "sub" }, p.name) : null));
        nodes.push(link);
      });
    }
    const status = el("div", { className: "empty" }, "Searching...");
    box.replaceChildren(...nodes, el("div", { className: "group" }, "Motions"), status);
    open(true);
    select(matches.length ? 0 : -1);
    if (query.length < 3) {
      status.textContent = "Type at least 3 letters to search motions.";
      return;
    }
    try {
      const data = await fetchJson(`/api/v1/items/?${new URLSearchParams({ search: query, limit: 6 })}`);
      if (current !== request) return;
      const motions = data.results.map((m) =>
        option(`/motion/${m.id}/`, m.title, `${formatDate(m.vote_date)} · ${m.status}`)
      );
      status.remove();
      if (motions.length) box.append(...motions);
      else box.append(el("div", { className: "empty" }, "No motions found."));
      if (data.count > motions.length) {
        box.append(option(
          `/motions/?${new URLSearchParams({ search: query })}`,
          `Show all ${data.count.toLocaleString()} matching motions`, "", "all"
        ));
      }
      if (active === -1) select(0);
    } catch (error) {
      if (current === request) status.textContent = `Could not search motions: ${error.message}`;
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
