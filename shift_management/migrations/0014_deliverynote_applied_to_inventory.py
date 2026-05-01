from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shift_management', '0013_invoice_deliverynote_invoiceitem_deliverynoteitem'),
    ]

    operations = [
        migrations.AddField(
            model_name='deliverynote',
            name='applied_to_inventory',
            field=models.BooleanField(default=False, verbose_name='在庫反映済み'),
        ),
    ]

