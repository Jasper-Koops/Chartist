export function toPoints(parties) {
  return parties
    .map((party) => {
      const scores = Object.fromEntries(
        (party.party_scores || []).map((s) => [Number(s.component), Number(s.score)])
      );
      if (!Number.isFinite(scores[1]) || !Number.isFinite(scores[2])) return null;
      return {
        x: scores[1],
        y: scores[2],
        z: Number.isFinite(scores[3]) ? scores[3] : null,
        label: party.abbreviation || party.name,
        abbreviation: party.abbreviation || party.name,
        name: party.name,
        partyId: party.id,
        logo_url: party.logo_url,
      };
    })
    .filter(Boolean);
}

// Color by position on the main axis (PC1): terracotta, through warm
// grey, to deep blue (safe for common color-vision types; >= 3.5:1 on
// the paper), the same in the map and the axis lines.
export function mainAxisColor(x, points) {
  const xs = points.map((p) => p.x);
  const [lo, hi] = [Math.min(...xs), Math.max(...xs)];
  const mix = (a, b, t) => {
    const ca = a.match(/\w\w/g).map((h) => parseInt(h, 16));
    const cb = b.match(/\w\w/g).map((h) => parseInt(h, 16));
    return `rgb(${ca.map((c, i) => Math.round(c + (cb[i] - c) * t)).join(", ")})`;
  };
  const t = (x - lo) / (hi - lo || 1);
  const [low, middle, high] = [css("--data-lo"), css("--data-mid"), css("--data-hi")];
  return t < 0.5 ? mix(low, middle, t * 2) : mix(middle, high, t * 2 - 1);
}


export function displayedVariance(variance, flat) {
  return (flat ? [1, 2] : [1, 2, 3]).reduce(
    (sum, number) => sum + (Number(variance[number]) || 0), 0);
}
