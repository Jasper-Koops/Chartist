import pandas as pd
from pca import pca
from analyzer.utils import generate_dataframe
from scraper.models import Party
from analyzer.models import PCAAnalysis, PCAComponentPartyScore, PCAItemLoading


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


def prepare_df() -> tuple[pd.DataFrame, list[str]]:
    """
    Prepare the DataFrame for PCA analysis.

    This function generates a DataFrame, uses the motion IDS as row indices,
    and transposes the data for PCA analysis.

    The resulting DataFrame has parties as rows and parliamentary items.ids columns.

    Returns:
        tuple: A tuple containing:
            - prepared_df (pd.DataFrame): The transposed DataFrame ready for PCA.
            - labels (list): The column labels of the original DataFrame.
    """
    df = generate_dataframe()
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
    prepared_df, labels = prepare_df()
    model = generate_pca_object(prepared_df, labels, n_components=n_components)
    components = model.results.get("PC")

    analysis: PCAAnalysis = PCAAnalysis.objects.create()
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
