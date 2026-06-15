from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("analyzer", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="pcaanalysis",
            name="total_explained_variance",
            field=models.FloatField(default=0.0),
        ),
    ]
