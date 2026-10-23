export function createHomeState() {
  // ---------- Shared state ----------
  // One request each, shared by every section.
  const requests = {
    parties: fetchJson("/api/v1/parties/?limit=500").then(results),
    analysis: fetchJson("/api/v1/analysis/?ordering=-created_at&limit=1").then((p) => results(p)[0] || null),
    matrix: fetchJson("/api/v1/agreement/?limit=1").then((p) => results(p)[0] || null),
  };
  // The highlighted party is kept in the URL (?party=<id>), so a view can
  // be shared and survives a reload.
  const focusListeners = [];
  let focusedParty = Number(new URLSearchParams(location.search).get("party")) || null;
  function onFocus(listener) {
    focusListeners.push(listener);
    if (focusedParty) listener(focusedParty);
  }
  function setFocus(partyId) {
    focusedParty = partyId || null;
    document.getElementById("focus").value = focusedParty ?? "";
    const url = new URL(location.href);
    if (focusedParty) url.searchParams.set("party", focusedParty);
    else url.searchParams.delete("party");
    history.replaceState(null, "", url);
    focusListeners.forEach((listener) => listener(focusedParty));
  }
  const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;

  // ---------- Key figures ----------
  statusRequest.then((status) => {
    document.getElementById("stat-motions").textContent = number(status.motions_with_votes);
    const period = document.getElementById("stat-period");
    if (status.earliest_vote_date && status.latest_vote_date) {
      period.textContent = `${formatDate(status.earliest_vote_date)} – ${formatDate(status.latest_vote_date)}`;
    }
  }).catch(() => {});


  return { requests, onFocus, setFocus, reducedMotion, get focusedParty() { return focusedParty; } };
}
