from django.db import models
from django.contrib.auth.models import User

class Staff(models.Model):
    """スタッフ（従業員）情報モデル"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True, verbose_name="ユーザーアカウント")
    name = models.CharField(max_length=100, verbose_name="名前")
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="電話番号")
    email = models.EmailField(blank=True, null=True, verbose_name="メールアドレス")
    position = models.CharField(max_length=100, blank=True, null=True, verbose_name="役職/担当")
    is_active = models.BooleanField(default=True, verbose_name="有効")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="作成日時")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新日時")

    class Meta:
        verbose_name = "スタッフ"
        verbose_name_plural = "スタッフ"
        ordering = ['name']

    def __str__(self):
        return self.name


class ShiftType(models.Model):
    """シフト種別モデル（早番・遅番など）"""
    name = models.CharField(max_length=50, verbose_name="シフト種別名")
    color = models.CharField(max_length=20, default="#3498db", verbose_name="表示色")
    start_time = models.TimeField(verbose_name="デフォルト開始時間")
    end_time = models.TimeField(verbose_name="デフォルト終了時間")
    description = models.TextField(blank=True, null=True, verbose_name="説明")

    class Meta:
        verbose_name = "シフト種別"
        verbose_name_plural = "シフト種別"

    def __str__(self):
        return self.name


class Shift(models.Model):
    """シフト情報モデル"""
    DELETION_REASON_CHOICES = [
        ('public_holiday', '公休'),
        ('paid_leave', '有給休暇'),
        ('paid_leave_am', '有給休暇(午前)'),
        ('paid_leave_pm', '有給休暇(午後)'),
        ('absenteeism', '欠勤'),
        ('other', 'その他'),
    ]

    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, verbose_name="スタッフ")
    shift_type = models.ForeignKey(ShiftType, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="シフト種別")
    date = models.DateField(verbose_name="日付")
    start_time = models.TimeField(verbose_name="開始時間")
    end_time = models.TimeField(verbose_name="終了時間")
    notes = models.TextField(blank=True, null=True, verbose_name="備考")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="作成日時")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新日時")

    is_deleted_with_reason = models.BooleanField(default=False, verbose_name="事由付き削除フラグ")
    deletion_reason = models.CharField(
        max_length=50,
        choices=DELETION_REASON_CHOICES,
        blank=True,
        null=True,
        verbose_name="削除事由"
    )

    class Meta:
        verbose_name = "シフト"
        verbose_name_plural = "シフト"
        ordering = ['date', 'start_time']
        unique_together = ['staff', 'date', 'start_time']

    def __str__(self):
        status = ""
        if self.is_deleted_with_reason:
            status = f" (削除事由: {self.get_deletion_reason_display()})"
        return f"{self.staff.name} - {self.date} ({self.start_time}〜{self.end_time}){status}"


class ShiftTemplate(models.Model):
    """シフトテンプレートモデル"""
    name = models.CharField(max_length=100, verbose_name="テンプレート名")
    description = models.TextField(blank=True, null=True, verbose_name="説明")
    is_active = models.BooleanField(default=True, verbose_name="有効")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="作成日時")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新日時")

    class Meta:
        verbose_name = "シフトテンプレート"
        verbose_name_plural = "シフトテンプレート"

    def __str__(self):
        return self.name


class ShiftTemplateDetail(models.Model):
    """シフトテンプレート詳細モデル"""
    WEEKDAY_CHOICES = [
        (0, '月曜日'),
        (1, '火曜日'),
        (2, '水曜日'),
        (3, '木曜日'),
        (4, '金曜日'),
        (5, '土曜日'),
        (6, '日曜日'),
    ]
    
    template = models.ForeignKey(ShiftTemplate, on_delete=models.CASCADE, related_name='details', verbose_name="テンプレート")
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, verbose_name="スタッフ")
    shift_type = models.ForeignKey(ShiftType, on_delete=models.CASCADE, verbose_name="シフト種別")
    weekday = models.IntegerField(choices=WEEKDAY_CHOICES, verbose_name="曜日")
    start_time = models.TimeField(verbose_name="開始時間")
    end_time = models.TimeField(verbose_name="終了時間")

    class Meta:
        verbose_name = "シフトテンプレート詳細"
        verbose_name_plural = "シフトテンプレート詳細"
        unique_together = ['template', 'staff', 'weekday']

    def __str__(self):
        return f"{self.template.name} - {self.staff.name} - {self.get_weekday_display()}" 