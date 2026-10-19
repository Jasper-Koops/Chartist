"""
Compare PCA settings: how much variance the first components explain, and
whether the party positions stay the same.

Read-only: uses the stored votes and changes nothing. Run from the project
root with:

    python scripts/compare_pca.py

Levers compared (the current analysis is the first value of each):
- scaling: each motion standardized (pca(normalize=True)) or only centered;
- abstain: "did not take part" as 0, or as a missing vote;
- missing: drop motions on which an included party has no vote, or fill
  the missing vote with the motion's average (which adds no deviation);
- filter: all motions, or only those where at least 2 or 3 parties voted
  against the majority (near-unanimous motions say little about positions).
"""

import itertools
import logging
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Chartist.settings")

import django  # noqa: E402

django.setup()

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from pca import pca  # noqa: E402
from scipy.stats import spearmanr  # noqa: E402
from sklearn.decomposition import PCA  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402

from analyzer.utils import AnalysisLogger, generate_dataframe  # noqa: E402

logging.disable(logging.CRITICAL)  # generate_dataframe logs every missing vote


def load_votes() -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Votes as the analysis loads them: parties (rows) x motions (columns),
    1 for, -1 against, 0 did not take part, NaN no vote. Also a mask of the
    'did not take part' votes, for the variant that treats them as missing.
    """
    df = generate_dataframe(AnalysisLogger(logging.getLogger("compare"), {}))
    votes = df.set_index("Motion ID").T.astype(float)
    return votes, votes == 0


def prepare(
    votes: pd.DataFrame,
    abstain_zero: bool,
    scaling: str,
    missing: str,
    minority_min: int,
) -> tuple[np.ndarray, list[int]]:
    """The matrix to run PCA on, for one combination of settings."""
    X = votes.copy()
    if not abstain_zero:
        X = X.mask(ABSTAIN)
    if missing == "drop":
        X = X.loc[:, X.notna().all()]
    else:
        X = X.loc[:, X.notna().any()]
        X = X.fillna(X.mean())
    # Parties on the losing side of each motion, among those voting for or
    # against.
    if minority_min:
        n_for = (votes[X.columns] == 1).sum()
        n_against = (votes[X.columns] == -1).sum()
        X = X.loc[:, np.minimum(n_for, n_against) >= minority_min]
    values = X.to_numpy()
    values = values - values.mean(axis=0)
    if scaling == "standardized":
        std = values.std(axis=0)
        values = values / np.where(std == 0, 1, std)
    return values, list(X.columns)


def fit(values: np.ndarray, n: int = 3) -> tuple[np.ndarray, np.ndarray]:
    model = PCA(n_components=n).fit(values)
    return model.transform(values), np.asarray(model.explained_variance_ratio_)


def rank_agreement(
    scores: np.ndarray, base_scores: np.ndarray, component: int
) -> float:
    """Spearman correlation of the party order on a component, ignoring
    the sign (the direction of an axis is arbitrary)."""
    rho, _ = spearmanr(scores[:, component], base_scores[:, component])
    return float(abs(rho))


def prediction(coords: np.ndarray, votes: pd.DataFrame) -> tuple[float, float]:
    """
    Share of for/against votes the 2D positions predict, NOMINATE-style: per
    motion, the best straight line between the parties voting for and those
    voting against. Also the share of the minority votes predicted beyond
    'everyone votes with the majority' (APRE). Same motions for every variant:
    every motion with at least one vote on each side.
    """
    correct = total = minority_total = errors_total = 0
    for motion in votes.columns:
        column = votes[motion]
        voted = column.isin([1, -1]).to_numpy()
        y = column.to_numpy()[voted]
        if len(set(y)) < 2:
            continue
        model = LogisticRegression(C=1e4, max_iter=1000).fit(coords[voted], y)
        hits = int((model.predict(coords[voted]) == y).sum())
        correct += hits
        total += len(y)
        minority_total += min((y == 1).sum(), (y == -1).sum())
        errors_total += len(y) - hits
    return correct / total, float(
        (minority_total - errors_total) / minority_total
    )


votes, ABSTAIN = load_votes()
print(f"Parties: {len(votes)} ({', '.join(votes.index)})")
print(
    f"Motions: {votes.shape[1]}; with a missing vote: {int(votes.isna().any().sum())}; "
    f"'did not take part' votes: {int(ABSTAIN.sum().sum())}"
)

# Check: the current setup reproduces the stored analysis method.
base_values, base_motions = prepare(votes, True, "standardized", "drop", 0)
base_scores, base_ratio = fit(base_values)
reference = pca(n_components=3, normalize=True, verbose=0)
reference.fit_transform(votes[base_motions].dropna(axis=1), verbose=0)
assert np.allclose(
    base_ratio, reference.results["variance_ratio"][:3], atol=1e-4
), "baseline differs"
print(f"Check: matches pca(normalize=True): {np.round(base_ratio * 100, 2)}%\n")

rows = []
for scaling, abstain_zero, missing, minority_min in itertools.product(
    ["standardized", "centered"], [True, False], ["drop", "fill"], [0, 2, 3]
):
    values, motions = prepare(
        votes, abstain_zero, scaling, missing, minority_min
    )
    scores, ratio = fit(values)
    rows.append(
        {
            "scaling": scaling,
            "abstain": "0" if abstain_zero else "missing",
            "missing": missing,
            "minority>=": minority_min or "-",
            "motions": len(motions),
            "PC1 %": ratio[0] * 100,
            "PC2 %": ratio[1] * 100,
            "PC3 %": ratio[2] * 100,
            "PC1-3 %": ratio.sum() * 100,
            "PC1-2 %": ratio[:2].sum() * 100,
            "order PC1": rank_agreement(scores, base_scores, 0),
            "order PC2": rank_agreement(scores, base_scores, 1),
            "_coords": scores[:, :2],
        }
    )

table = pd.DataFrame(rows)
shown = table.drop(columns="_coords")
pd.set_option("display.width", 200)
print(
    shown.to_string(
        index=False,
        float_format=lambda v: f"{v:.2f}" if v < 1.0001 else f"{v:.1f}",
    )
)

# Prediction from the 2D map, for the current setup and the strongest
# variant per lever (fitting a line per motion is slow).
print("\nVotes predicted by the 2D map (same motions for every row):")
picks = [0] + list(table.sort_values("PC1-2 %", ascending=False).index[:4])
for i in dict.fromkeys(picks):
    start = time.time()
    accuracy, apre = prediction(table.loc[i, "_coords"], votes)
    label = ", ".join(
        str(table.loc[i, c])
        for c in ["scaling", "abstain", "missing", "minority>="]
    )
    print(
        f"  {label:<40} correct {accuracy * 100:.1f}%  APRE {apre * 100:.1f}%  ({time.time() - start:.0f}s)"
    )
