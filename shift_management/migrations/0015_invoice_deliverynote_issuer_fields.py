from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shift_management', '0014_deliverynote_applied_to_inventory'),
    ]

    operations = [
        migrations.AddField(
            model_name='invoice',
            name='issuer_name',
            field=models.CharField(blank=True, max_length=200, null=True, verbose_name='発行元名（上書き）'),
        ),
        migrations.AddField(
            model_name='invoice',
            name='issuer_address',
            field=models.TextField(blank=True, null=True, verbose_name='発行元住所（上書き）'),
        ),
        migrations.AddField(
            model_name='invoice',
            name='issuer_phone',
            field=models.CharField(blank=True, max_length=50, null=True, verbose_name='発行元電話（上書き）'),
        ),
        migrations.AddField(
            model_name='invoice',
            name='issuer_email',
            field=models.EmailField(blank=True, max_length=254, null=True, verbose_name='発行元メール（上書き）'),
        ),
        migrations.AddField(
            model_name='deliverynote',
            name='issuer_name',
            field=models.CharField(blank=True, max_length=200, null=True, verbose_name='発行元名（上書き）'),
        ),
        migrations.AddField(
            model_name='deliverynote',
            name='issuer_address',
            field=models.TextField(blank=True, null=True, verbose_name='発行元住所（上書き）'),
        ),
        migrations.AddField(
            model_name='deliverynote',
            name='issuer_phone',
            field=models.CharField(blank=True, max_length=50, null=True, verbose_name='発行元電話（上書き）'),
        ),
        migrations.AddField(
            model_name='deliverynote',
            name='issuer_email',
            field=models.EmailField(blank=True, max_length=254, null=True, verbose_name='発行元メール（上書き）'),
        ),
    ]

