# Generated by Django 4.2.7 on 2025-04-10 12:41

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='shopifystore',
            name='setup_complete',
            field=models.BooleanField(default=False, help_text='Whether the store setup is complete'),
        ),
    ]
