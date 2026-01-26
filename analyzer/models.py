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


class PCAComponentPartyScore(models.Model):
    """
    Model to store PCA scores for each party
    """

    analysis = models.ForeignKey(
        PCAAnalysis, on_delete=models.CASCADE, related_name="party_scores"
    )
    party = models.ForeignKey(
        Party, on_delete=models.CASCADE, related_name="pca_scores"
    )
    component = models.IntegerField()
    score = models.FloatField()

    class Meta:
        verbose_name = "PCA Component Party Score"
        verbose_name_plural = "PCA Component Party Scores"

    def __str__(self) -> str:
        return f"{self.party} PC: {self.component}- score: {self.score}"


class PCAItemLoading(models.Model):
    """
    Model to store PCA loadings for each parliamentary item
    """

    analysis = models.ForeignKey(
        PCAAnalysis, on_delete=models.CASCADE, related_name="item_loadings"
    )
    parliamentary_item = models.ForeignKey(
        ParliamentaryItem, on_delete=models.CASCADE, related_name="pca_loadings"
    )
    component = models.IntegerField()
    loading = models.FloatField()

    class Meta:
        verbose_name = "PCA Item Loading"
        verbose_name_plural = "PCA Item Loadings"

    def __str__(self) -> str:
        return f"Item ID: {self.parliamentary_item_id} PC: {self.component}- loading: {self.loading}"
