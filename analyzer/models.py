from django.db import models
from scraper.models import Party, ParliamentaryItem


class PCAAnalysis(models.Model):
    """
    Model to store PCA analysis results
    """

    created_at = models.DateTimeField(auto_now_add=True)

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

    def __str__(self) -> str:
        return f"Item ID: {self.parliamentary_item_id} PC{self.component.number} - loading: {self.loading}"
