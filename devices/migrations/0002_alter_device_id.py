# Generated by Django 5.2 on 2025-04-22 14:55

import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('devices', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='device',
            name='id',
            field=models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False),
        ),
    ]
