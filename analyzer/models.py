from django.db import models
from scraper.models import Party


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

    def __str__(self) -> str:
        return f"{self.party} PC: {self.component}- score: {self.score}"
