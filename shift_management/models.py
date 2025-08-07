from django.db import models
from django.contrib.auth.models import User

class Organization(models.Model):
    """組織（業者・施設）情報モデル"""
    name = models.CharField(max_length=100, verbose_name="組織名")
    code = models.CharField(max_length=20, unique=True, verbose_name="組織コード")
    description = models.TextField(blank=True, null=True, verbose_name="説明")
    is_active = models.BooleanField(default=True, verbose_name="有効")
    
    # 設定項目
    timezone = models.CharField(max_length=50, default='Asia/Tokyo', verbose_name="タイムゾーン")
    currency = models.CharField(max_length=3, default='JPY', verbose_name="通貨")
    
    # 連絡先情報
    contact_email = models.EmailField(blank=True, null=True, verbose_name="連絡先メール")
    contact_phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="連絡先電話")
    address = models.TextField(blank=True, null=True, verbose_name="住所")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="作成日時")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新日時")
    
    class Meta:
        verbose_name = "組織"
        verbose_name_plural = "組織"
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.code})"
    
    def get_active_staff_count(self):
        """有効なスタッフ数を取得"""
        return self.staff_set.filter(is_active=True, approval_status='approved').count()

class Staff(models.Model):
    """スタッフ（従業員）情報モデル"""
    APPROVAL_STATUS_CHOICES = [
        ('pending', '承認待ち'),
        ('approved', '承認済み'),
        ('rejected', '却下'),
    ]
    
    ROLE_TYPE_CHOICES = [
        ('user', '利用者'),
        ('part_time', 'アルバイト'),
        ('staff', '職員'),
        ('manager', '管理者'),
    ]
    
    # 組織フィールドを追加
    organization = models.ForeignKey(
        Organization, 
        on_delete=models.CASCADE, 
        verbose_name="所属組織",
        null=True,  # 既存データとの互換性のため一時的にnull許可
        blank=True
    )
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True, verbose_name="ユーザーアカウント")
    name = models.CharField(max_length=100, verbose_name="名前")
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="電話番号")
    email = models.EmailField(blank=True, null=True, verbose_name="メールアドレス")
    position = models.CharField(max_length=100, blank=True, null=True, verbose_name="役職/担当")
    role_type = models.CharField(
        max_length=20,
        choices=ROLE_TYPE_CHOICES,
        default='user',
        verbose_name="権限種別"
    )
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
        ordering = ['organization', 'name']
        # 組織内でのユニーク制約
        constraints = [
            models.UniqueConstraint(
                fields=['organization', 'email'],
                condition=models.Q(email__isnull=False),
                name='unique_email_per_organization'
            ),
        ]

    def __str__(self):
        org_name = self.organization.name if self.organization else "未設定"
        return f"{self.name} ({org_name})"
    
    def is_approved(self):
        """承認済みかどうかを判定"""
        return self.approval_status == 'approved'
    
    def is_pending(self):
        """承認待ちかどうかを判定"""
        return self.approval_status == 'pending'
    
    def get_role_display_with_icon(self):
        """権限種別をアイコン付きで表示"""
        role_icons = {
            'user': '👤',
            'part_time': '🎒',
            'staff': '👔',
            'manager': '👑',
        }
        icon = role_icons.get(self.role_type, '👤')
        return f"{icon} {self.get_role_type_display()}"
    
    def can_view_staff_shifts(self, target_staff):
        """対象スタッフのシフトを閲覧できるかどうかを判定"""
        # 異なる組織のスタッフは閲覧不可
        if self.organization != target_staff.organization:
            return False
        
        # 自分のシフトは常に閲覧可能
        if self == target_staff:
            return True
        
        # 管理者は同一組織内の全員のシフトを閲覧可能
        if self.role_type == 'manager':
            return True
        
        # 職員は同一組織内の職員とアルバイトのシフトを閲覧可能
        if self.role_type == 'staff':
            return target_staff.role_type in ['staff', 'part_time']
        
        # アルバイトは同一組織内の同じアルバイトのシフトを閲覧可能
        if self.role_type == 'part_time':
            return target_staff.role_type == 'part_time'
        
        # 利用者は自分のシフトのみ閲覧可能（上記で処理済み）
        return False


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


