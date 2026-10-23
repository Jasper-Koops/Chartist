import { mainAxisColor } from "./data.js";

export function createOverview(state) {
  const { requests, onFocus, setFocus } = state;
  const axesView = { analysis: null, points: null, mode: "dots" };

  function renderAxes(analysis, allPoints, mode = axesView.mode) {
    Object.assign(axesView, { analysis, points: allPoints, mode });
    const box = document.getElementById("axes");
    const components = [...(analysis?.components || [])].sort((a, b) => a.number - b.number);
    if (!components.length || !allPoints.length) {
      box.replaceChildren(el("p", { className: "hint" }, t("No analysis yet. Run the analysis first.")));
      return;
    }
    box.classList.toggle("logos", mode === "logos");
    document.querySelectorAll("#axes-mode [data-mode]").forEach((button) =>
      button.setAttribute("aria-pressed", String(button.dataset.mode === mode)));
    const role = { 1: t("across the map"), 2: t("up and down"), 3: t("the depth") };
    const coordinate = { 1: "x", 2: "y", 3: "z" };
    const pending = [];
    box.replaceChildren(
      ...components.map((c) => {
        const key = coordinate[c.number];
        const placed = key ? allPoints.filter((p) => Number.isFinite(p[key])) : [];
        const line = el("div", { role: "group" });
        const ends = el("div", { className: "party-line-ends" });
        if (placed.length) {
          const sorted = [...placed].sort((a, b) => a[key] - b[key]);
          line.setAttribute("aria-label", t("Parties on PC{number}, from {from} to {to}", { number: c.number, from: sorted[0].label, to: sorted.at(-1).label }));
          ends.append(el("span", {}, sorted[0].label), el("span", {}, sorted.at(-1).label));
          // Placed once the line is on the page and has its width.
          pending.push(() => partyLine(line,
            placed.map((p) => ({
              id: p.partyId, abbreviation: p.abbreviation, logo_url: p.logo_url,
              value: p[key], color: mainAxisColor(p.x, allPoints),
            })),
            { mode }));
        }
        return el("article", { className: "axis" },
          el("div", { className: "axis-text" },
            el("p", { className: "axis-name" }, el("strong", {}, `PC${c.number}`), ` · ${role[c.number] || t("a further pattern")}`),
            el("div", { className: "axis-share" }, pct(c.explained_variance, 1)),
            el("p", { className: "axis-note" }, t("of the differences between parties"))),
          el("div", { className: "axis-line" }, line, ends),
          el("a", { className: "more", href: `/component/${c.number}/` },
            el("span", {}, t("The motions behind it")),
            roundArrow()),
        );
      })
    );
    pending.forEach((place) => place());
    // Side by side, the lines line up: all as tall as the tallest.
    const lines = [...box.querySelectorAll(".party-line")];
    const tallest = Math.max(0, ...lines.map((line) => line.offsetHeight));
    if (mode === "dots") lines.forEach((line) => { line.style.height = `${tallest}px`; });
    highlightAxes(state.focusedParty);
  }

  function highlightAxes(partyId) {
    document.querySelectorAll("#axes .party-line").forEach((line) => highlightOnLine(line, partyId));
  }
  onFocus(highlightAxes);
  document.querySelectorAll("#axes-mode [data-mode]").forEach((button) =>
    button.addEventListener("click", () => {
      if (axesView.points) renderAxes(axesView.analysis, axesView.points, button.dataset.mode);
    }));
  // The marks are placed in pixels: place them again when the width changes.
  let axesWidth = 0;
  new ResizeObserver(([entry]) => {
    const width = Math.round(entry.contentRect.width);
    if (width === axesWidth) return;
    axesWidth = width;
    if (axesView.points) renderAxes(axesView.analysis, axesView.points);
  }).observe(document.getElementById("axes"));

  // ---------- 03: agreement matrix ----------
  // Sequential ramp from the paper color (low agreement) to deep blue
  // (high), so blocs show as dark squares.
  const AGREEMENT_RAMP = [
    "#f3ece0", "#dde0dd", "#c3d0db", "#a6bdd5", "#88a7cb",
    "#6a8fbe", "#4f77ad", "#365f9a", "#1f4e8c",
  ];
  function rampRgb(t) {
    const hex = (h) => { const n = parseInt(h.slice(1), 16); return [(n >> 16) & 255, (n >> 8) & 255, n & 255]; };
    const pos = Math.min(Math.max(t, 0), 1) * (AGREEMENT_RAMP.length - 1);
    const i = Math.min(Math.floor(pos), AGREEMENT_RAMP.length - 2);
    const a = hex(AGREEMENT_RAMP[i]);
    const b = hex(AGREEMENT_RAMP[i + 1]);
    return a.map((c, k) => Math.round(c + (b[k] - c) * (pos - i)));
  }
  // Black or white cell text, whichever contrasts more with the cell (WCAG
  // relative luminance). The worst case on this ramp is 4.6:1.
  function cellInk(rgb) {
    const [r, g, b] = rgb.map((c) => {
      const v = c / 255;
      return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
    });
    const luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b;
    return luminance > 0.179 ? "#000000" : "#ffffff";
  }
  // Fit the ramp to the observed values, rounded out to 5%.
  function agreementDomain(agreements) {
    const values = agreements.map((a) => a.agreement).filter((v) => v !== null);
    if (!values.length) return [0, 1];
    const lo = Math.floor(Math.min(...values) * 20) / 20;
    const hi = Math.ceil(Math.max(...values) * 20) / 20;
    return lo < hi ? [lo, hi] : [Math.max(lo - 0.05, 0), hi];
  }

  // Order parties so similar ones are adjacent: average-linkage clustering
  // on 1 - agreement; when merging, keep the orientation whose touching ends
  // are closest.
  function clusterOrder(parties, lookup) {
    const distance = (a, b) => {
      const pair = lookup.get(`${a.id}-${b.id}`);
      return pair && pair.agreement !== null ? 1 - pair.agreement : null;
    };
    const linkage = (left, right) => {
      let sum = 0;
      let count = 0;
      for (const a of left) for (const b of right) {
        const d = distance(a, b);
        if (d !== null) { sum += d; count += 1; }
      }
      return count ? sum / count : Infinity;
    };
    const endGap = (a, b) => distance(a, b) ?? 1;
    let clusters = parties.map((party) => [party]);
    while (clusters.length > 1) {
      let best = null;
      for (let i = 0; i < clusters.length; i++) {
        for (let j = i + 1; j < clusters.length; j++) {
          const d = linkage(clusters[i], clusters[j]);
          if (!best || d < best.d) best = { i, j, d };
        }
      }
      const left = clusters[best.i];
      const right = clusters[best.j];
      const [a, b] = [
        [left, right],
        [[...left].reverse(), right],
        [left, [...right].reverse()],
        [[...left].reverse(), [...right].reverse()],
      ].reduce((keep, option) =>
        endGap(option[0].at(-1), option[1][0]) < endGap(keep[0].at(-1), keep[1][0]) ? option : keep
      );
      clusters = clusters.filter((_, k) => k !== best.i && k !== best.j);
      clusters.push([...a, ...b]);
    }
    return clusters[0] || [];
  }

  function renderMatrix(matrix, lookup, names) {
    const table = document.getElementById("matrix");
    const parties = clusterOrder(matrix.parties, lookup);
    const [lo, hi] = agreementDomain(matrix.agreements);
    const scale = (value) => rampRgb((value - lo) / (hi - lo));

    document.getElementById("legend-bar").style.background =
      `linear-gradient(to right, ${AGREEMENT_RAMP.join(", ")})`;
    document.getElementById("legend-min").textContent = pct(lo);
    document.getElementById("legend-max").textContent = pct(hi);
    document.getElementById("legend").hidden = false;

    const nameLink = (party) =>
      el("a", { href: `/party/${party.id}/`, title: names.get(party.id) || party.abbreviation }, party.abbreviation);
    const header = el("tr", {}, el("th"));
    parties.forEach((party) =>
      header.append(el("th", { className: "col" }, nameLink(party)))
    );
    header.querySelectorAll("th.col").forEach((th, i) => { th.dataset.col = parties[i].id; });
    const rows = [header];
    for (const party of parties) {
      const row = el("tr", {}, el("th", { className: "row" }, nameLink(party)));
      row.firstChild.dataset.row = party.id;
      for (const other of parties) {
        const td = el("td");
        td.dataset.row = party.id;
        td.dataset.col = other.id;
        const pair = lookup.get(`${party.id}-${other.id}`);
        if (party.id === other.id) {
          td.className = "self";
        } else if (pair && pair.agreement !== null) {
          td.append(el("a", { href: `/pair/${party.id}/${other.id}/` }, Math.round(pair.agreement * 100)));
          const rgb = scale(pair.agreement);
          td.style.background = `rgb(${rgb.join(", ")})`;
          td.style.color = cellInk(rgb);
          td.title = t("{a} and {b}: {share} of {count} shared motions", {
            a: party.abbreviation, b: other.abbreviation, share: pct(pair.agreement, 1), count: number(pair.shared_motions),
          });
        } else {
          td.className = "none";
          td.textContent = "–";
          td.title = t("Not compared: no shared motions, or the same party under a new name");
        }
        row.append(td);
      }
      rows.push(row);
    }
    table.replaceChildren(...rows);

    // Focus a party: its row and column stay bright.
    const cells = [...table.querySelectorAll("td, th[data-row], th[data-col]")];
    const applyFocus = (partyId) => {
      table.classList.toggle("focusing", Boolean(partyId));
      cells.forEach((cell) => {
        const on = partyId && (Number(cell.dataset.row) === partyId || Number(cell.dataset.col) === partyId);
        cell.classList.toggle("in-focus", Boolean(on));
      });
    };
    const chip = document.getElementById("matrix-focus");
    chip.querySelector("button").addEventListener("click", () => setFocus(null));
    const abbreviations = new Map(parties.map((p) => [p.id, p.abbreviation]));
    onFocus((partyId) => {
      applyFocus(partyId);
      chip.hidden = !partyId;
      chip.querySelector("strong").textContent = abbreviations.get(partyId) || "";
    });
  }

  // ---------- 04: every party, closest and furthest ----------
  function closestAndFurthest(partyId, matrix, lookup) {
    const scored = matrix.parties
      .filter((other) => other.id !== partyId)
      .map((other) => ({ other, pair: lookup.get(`${partyId}-${other.id}`) }))
      .filter(({ pair }) => pair && pair.agreement !== null)
      .sort((a, b) => b.pair.agreement - a.pair.agreement);
    return { closest: scored[0] || null, furthest: scored.at(-1) || null };
  }

  function renderPartyIndex(parties, matrix, lookup) {
    const grid = document.getElementById("party-grid");
    const buttons = [...document.querySelectorAll("#party-sort [data-sort]")];
    const pc1 = (p) => (p.party_scores || []).find((s) => Number(s.component) === 1)?.score ?? -Infinity;
    const entries = parties.map((party) => {
      const { closest, furthest } = matrix ? closestAndFurthest(party.id, matrix, lookup) : {};
      const line = (label, entry, kind) => {
        const track = el("span", { className: "track" }, el("span"));
        track.firstChild.style.width = entry ? cssPct(entry.pair.agreement) : "0";
        return el("div", { className: `rel ${kind}` },
          el("span", { className: "k" }, label),
          el("span", { className: "v", title: entry?.other.abbreviation || "" },
            entry ? partyLogo(entry.other, { size: "sm" }) : null,
            el("span", {}, entry ? entry.other.abbreviation : "–")),
          el("span", { className: "p" }, entry ? pct(entry.pair.agreement) : ""),
          el("span", { className: "k" }),
          track);
      };
      const node = el(
        "a", { className: "entry", href: `/party/${party.id}/` },
        el("div", { className: "head" },
          partyLogo(party, { size: "md" }),
          el("span", { className: "abbr" }, party.abbreviation)),
        el("div", { className: "name" }, party.name !== party.abbreviation ? party.name : ""),
        line(t("Most with"), closest, "most"),
        line(t("Least with"), furthest, "least"),
        el("span", { className: "go" },
          el("span", {}, t("Open party page")),
          roundArrow("arrow")),
      );
      return { party, node, agreement: closest?.pair.agreement ?? -1 };
    });
    const order = {
      name: (a, b) => a.party.abbreviation.localeCompare(b.party.abbreviation),
      pc1: (a, b) => pc1(a.party) - pc1(b.party),
      agreement: (a, b) => b.agreement - a.agreement,
    };
    const draw = (key) => {
      buttons.forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.sort === key)));
      grid.replaceChildren(...[...entries].sort(order[key]).map((e) => e.node));
    };
    buttons.forEach((button) => button.addEventListener("click", () => draw(button.dataset.sort)));
    draw("name");
  }

  const chaptersLoaded = (async () => {
    const [matrix, parties] = await Promise.all([requests.matrix, requests.parties]);
    const names = new Map(parties.map((p) => [p.id, p.name]));
    const lookup = new Map((matrix?.agreements || []).map((a) => [`${a.party}-${a.other_party}`, a]));
    if (matrix) {
      renderMatrix(matrix, lookup, names);
    } else {
      document.getElementById("matrix").replaceChildren(
        el("tr", {}, el("td", { className: "placeholder" }, t("No agreement matrix yet. Run the analysis first.")))
      );
    }
    renderPartyIndex(parties, matrix, lookup);
  })().catch((error) => {
    document.getElementById("matrix").replaceChildren(
      el("tr", {}, el("td", { className: "placeholder" }, t("Could not load agreement: {error}", { error: error.message })))
    );
  });


  return { renderAxes, chaptersLoaded };
}
