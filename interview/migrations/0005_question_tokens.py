# Generated migration for Question.tokens field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('interview', '0004_auto_20251115_0910'),
    ]

    operations = [
        migrations.AddField(
            model_name='question',
            name='tokens',
            field=models.JSONField(default=list),
        ),
    ]