class LeaveRequest(models.Model):
    """休み・通院申請モデル"""
    REQUEST_TYPE_CHOICES = [
        ('paid_leave', '有給休暇'),
        ('sick_leave', '病気休暇'),
        ('medical_appointment', '通院'),
        ('other', 'その他'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', '通常'),
        ('medium', '重要'),
        ('high', '緊急'),
    ]
    
    APPROVAL_STATUS_CHOICES = [
        ('pending', '承認待ち'),
        ('approved', '承認済み'),
        ('rejected', '却下'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="申請者")
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, verbose_name="スタッフ")
    request_type = models.CharField(max_length=50, choices=REQUEST_TYPE_CHOICES, verbose_name="申請種別")
    start_date = models.DateField(verbose_name="開始日")
    end_date = models.DateField(verbose_name="終了日")
    reason = models.TextField(blank=True, null=True, verbose_name="理由")
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='low', verbose_name="緊急度")
    approval_status = models.CharField(
        max_length=20,
        choices=APPROVAL_STATUS_CHOICES,
        default='pending',
        verbose_name="承認状態"
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_leave_requests',
        verbose_name="承認者"
    )
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name="承認日時")
    rejection_reason = models.TextField(blank=True, null=True, verbose_name="却下理由")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="申請日時")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新日時")
    
    class Meta:
        verbose_name = "休み・通院申請"
        verbose_name_plural = "休み・通院申請"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.staff.name} - {self.get_request_type_display()} ({self.start_date}〜{self.end_date})"
    
    def is_approved(self):
        return self.approval_status == 'approved'
    
    def is_pending(self):
        return self.approval_status == 'pending'
    
    def get_duration_days(self):
        return (self.end_date - self.start_date).days + 1


class ShiftProposal(models.Model):
    """シフト打診モデル"""
    STATUS_CHOICES = [
        ('pending', '回答待ち'),
        ('accepted', '承諾'),
        ('declined', '拒否'),
        ('expired', '期限切れ'),
    ]
    
    proposed_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_proposals', verbose_name="打診者")
    proposed_to = models.ForeignKey(Staff, on_delete=models.CASCADE, verbose_name="打診先スタッフ")
    shift_date = models.DateField(verbose_name="シフト日")
    start_time = models.TimeField(verbose_name="開始時間")
    end_time = models.TimeField(verbose_name="終了時間")
    shift_type = models.ForeignKey(ShiftType, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="シフト種別")
    position = models.CharField(max_length=100, blank=True, null=True, verbose_name="担当ポジション")
    message = models.TextField(blank=True, null=True, verbose_name="メッセージ")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="回答状況")
    response_deadline = models.DateTimeField(null=True, blank=True, verbose_name="回答期限")
    responded_at = models.DateTimeField(null=True, blank=True, verbose_name="回答日時")
    response_message = models.TextField(blank=True, null=True, verbose_name="回答メッセージ")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="打診日時")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新日時")
    
    class Meta:
        verbose_name = "シフト打診"
        verbose_name_plural = "シフト打診"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.proposed_to.name} - {self.shift_date} ({self.get_status_display()})"
    
    def is_pending(self):
        return self.status == 'pending'
    
    def is_expired(self):
        from django.utils import timezone
        if self.response_deadline and timezone.now() > self.response_deadline:
            return True
        return self.status == 'expired'


class StaffCompatibility(models.Model):
    """スタッフ間相性設定モデル"""
    COMPATIBILITY_CHOICES = [
        (1, '避ける'),
        (2, '注意'),
        (3, '普通'),
        (4, '良好'),
    ]
    
    staff1 = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='compatibility_as_staff1', verbose_name="スタッフ1")
    staff2 = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='compatibility_as_staff2', verbose_name="スタッフ2")
    compatibility_level = models.IntegerField(choices=COMPATIBILITY_CHOICES, verbose_name="相性レベル")
    reason = models.TextField(blank=True, null=True, verbose_name="設定理由")
    set_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="設定者")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="設定日時")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新日時")
    
    class Meta:
        verbose_name = "スタッフ間相性設定"
        verbose_name_plural = "スタッフ間相性設定"
        unique_together = ['staff1', 'staff2']
    
    def __str__(self):
        return f"{self.staff1.name} ⇔ {self.staff2.name} ({self.get_compatibility_level_display()})"


