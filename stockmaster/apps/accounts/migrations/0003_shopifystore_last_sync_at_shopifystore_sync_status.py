# Generated by Django 4.2.8 on 2025-04-10 20:31

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_shopifystore_setup_complete'),
    ]

    operations = [
        migrations.AddField(
            model_name='shopifystore',
            name='last_sync_at',
            field=models.DateTimeField(blank=True, help_text='When the store was last synced', null=True),
        ),
        migrations.AddField(
            model_name='shopifystore',
            name='sync_status',
            field=models.CharField(choices=[('pending', 'Pending'), ('in_progress', 'In Progress'), ('success', 'Success'), ('failed', 'Failed')], default='pending', help_text='Current sync status', max_length=50),
        ),
    ]
