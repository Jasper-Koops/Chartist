from bisect import bisect_left
from typing import NamedTuple

import numpy as np
import pandas as pd
from pca import pca
from analyzer.agreement import run_agreement_analysis
from analyzer.votes import item_vote_dates, party_votes
from analyzer.utils import (
    PCA_FIT_COVERAGE,
    PCA_MIN_PROJECTED_VOTES,
    AnalysisLogger,
    generate_dataframe,
    log_to_stdout,
)
from scraper.models import Party, PartyVote
from analyzer.models import (
    PCAAnalysis,
    PCAComponent,
    PCAComponentPartyScore,
    PCAItemLoading,
)
from datetime import date
from typing import TextIO
from django.db.transaction import atomic
from django.core.management.base import OutputWrapper
import logging

logger = logging.getLogger(__name__)


def calculate_party_participation_rate() -> None:
    """
    Calculate and update the participation rate for each party.

    The rate is measured from each party's own start: the share of voted
    items, dated on or after the party's first vote, on which the party has
    a vote. A party that formed during the period (e.g. a split) is
    therefore not penalised for items from before it existed.

    Only items with at least one vote count; items whose votes are not
    published yet are ignored. Parties without votes get 0%.

    Inherited votes count (see `party_votes`): a party that continues another
    party is measured from its predecessor's start.
    """
    # By voting date: the start is when the party first voted, not when a
    # record was last modified.
    item_dates: dict[int, date] = item_vote_dates()
    # Distinct on the item, not the date: many items share a date.
    voted_item_dates: list[date] = sorted(
        item_dates[item_id]
        for item_id in PartyVote.objects.values_list(
            "parliamentary_item_id", flat=True
        ).distinct()
    )
    votes = party_votes()
    parties_to_update = []
    for party in Party.objects.all():
        own_votes = votes.get(party.id, {})
        votes_cast = len(own_votes)
        if not votes_cast:
            participation_rate: float = 0.0
        else:
            first_vote = min(item_dates[item_id] for item_id in own_votes)
            eligible = len(voted_item_dates) - bisect_left(
                voted_item_dates, first_vote
            )
            participation_rate = (votes_cast / eligible) * 100
        party.participation_rate = participation_rate
        parties_to_update.append(party)

    Party.objects.bulk_update(parties_to_update, ["participation_rate"])


def generate_pca_object(
    prepared_df: pd.DataFrame, labels: list[str], n_components: int = 5
) -> pca:
    """
    Generate a PCA object and fit it to the provided data.

    A covariance PCA: each motion is centered but not standardized. Every
    motion is in the same unit (-1, 0, 1), so there is no difference in
    scale to correct for, and standardizing would give a near-unanimous
    motion (one party against the rest) as much weight as a close vote.
    Centered, a divided vote weighs more. This is the usual choice for
    votes; methods made for roll calls, like Optimal Classification and
    NOMINATE, do not standardize votes either.

    Args:
        prepared_df (pd.DataFrame): The prepared DataFrame containing the data for PCA.
        labels (list): The row labels for the PCA model.
        n_components (int, optional): The number of principal components to compute. Defaults to 5.

    Returns:
        pca: The PCA model fitted to the data.
    """
    model = pca(n_components=n_components, normalize=False)
    model.fit_transform(prepared_df, row_labels=labels)
    return model


class PreparedVotes(NamedTuple):
    """
    The vote matrices for the PCA (parties as rows, motion ids as columns;
    1 for, -1 against, 0 did not take part).

    Attributes:
        fit (pd.DataFrame): Parties the axes are fitted on, with a vote on
            every column.
        labels (list[str]): The row labels of `fit`.
        projected (pd.DataFrame): Parties placed on those axes afterwards,
            over the same columns; NaN where the party has no vote.
    """

    fit: pd.DataFrame
    labels: list[str]
    projected: pd.DataFrame


def prepare_df(log: AnalysisLogger) -> PreparedVotes:
    """
    Prepare the vote matrices for the PCA.

    PCA needs a vote from every party on every motion, but a party that
    started later (e.g. a member who left their party group) has no votes
    before its start. Dropping those motions for everyone would limit the
    map to the period since the newest party started; filling them in would
    invent votes. Instead, as is standard for PCA ("supplementary
    individuals"):

    - the axes are fitted on the parties with a vote on nearly every motion
      (`PCA_FIT_COVERAGE`), over the motions all of them voted on;
    - the other parties are placed on those axes afterwards, using only the
      motions they voted on (see `project_parties`). Parties with fewer than
      `PCA_MIN_PROJECTED_VOTES` such votes are left out.

    Args:
      log (AnalysisLogger): Logger instance for tracking dataframe generation
        and party exclusions.

    Returns:
        PreparedVotes: The matrix to fit on, its row labels, and the matrix
            of the parties to project.

    Raises:
        ValueError: If no motion has a vote from every fitted party.
    """
    df = generate_dataframe(log=log)
    votes = df.set_index("Motion ID").transpose().astype(float)
    votes.columns = [int(item_id) for item_id in votes.columns]

    coverage = votes.notna().mean(axis=1)
    fit_parties = coverage[coverage >= PCA_FIT_COVERAGE].index
    fit = votes.loc[fit_parties].dropna(axis=1)
    log.info(
        f"Fitting on {len(fit.index)} parties; removed "
        f"{votes.shape[1] - fit.shape[1]} parliamentary items with missing "
        "votes among them.",
        extra={"parties": list(fit.index), "items": fit.shape[1]},
    )
    if fit.empty:
        raise ValueError(
            "No parliamentary items available for PCA analysis. "
            "Run import_data first."
        )

    projected = votes.drop(index=fit_parties)[fit.columns]
    counts = projected.notna().sum(axis=1)
    too_few = list(counts[counts < PCA_MIN_PROJECTED_VOTES].index)
    if too_few:
        log.info(
            f"Left out of the PCA, too few votes: {', '.join(too_few)}.",
            extra={"parties": too_few},
        )
    projected = projected.drop(index=too_few)
    return PreparedVotes(fit, list(fit.index), projected)