class Holiday(models.Model):
    """祝日・休日モデル"""
    HOLIDAY_TYPE_CHOICES = [
        ('national', '国民の祝日'),
        ('company', '会社休日'),
        ('regional', '地域休日'),
    ]
    
    date = models.DateField(unique=True, verbose_name="日付")
    name = models.CharField(max_length=100, verbose_name="祝日名")
    holiday_type = models.CharField(max_length=20, choices=HOLIDAY_TYPE_CHOICES, default='national', verbose_name="祝日種別")
    is_active = models.BooleanField(default=True, verbose_name="有効")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="作成日時")
    
    class Meta:
        verbose_name = "祝日・休日"
        verbose_name_plural = "祝日・休日"
        ordering = ['date']
    
    def __str__(self):
        return f"{self.date} - {self.name}"


class Event(models.Model):
    """イベントモデル（会議、研修等）"""
    EVENT_TYPE_CHOICES = [
        ('meeting', '会議'),
        ('training', '研修'),
        ('event', 'イベント'),
        ('maintenance', 'メンテナンス'),
        ('other', 'その他'),
    ]
    
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        verbose_name="組織",
        null=True,  # 既存データとの互換性のため
        blank=True
    )
    title = models.CharField(max_length=200, verbose_name="タイトル")
    description = models.TextField(blank=True, null=True, verbose_name="説明")
    event_type = models.CharField(max_length=50, choices=EVENT_TYPE_CHOICES, verbose_name="イベント種別")
    start_datetime = models.DateTimeField(verbose_name="開始日時")
    end_datetime = models.DateTimeField(verbose_name="終了日時")
    location = models.CharField(max_length=200, blank=True, null=True, verbose_name="場所")
    participants = models.ManyToManyField(Staff, through='EventParticipant', verbose_name="参加者")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="作成者")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="作成日時")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新日時")
    
    class Meta:
        verbose_name = "イベント"
        verbose_name_plural = "イベント"
        ordering = ['start_datetime']
    
    def __str__(self):
        return f"{self.title} ({self.start_datetime.strftime('%Y-%m-%d %H:%M')})"


class EventParticipant(models.Model):
    """イベント参加者モデル"""
    STATUS_CHOICES = [
        ('invited', '招待済み'),
        ('accepted', '参加'),
        ('declined', '不参加'),
        ('maybe', '未定'),
    ]
    
    event = models.ForeignKey(Event, on_delete=models.CASCADE, verbose_name="イベント")
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, verbose_name="スタッフ")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='invited', verbose_name="参加状況")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="招待日時")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新日時")
    
    class Meta:
        verbose_name = "イベント参加者"
        verbose_name_plural = "イベント参加者"
        unique_together = ['event', 'staff']
    
    def __str__(self):
        return f"{self.event.title} - {self.staff.name} ({self.get_status_display()})"


class Notification(models.Model):
    """通知モデル"""
    NOTIFICATION_TYPE_CHOICES = [
        ('leave_request', '休み申請'),
        ('leave_approved', '休み承認'),
        ('leave_rejected', '休み拒否'),
        ('shift_proposal', 'シフト打診'),
        ('shift_proposal_accepted', 'シフト打診承諾'),
        ('shift_proposal_declined', 'シフト打診拒否'),
        ('shift_assigned', 'シフト割り当て'),
        ('general', '一般'),
    ]
    
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="受信者")
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPE_CHOICES, verbose_name="通知タイプ")
    title = models.CharField(max_length=200, verbose_name="タイトル")
    message = models.TextField(verbose_name="メッセージ")
    is_read = models.BooleanField(default=False, verbose_name="既読")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="作成日時")
    
    # 関連オブジェクトへの参照（任意）
    leave_request = models.ForeignKey(LeaveRequest, on_delete=models.CASCADE, null=True, blank=True, verbose_name="休み申請")
    shift_proposal = models.ForeignKey(ShiftProposal, on_delete=models.CASCADE, null=True, blank=True, verbose_name="シフト打診")
    shift = models.ForeignKey(Shift, on_delete=models.CASCADE, null=True, blank=True, verbose_name="シフト")
    
    class Meta:
        verbose_name = "通知"
        verbose_name_plural = "通知"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.recipient.username} - {self.title}"
    
    def mark_as_read(self):
        """既読にする"""
        self.is_read = True
        self.save()


def create_notification(recipient, notification_type, title, message, **kwargs):
    """通知作成ヘルパー関数"""
    notification = Notification.objects.create(
        recipient=recipient,
        notification_type=notification_type,
        title=title,
        message=message,
        **kwargs
    )
    return notification 