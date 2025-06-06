# Generated by Django 5.2.1 on 2025-06-03 11:13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shift_management', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='shift',
            name='deletion_reason',
            field=models.CharField(blank=True, choices=[('public_holiday', '公休'), ('paid_leave', '有給休暇'), ('paid_leave_am', '有給休暇(午前)'), ('paid_leave_pm', '有給休暇(午後)'), ('absenteeism', '欠勤'), ('other', 'その他')], max_length=50, null=True, verbose_name='削除事由'),
        ),
        migrations.AddField(
            model_name='shift',
            name='is_deleted_with_reason',
            field=models.BooleanField(default=False, verbose_name='事由付き削除フラグ'),
        ),
    ]
