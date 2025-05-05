from django.db import migrations


def create_default_ranks(apps, schema_editor):
    # Get the model
    RankTier = apps.get_model('ranks', 'RankTier')

    # Create balanced rank tiers based on the enhanced scoring algorithm
    # The new system awards points from multiple sources:
    # - Base points (up to 50 from average score)
    # - Duration bonus (up to 20 points)
    # - Streak bonus (up to 15 points)
    # - Good posture percentage (up to 15 points)
    # This means a single good session could award around 40-70 points

    default_tiers = [
        {'name': 'NONE', 'minimum_score': 0},  # Starting tier
        {'name': 'BRONZE', 'minimum_score': 100},  # Achievable in ~2 good sessions
        {'name': 'SILVER', 'minimum_score': 300},  # Achievable in ~5-6 good sessions
        {'name': 'GOLD', 'minimum_score': 600},  # Achievable in ~10-12 good sessions
        {'name': 'PLATINUM', 'minimum_score': 1200},  # Achievable in ~20-25 good sessions
        {'name': 'DIAMOND', 'minimum_score': 2400},  # Achievable in ~40-50 good sessions
    ]

    for tier in default_tiers:
        RankTier.objects.create(**tier)


def delete_default_ranks(apps, schema_editor):
    # Get the model
    RankTier = apps.get_model('ranks', 'RankTier')

    # Delete all tiers
    RankTier.objects.filter(
        name__in=['NONE', 'BRONZE', 'SILVER', 'GOLD', 'PLATINUM', 'DIAMOND']
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('ranks', '0001_initial'),  # Make sure to replace with your actual initial migration
    ]

    operations = [
        migrations.RunPython(create_default_ranks, delete_default_ranks),
    ]