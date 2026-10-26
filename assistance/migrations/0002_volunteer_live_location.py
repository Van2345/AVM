from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("assistance", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="volunteer",
            name="location_accuracy",
            field=models.DecimalField(
                blank=True, decimal_places=1, max_digits=8, null=True
            ),
        ),
        migrations.AddField(
            model_name="volunteer",
            name="location_updated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
