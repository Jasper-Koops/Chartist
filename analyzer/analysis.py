import pandas as pd
from pca import pca
from django.db.models import QuerySet
from analyzer.utils import generate_dataframe, log_to_stdout, AnalysisLogger
from scraper.models import Party, PartyVote, ParliamentaryItem
from analyzer.models import PCAAnalysis, PCAComponentPartyScore, PCAItemLoading
from typing import TextIO
from django.db.transaction import atomic
from django.core.management.base import OutputWrapper
import logging

logger = logging.getLogger(__name__)


def calculate_party_participation_rate() -> None:
    """
    Calculate and update the participation rate for each party.

    This function iterates through all parties in the database, calculates their
    participation rate in parliamentary votes, and updates the corresponding
    field in the Party model.
    """
    parties: QuerySet[Party] = Party.objects.all()
    total_items: int = ParliamentaryItem.objects.count()
    parties_to_update = []
    for party in parties:
        votes_cast: int = PartyVote.objects.filter(party=party).count()
        if total_items > 0:
            participation_rate: float = (votes_cast / total_items) * 100
        else:
            participation_rate = 0.0
        party.participation_rate = participation_rate
        parties_to_update.append(party)

    Party.objects.bulk_update(parties_to_update, ["participation_rate"])


# FIXME - test
def generate_pca_object(
    prepared_df: pd.DataFrame, labels: list[str], n_components: int = 5
) -> pca:
    """
    Generate a PCA object and fit it to the provided data.

    Args:
        prepared_df (pd.DataFrame): The prepared DataFrame containing the data for PCA.
        labels (list): The row labels for the PCA model.
        n_components (int, optional): The number of principal components to compute. Defaults to 5.

    Returns:
        pca: The PCA model fitted to the data.
    """
    model = pca(n_components=n_components, normalize=True)
    model.fit_transform(prepared_df, row_labels=labels)
    return model


def prepare_df(log: AnalysisLogger) -> tuple[pd.DataFrame, list[str]]:
    """
    Prepare the DataFrame for PCA analysis.

    This function generates a DataFrame, uses the motion IDs as row indices,
    and transposes the data for PCA analysis.

    The resulting DataFrame has parties as rows and parliamentary items IDs as
    columns.

    Items on which not all parties have voted (i.e., rows with NaN values) are
    removed.

    Args:
      log (AnalysisLogger): Logger instance for tracking dataframe generation
        and party exclusions.

    Returns:
        tuple: A tuple containing:
            - prepared_df (pd.DataFrame): The transposed DataFrame ready for PCA.
            - labels (list): The column labels of the original DataFrame.
    """
    df = generate_dataframe(log=log)
    # Remove all rows with NaN values
    before = len(df)
    df = df.dropna()
    removed = before - len(df)
    # Check how many items were removed
    log.info(
        f"Removed {removed} parliamentary items with missing votes.",
        extra={"removed": removed, "before": before, "after": len(df)},
    )
    labels = df.columns[1:]
    item_ids = df["Motion ID"]
    prepared_df = pd.DataFrame(data=df.iloc[:, 1:], columns=labels)
    prepared_df = prepared_df.rename(index=item_ids)
    prepared_df = prepared_df.transpose()

    return prepared_df, labels


def run_pca_analysis(n_components: int = 3) -> None:
    """
    Run PCA analysis and store the results in the database.

    This function prepares the data, performs PCA, and saves the component-party scores
    in the database. Each principal component's scores are linked to the
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

        prepared_df, labels = prepare_df(log=log)
        model = generate_pca_object(
            prepared_df, labels, n_components=n_components
        )
        components = model.results.get("PC")

        loadings = model.results.get("loadings")
        item_loadings: list[PCAItemLoading] = []
        for index, row in loadings.transpose().iterrows():
            for pc_component_score in row.index:
                item_loadings.append(
                    PCAItemLoading(
                        analysis=analysis,
                        parliamentary_item_id=int(index),
                        component=int(pc_component_score.strip("PC")),
                        loading=row[pc_component_score],
                    )
                )

        if item_loadings:
            PCAItemLoading.objects.bulk_create(item_loadings)

        dict_version = components.to_dict()
        for component, party_scores in dict_version.items():
            for party_name, score in party_scores.items():
                party = Party.objects.get(abbreviation=party_name)
                PCAComponentPartyScore.objects.create(
                    analysis=analysis,
                    party=party,
                    component=int(component.removeprefix("PC")),
                    score=score,
                )


# FIXME - test
def run_full_analysis(
    n_components: int, stdout: TextIO | OutputWrapper | None = None
) -> None:
    """
    Run the full analysis pipeline.

    This function calculates party participation rates and performs PCA analysis.
    """
    log_to_stdout(msg="Calculating party participation rates...", stdout=stdout)
    calculate_party_participation_rate()
    log_to_stdout(msg="Done.\nRunning PCA analysis...", stdout=stdout)
    run_pca_analysis(n_components=n_components)
    log_to_stdout(msg="PCA analysis completed.", stdout=stdout)