def project_parties(model: pca, projected: pd.DataFrame) -> pd.DataFrame:
    """
    Place parties on fitted PCA axes using only the motions they voted on.

    Least-squares projection onto the axes over the observed votes
    ("projection to the model plane"). Nothing is filled in, so a party
    with fewer votes is not pulled towards the centre. For a party with
    every vote this equals the ordinary PCA score.

    Args:
        model (pca): The fitted PCA (`generate_pca_object`).
        projected (pd.DataFrame): Parties x the fitted motions, NaN where a
            party has no vote.

    Returns:
        pd.DataFrame: Scores per party (rows) and component (PC1, PC2, ...).
    """
    fitted = model.results["model"]
    columns = list(model.results["PC"].columns)
    scores = {}
    for party, row in projected.iterrows():
        voted = row.notna().to_numpy()
        axes = fitted.components_[:, voted].T
        deviation = row.to_numpy()[voted] - fitted.mean_[voted]
        scores[party] = np.linalg.lstsq(axes, deviation, rcond=None)[0]
    return pd.DataFrame.from_dict(scores, orient="index", columns=columns)


def run_pca_analysis(n_components: int = 3) -> None:
    """
    Run PCA analysis and store the results in the database.

    This function prepares the data, performs PCA, and saves the component-party scores
    in the database. Parties that started later are projected onto the axes
    (see `prepare_df`). Each principal component's scores are linked to the
    corresponding party and analysis instance.

    The loadings for each parliamentary item for each component are also stored
     in the database as PCAItemLoading instances.

    Args:
        n_components (int, optional): The number of principal components to
        compute. Defaults to 3.
    """
    with atomic():
        analysis: PCAAnalysis = PCAAnalysis.objects.create()
        log = AnalysisLogger(logger, {"analysis_id": analysis.id})

        prepared = prepare_df(log=log)
        model = generate_pca_object(
            prepared.fit, prepared.labels, n_components=n_components
        )

        # Create PCAComponent records with explained variance
        explained_variances = model.results.get("variance_ratio")
        pca_components: dict[str, PCAComponent] = {}
        for i, variance in enumerate(explained_variances, start=1):
            pca_component = PCAComponent.objects.create(
                analysis=analysis,
                number=i,
                explained_variance=variance,
            )
            pca_components[f"PC{i}"] = pca_component

        analysis.total_explained_variance = sum(explained_variances)
        analysis.save(update_fields=["total_explained_variance"])

        # Save item loadings
        loadings = model.results.get("loadings")
        item_loadings: list[PCAItemLoading] = []
        for index, row in loadings.transpose().iterrows():
            for pc_label in row.index:
                item_loadings.append(
                    PCAItemLoading(
                        component=pca_components[pc_label],
                        parliamentary_item_id=int(index),
                        loading=row[pc_label],
                    )
                )

        if item_loadings:
            PCAItemLoading.objects.bulk_create(item_loadings)

        # Save party scores: fitted and projected parties alike.
        components = pd.concat(
            [
                model.results.get("PC"),
                project_parties(model, prepared.projected),
            ]
        )
        dict_version = components.to_dict()
        party_lookup: dict[str, Party] = {
            party.abbreviation: party for party in Party.objects.all()
        }
        party_scores_to_create: list[PCAComponentPartyScore] = []
        for pc_label, party_scores in dict_version.items():
            for party_name, score in party_scores.items():
                party_scores_to_create.append(
                    PCAComponentPartyScore(
                        component=pca_components[pc_label],
                        party=party_lookup[party_name],
                        score=score,
                    )
                )

        if party_scores_to_create:
            PCAComponentPartyScore.objects.bulk_create(party_scores_to_create)


def run_full_analysis(
    n_components: int, stdout: TextIO | OutputWrapper | None = None
) -> None:
    """
    Run the full analysis pipeline.

    This function calculates party participation rates, performs PCA analysis
    and calculates the party agreement matrix.
    """
    log_to_stdout(msg="Calculating party participation rates...", stdout=stdout)
    calculate_party_participation_rate()
    log_to_stdout(msg="Done.\nRunning PCA analysis...", stdout=stdout)
    run_pca_analysis(n_components=n_components)
    log_to_stdout(
        msg="PCA analysis completed.\nCalculating agreement matrix...",
        stdout=stdout,
    )
    run_agreement_analysis()
    log_to_stdout(msg="Agreement matrix completed.", stdout=stdout)
