# Generated by Django 4.2.8 on 2025-04-08 14:26

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('inventory', '0001_initial'),
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='StockPrediction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('predicted_out_of_stock_date', models.DateTimeField(blank=True, help_text='Predicted date when the product will be out of stock', null=True)),
                ('confidence_score', models.FloatField(default=0.0, help_text='Confidence score for the prediction (0-1)')),
                ('days_of_data', models.IntegerField(default=0, help_text='Number of days of data used for prediction')),
                ('average_sales_per_day', models.FloatField(default=0.0, help_text='Average sales per day based on historical data')),
                ('current_stock_level', models.IntegerField(default=0, help_text='Current stock level when the prediction was made')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='stock_predictions', to='inventory.product')),
            ],
            options={
                'verbose_name': 'Stock Prediction',
                'verbose_name_plural': 'Stock Predictions',
                'ordering': ['-created_at'],
                'indexes': [models.Index(fields=['product', 'created_at'], name='analytics_s_product_43ab33_idx'), models.Index(fields=['predicted_out_of_stock_date'], name='analytics_s_predict_f63ba0_idx')],
            },
        ),
        migrations.CreateModel(
            name='ProductAnalytics',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('out_of_stock_count', models.IntegerField(default=0, help_text='Number of times the product has been out of stock')),
                ('total_days_out_of_stock', models.IntegerField(default=0, help_text='Total days the product has been out of stock')),
                ('last_out_of_stock_at', models.DateTimeField(blank=True, help_text='When the product was last out of stock', null=True)),
                ('times_hidden', models.IntegerField(default=0, help_text='Number of times the product has been hidden')),
                ('total_days_hidden', models.IntegerField(default=0, help_text='Total days the product has been hidden')),
                ('last_hidden_at', models.DateTimeField(blank=True, help_text='When the product was last hidden', null=True)),
                ('rule_applications_count', models.IntegerField(default=0, help_text='Number of rule applications to this product')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('product', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='analytics', to='inventory.product')),
            ],
            options={
                'verbose_name': 'Product Analytics',
                'verbose_name_plural': 'Product Analytics',
                'indexes': [models.Index(fields=['out_of_stock_count'], name='analytics_p_out_of__bbe331_idx'), models.Index(fields=['times_hidden'], name='analytics_p_times_h_87c6d8_idx')],
            },
        ),
        migrations.CreateModel(
            name='DailySummary',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(help_text='The date of the summary')),
                ('total_products', models.IntegerField(default=0, help_text='Total number of products')),
                ('out_of_stock_products', models.IntegerField(default=0, help_text='Number of out-of-stock products')),
                ('low_stock_products', models.IntegerField(default=0, help_text='Number of low-stock products')),
                ('hidden_products', models.IntegerField(default=0, help_text='Number of hidden products')),
                ('rules_applied', models.IntegerField(default=0, help_text='Number of rules applied')),
                ('notifications_sent', models.IntegerField(default=0, help_text='Number of notifications sent')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('store', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='daily_summaries', to='accounts.shopifystore')),
            ],
            options={
                'verbose_name': 'Daily Summary',
                'verbose_name_plural': 'Daily Summaries',
                'ordering': ['-date'],
                'indexes': [models.Index(fields=['store', 'date'], name='analytics_d_store_i_cc897d_idx')],
                'unique_together': {('store', 'date')},
            },
        ),
    ]
