from django.db import models
from django.contrib.auth.models import User

class Staff(models.Model):
    """スタッフ（従業員）情報モデル"""
    APPROVAL_STATUS_CHOICES = [
        ('pending', '承認待ち'),
        ('approved', '承認済み'),
        ('rejected', '却下'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True, verbose_name="ユーザーアカウント")
    name = models.CharField(max_length=100, verbose_name="名前")
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="電話番号")
    email = models.EmailField(blank=True, null=True, verbose_name="メールアドレス")
    position = models.CharField(max_length=100, blank=True, null=True, verbose_name="役職/担当")
    is_active = models.BooleanField(default=True, verbose_name="有効")
    approval_status = models.CharField(
        max_length=20,
        choices=APPROVAL_STATUS_CHOICES,
        default='pending',
        verbose_name="承認状態"
    )
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name="承認日時")
    approved_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='approved_staff',
        verbose_name="承認者"
    )
    rejection_reason = models.TextField(blank=True, null=True, verbose_name="却下理由")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="作成日時")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新日時")

    class Meta:
        verbose_name = "スタッフ"
        verbose_name_plural = "スタッフ"
        ordering = ['name']

    def __str__(self):
        return self.name
    
    def is_approved(self):
        """承認済みかどうかを判定"""
        return self.approval_status == 'approved'
    
    def is_pending(self):
        """承認待ちかどうかを判定"""
        return self.approval_status == 'pending'


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
    
    APPROVAL_STATUS_CHOICES = [
        ('pending', '承認待ち'),
        ('approved', '承認済み'),
        ('rejected', '却下'),
    ]

    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, verbose_name="スタッフ")
    shift_type = models.ForeignKey(ShiftType, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="シフト種別")
    date = models.DateField(verbose_name="日付")
    start_time = models.TimeField(null=True, blank=True, verbose_name="開始時間")
    end_time = models.TimeField(null=True, blank=True, verbose_name="終了時間")
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
    
    # シフト承認関連フィールド
    approval_status = models.CharField(
        max_length=20,
        choices=APPROVAL_STATUS_CHOICES,
        default='approved',  # 管理者が作成したシフトはデフォルトで承認済み
        verbose_name="承認状態"
    )
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name="承認日時")
    approved_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='approved_shifts',
        verbose_name="承認者"
    )
    rejection_reason = models.TextField(blank=True, null=True, verbose_name="却下理由")
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_shifts',
        verbose_name="作成者"
    )

    class Meta:
        verbose_name = "シフト"
        verbose_name_plural = "シフト"
        ordering = ['date', 'start_time']
        # unique_together = ['staff', 'date', 'start_time']  # 事由登録でstart_timeがNullになるため一時的にコメントアウト

    def __str__(self):
        if self.is_deleted_with_reason:
            return f"{self.staff.name} - {self.date} (事由: {self.get_deletion_reason_display()})"
        else:
            time_str = ""
            if self.start_time and self.end_time:
                time_str = f" ({self.start_time}〜{self.end_time})"
            approval_str = ""
            if self.approval_status == 'pending':
                approval_str = " [承認待ち]"
            elif self.approval_status == 'rejected':
                approval_str = " [却下]"
            return f"{self.staff.name} - {self.date}{time_str}{approval_str}"
    
    def is_approved(self):
        """承認済みかどうかを判定"""
        return self.approval_status == 'approved'
    
    def is_pending(self):
        """承認待ちかどうかを判定"""
        return self.approval_status == 'pending'
    
    def is_staff_created(self):
        """スタッフが作成したシフトかどうかを判定"""
        if not self.created_by:
            return False
        # スタッフユーザーかどうかを判定（管理者でない場合）
        return not self.created_by.is_staff


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