from django.db import models
from scraper.models import Party, ParliamentaryItem


class PCAAnalysis(models.Model):
    """
    Model to store PCA analysis results
    """

    created_at = models.DateTimeField(auto_now_add=True)
    total_explained_variance = models.FloatField(default=0.0)

    class Meta:
        verbose_name = "PCA Analysis"
        verbose_name_plural = "PCA Analyses"

    def __str__(self) -> str:
        return f"PCA Analysis at {self.created_at}"


class PCAComponent(models.Model):
    """
    Model to store a principal component and its explained variance.
    """

    analysis = models.ForeignKey(
        PCAAnalysis, on_delete=models.CASCADE, related_name="components"
    )
    number = models.IntegerField()
    explained_variance = models.FloatField()

    class Meta:
        verbose_name = "PCA Component"
        verbose_name_plural = "PCA Components"
        unique_together = ("analysis", "number")

    def __str__(self) -> str:
        return f"PC{self.number} ({self.explained_variance:.1%})"


class PCAComponentPartyScore(models.Model):
    """
    Model to store PCA scores for each party
    """

    component = models.ForeignKey(
        PCAComponent, on_delete=models.CASCADE, related_name="party_scores"
    )
    party = models.ForeignKey(
        Party, on_delete=models.CASCADE, related_name="pca_scores"
    )
    score = models.FloatField()

    class Meta:
        verbose_name = "PCA Component Party Score"
        verbose_name_plural = "PCA Component Party Scores"
        unique_together = ("component", "party")

    def __str__(self) -> str:
        return f"{self.party} PC{self.component.number} - score: {self.score}"


class PCAItemLoading(models.Model):
    """
    Model to store PCA loadings for each parliamentary item
    """

    component = models.ForeignKey(
        PCAComponent, on_delete=models.CASCADE, related_name="item_loadings"
    )
    parliamentary_item = models.ForeignKey(
        ParliamentaryItem, on_delete=models.CASCADE, related_name="pca_loadings"
    )
    loading = models.FloatField()

    class Meta:
        verbose_name = "PCA Item Loading"
        verbose_name_plural = "PCA Item Loadings"
        unique_together = ("component", "parliamentary_item")

    def __str__(self) -> str:
        return f"Item ID: {self.parliamentary_item_id} PC{self.component.number} - loading: {self.loading}"


class AgreementMatrix(models.Model):
    """
    Pairwise voting agreement between parties, stored per analysis run.
    """

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Agreement Matrix"
        verbose_name_plural = "Agreement Matrices"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Agreement Matrix at {self.created_at}"


class PartyAgreement(models.Model):
    """
    Agreement of one party with another party within a matrix.

    Stored for both orderings of a pair, so all agreements of a single party
    can be selected with one filter.
    """

    matrix = models.ForeignKey(
        AgreementMatrix, on_delete=models.CASCADE, related_name="agreements"
    )
    party = models.ForeignKey(
        Party, on_delete=models.CASCADE, related_name="agreements"
    )
    other_party = models.ForeignKey(
        Party, on_delete=models.CASCADE, related_name="+"
    )
    agreement = models.FloatField(
        null=True,
        blank=True,
        help_text="Share (0-1) of shared motions on which both parties voted "
        "the same. Empty when the parties share no motions.",
    )
    shared_motions = models.IntegerField(
        help_text="Number of motions on which both parties voted for or "
        "against."
    )

    class Meta:
        verbose_name = "Party Agreement"
        verbose_name_plural = "Party Agreements"
        unique_together = ("matrix", "party", "other_party")

    def __str__(self) -> str:
        return f"{self.party} - {self.other_party}: {self.agreement}"
