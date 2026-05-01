from django.db import models
from django.db import IntegrityError
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

    # 請求書・納品書用の画像
    company_logo = models.ImageField(
        upload_to='organization/logos/',
        blank=True,
        null=True,
        verbose_name="会社ロゴ",
        help_text="請求書・納品書に表示される会社ロゴ画像"
    )
    company_seal = models.ImageField(
        upload_to='organization/seals/',
        blank=True,
        null=True,
        verbose_name="会社印",
        help_text="請求書・納品書に表示される会社印画像"
    )

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
        ('global_admin', 'グローバル管理者'),
    ]
    
    # 在庫管理権限の選択肢
    INVENTORY_PERMISSION_CHOICES = [
        ('none', '権限なし'),
        ('view', '閲覧のみ'),
        ('edit', '編集可能'),
        ('admin', '管理者権限'),
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
    
    # 在庫管理権限フィールドを追加
    inventory_permission = models.CharField(
        max_length=20,
        choices=INVENTORY_PERMISSION_CHOICES,
        default='none',
        verbose_name="在庫管理権限"
    )
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

    def save(self, *args, **kwargs):
        """
        保存時の自動処理
        - 管理者（manager）とグローバル管理者（global_admin）は在庫管理の全権限を付与
        """
        # 管理者とグローバル管理者は自動的に在庫管理の全権限を持つ
        if self.role_type in ['manager', 'global_admin']:
            if self.inventory_permission == 'none':
                self.inventory_permission = 'admin'

        super().save(*args, **kwargs)

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
            'global_admin': '🌐',
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
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        verbose_name="組織",
        null=True,
        blank=True
    )
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
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, null=True, blank=True, verbose_name="スタッフ")
    shift_type = models.ForeignKey(ShiftType, on_delete=models.CASCADE, verbose_name="シフト種別")
    weekday = models.IntegerField(choices=WEEKDAY_CHOICES, verbose_name="曜日")
    start_time = models.TimeField(verbose_name="開始時間")
    end_time = models.TimeField(verbose_name="終了時間")

    class Meta:
        verbose_name = "シフトテンプレート詳細"
        verbose_name_plural = "シフトテンプレート詳細"
        # unique_togetherを削除（staffがnullの場合に複数レコード作成可能にするため）

    def __str__(self):
        staff_name = self.staff.name if self.staff else "スタッフ指定なし"
        return f"{self.template.name} - {staff_name} - {self.get_weekday_display()}"


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


# ===== 発注管理機能モデル =====

class Item(models.Model):
    """品目情報モデル"""
    item_code = models.CharField(max_length=50, verbose_name="品目コード")
    item_name = models.CharField(max_length=200, verbose_name="品目名")
    unit = models.CharField(max_length=20, default="個", verbose_name="単位")
    order_url = models.URLField(blank=True, null=True, verbose_name="発注先URL")
    threshold = models.IntegerField(
        default=10,
        verbose_name="在庫の目安数",
        help_text="この数を下回ると不足として表示されます"
    )
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, verbose_name="組織")
    is_active = models.BooleanField(default=True, verbose_name="有効")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="作成日時")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新日時")
    
    class Meta:
        verbose_name = "品目"
        verbose_name_plural = "品目"
        ordering = ['item_code']
        unique_together = ['item_code', 'organization']  # 組織内でのみユニーク
    
    def __str__(self):
        return f"{self.item_code} - {self.item_name}"
    
    @property
    def current_stock(self):
        """現在の在庫数を取得"""
        try:
            inventory = self.inventory.first()
            return inventory.current_stock if inventory else 0
        except:
            return 0
    
    @property
    def is_low_stock(self):
        """在庫閾値を下回っているかチェック"""
        return self.current_stock <= self.threshold


class Inventory(models.Model):
    """在庫情報モデル"""
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='inventory', verbose_name="品目")
    current_stock = models.IntegerField(default=0, verbose_name="現在の在庫数")
    last_updated = models.DateTimeField(auto_now=True, verbose_name="最終更新日時")
    
    class Meta:
        verbose_name = "在庫"
        verbose_name_plural = "在庫"
        unique_together = ['item']
    
    def __str__(self):
        return f"{self.item.item_name}: {self.current_stock}{self.item.unit}"


class Transaction(models.Model):
    """入出庫履歴モデル"""
    TRANSACTION_TYPE_CHOICES = [
        ('in', '入庫'),
        ('out', '出庫'),
        ('adjustment', '在庫修正'),
    ]
    
    item = models.ForeignKey(Item, on_delete=models.CASCADE, verbose_name="品目")
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES, verbose_name="トランザクションタイプ")
    quantity = models.IntegerField(verbose_name="数量")
    transaction_date = models.DateTimeField(auto_now_add=True, verbose_name="トランザクション日時")
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, verbose_name="担当者")
    notes = models.TextField(blank=True, null=True, verbose_name="備考")
    
    class Meta:
        verbose_name = "入出庫履歴"
        verbose_name_plural = "入出庫履歴"
        ordering = ['-transaction_date']
    
    def __str__(self):
        return f"{self.item.item_name} {self.get_transaction_type_display()} {self.quantity}{self.item.unit}"


class Order(models.Model):
    """発注履歴モデル"""
    STATUS_CHOICES = [
        ('ordered', '発注済み'),
        ('delivered', '納品済み'),
        ('cancelled', 'キャンセル'),
    ]
    
    item = models.ForeignKey(Item, on_delete=models.CASCADE, verbose_name="品目")
    ordered_quantity = models.IntegerField(verbose_name="発注数量")
    order_date = models.DateTimeField(auto_now_add=True, verbose_name="発注日時")
    supplier_url = models.URLField(blank=True, null=True, verbose_name="発注先URL")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ordered', verbose_name="状態")
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, verbose_name="発注担当者")
    delivery_date = models.DateTimeField(null=True, blank=True, verbose_name="納品日時")
    notes = models.TextField(blank=True, null=True, verbose_name="備考")
    
    class Meta:
        verbose_name = "発注履歴"
        verbose_name_plural = "発注履歴"
        ordering = ['-order_date']
    
    def __str__(self):
        return f"{self.item.item_name} {self.ordered_quantity}{self.item.unit} ({self.get_status_display()})"


class InventoryAuditLog(models.Model):
    """在庫管理監査ログモデル"""
    
    ACTION_CHOICES = [
        ('item_create', '品目作成'),
        ('item_update', '品目更新'),
        ('item_delete', '品目削除'),
        ('inventory_in', '入庫処理'),
        ('inventory_out', '出庫処理'),
        ('inventory_adjust', '在庫修正'),
        ('order_create', '発注作成'),
        ('order_update', '発注更新'),
        ('order_cancel', '発注キャンセル'),
        # 請求/納品: 監査用途のアクション（DBスキーマ変更不要）
        ('invoice_create', '請求書作成'),
        ('invoice_update', '請求書更新'),
        ('invoice_status', '請求書ステータス変更'),
        ('delivery_note_create', '納品書作成'),
        ('delivery_note_status', '納品書ステータス変更'),
        # 認証/権限
        ('user_login', 'ログイン'),
        ('user_logout', 'ログアウト'),
        ('permission_change', '権限変更'),
    ]
    
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        verbose_name="組織"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name="実行ユーザー"
    )
    action = models.CharField(
        max_length=20,
        choices=ACTION_CHOICES,
        verbose_name="操作種別"
    )
    target_model = models.CharField(
        max_length=50,
        verbose_name="対象モデル",
        blank=True,
        null=True
    )
    target_id = models.PositiveIntegerField(
        verbose_name="対象オブジェクトID",
        blank=True,
        null=True
    )
    description = models.TextField(
        verbose_name="操作説明",
        blank=True,
        null=True
    )
    old_values = models.JSONField(
        verbose_name="変更前データ",
        blank=True,
        null=True
    )
    new_values = models.JSONField(
        verbose_name="変更後データ",
        blank=True,
        null=True
    )
    ip_address = models.GenericIPAddressField(
        verbose_name="IPアドレス",
        blank=True,
        null=True
    )
    user_agent = models.TextField(
        verbose_name="ユーザーエージェント",
        blank=True,
        null=True
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        verbose_name="実行日時"
    )
    
    class Meta:
        verbose_name = "監査ログ"
        verbose_name_plural = "監査ログ"
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['organization', '-timestamp']),
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['action', '-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.get_action_display()} ({self.timestamp})"


# ===== 請求書・納品書発行機能モデル =====

class Invoice(models.Model):
    """請求書モデル"""
    
    STATUS_CHOICES = [
        ('draft', '下書き'),
        ('issued', '発行済み'),
        ('paid', '入金済み'),
        ('overdue', '支払期限超過'),
        ('cancelled', 'キャンセル'),
    ]
    
    invoice_number = models.CharField(max_length=50, unique=True, verbose_name="請求書番号")
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, verbose_name="組織")
    order = models.ForeignKey(Order, on_delete=models.CASCADE, null=True, blank=True, verbose_name="関連発注")
    
    # 請求先情報
    bill_to_name = models.CharField(max_length=200, verbose_name="請求先名")
    bill_to_address = models.TextField(verbose_name="請求先住所")
    bill_to_contact = models.CharField(max_length=100, blank=True, null=True, verbose_name="担当者")
    bill_to_phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="電話番号")
    bill_to_email = models.EmailField(blank=True, null=True, verbose_name="メールアドレス")
    
    # 請求情報
    issue_date = models.DateField(verbose_name="発行日")
    due_date = models.DateField(verbose_name="支払期限")
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="小計")
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=10.0, verbose_name="消費税率(%)")
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="消費税額")
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="合計金額")
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', verbose_name="状態")
    payment_date = models.DateField(null=True, blank=True, verbose_name="入金日")
    notes = models.TextField(blank=True, null=True, verbose_name="備考")

    # 発行元情報（組織情報を上書きしたい場合に使用）
    issuer_name = models.CharField(max_length=200, blank=True, null=True, verbose_name="発行元名（上書き）")
    issuer_address = models.TextField(blank=True, null=True, verbose_name="発行元住所（上書き）")
    issuer_phone = models.CharField(max_length=50, blank=True, null=True, verbose_name="発行元電話（上書き）")
    issuer_email = models.EmailField(blank=True, null=True, verbose_name="発行元メール（上書き）")
    
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="作成者")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="作成日時")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新日時")
    
    class Meta:
        verbose_name = "請求書"
        verbose_name_plural = "請求書"
        ordering = ['-issue_date']
    
    def __str__(self):
        return f"{self.invoice_number} - {self.bill_to_name} ({self.get_status_display()})"
    
    def save(self, *args, **kwargs):
        from datetime import datetime
        # 金額計算（採番に関わらず毎回更新）
        self.tax_amount = self.subtotal * (self.tax_rate / 100)
        self.total_amount = self.subtotal + self.tax_amount

        # 請求書番号の同時実行安全な自動生成
        if not self.invoice_number:
            now = datetime.now()
            prefix = f"INV{now.strftime('%Y%m')}"
            attempts = 0
            while attempts < 5:
                last_invoice = Invoice.objects.filter(
                    invoice_number__startswith=prefix
                ).order_by('-invoice_number').first()
                if last_invoice:
                    try:
                        last_num = int(last_invoice.invoice_number[-4:])
                    except ValueError:
                        last_num = 0
                else:
                    last_num = 0
                candidate = f"{prefix}{last_num + 1:04d}"
                self.invoice_number = candidate
                try:
                    return super().save(*args, **kwargs)
                except IntegrityError:
                    attempts += 1
                    continue
            # 最終手段：タイムスタンプ含みで一意にして保存
            self.invoice_number = f"{prefix}{now.strftime('%d%H%M%S')}"
            return super().save(*args, **kwargs)
        else:
            return super().save(*args, **kwargs)


class InvoiceItem(models.Model):
    """請求書明細モデル"""
    
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items', verbose_name="請求書")
    item = models.ForeignKey(Item, on_delete=models.CASCADE, null=True, blank=True, verbose_name="品目")
    item_name = models.CharField(max_length=200, verbose_name="品目名")
    item_description = models.TextField(blank=True, null=True, verbose_name="品目説明")
    quantity = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="数量")
    unit = models.CharField(max_length=20, default="個", verbose_name="単位")
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="単価")
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="金額")
    
    class Meta:
        verbose_name = "請求書明細"
        verbose_name_plural = "請求書明細"
        ordering = ['id']
    
    def save(self, *args, **kwargs):
        # 金額計算
        self.amount = self.quantity * self.unit_price
        super().save(*args, **kwargs)
        
        # 請求書の小計を再計算
        self.invoice.subtotal = sum(item.amount for item in self.invoice.items.all())
        self.invoice.save()
    
    def __str__(self):
        return f"{self.item_name} x {self.quantity}{self.unit}"


class DeliveryNote(models.Model):
    """納品書モデル"""
    
    STATUS_CHOICES = [
        ('draft', '下書き'),
        ('issued', '発行済み'),
        ('delivered', '納品済み'),
        ('cancelled', 'キャンセル'),
    ]
    
    delivery_number = models.CharField(max_length=50, unique=True, verbose_name="納品書番号")
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, verbose_name="組織")
    order = models.ForeignKey(Order, on_delete=models.CASCADE, null=True, blank=True, verbose_name="関連発注")
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, null=True, blank=True, verbose_name="関連請求書")
    
    # 納品先情報
    deliver_to_name = models.CharField(max_length=200, verbose_name="納品先名")
    deliver_to_address = models.TextField(verbose_name="納品先住所")
    deliver_to_contact = models.CharField(max_length=100, blank=True, null=True, verbose_name="担当者")
    deliver_to_phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="電話番号")
    
    # 納品情報
    issue_date = models.DateField(verbose_name="発行日")
    delivery_date = models.DateField(null=True, blank=True, verbose_name="納品予定日")
    actual_delivery_date = models.DateField(null=True, blank=True, verbose_name="実際の納品日")
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', verbose_name="状態")
    notes = models.TextField(blank=True, null=True, verbose_name="備考")

    # 在庫反映フラグ（納品済み在庫の二重反映防止）
    applied_to_inventory = models.BooleanField(default=False, verbose_name="在庫反映済み")

    # 発行元情報（組織情報を上書きしたい場合に使用）
    issuer_name = models.CharField(max_length=200, blank=True, null=True, verbose_name="発行元名（上書き）")
    issuer_address = models.TextField(blank=True, null=True, verbose_name="発行元住所（上書き）")
    issuer_phone = models.CharField(max_length=50, blank=True, null=True, verbose_name="発行元電話（上書き）")
    issuer_email = models.EmailField(blank=True, null=True, verbose_name="発行元メール（上書き）")
    
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="作成者")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="作成日時")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新日時")
    
    class Meta:
        verbose_name = "納品書"
        verbose_name_plural = "納品書"
        ordering = ['-issue_date']
    
    def __str__(self):
        return f"{self.delivery_number} - {self.deliver_to_name} ({self.get_status_display()})"
    
    def save(self, *args, **kwargs):
        # 納品書番号の同時実行安全な自動生成
        if not self.delivery_number:
            from datetime import datetime
            now = datetime.now()
            prefix = f"DEL{now.strftime('%Y%m')}"
            attempts = 0
            while attempts < 5:
                last_delivery = DeliveryNote.objects.filter(
                    delivery_number__startswith=prefix
                ).order_by('-delivery_number').first()
                if last_delivery:
                    try:
                        last_num = int(last_delivery.delivery_number[-4:])
                    except ValueError:
                        last_num = 0
                else:
                    last_num = 0
                candidate = f"{prefix}{last_num + 1:04d}"
                self.delivery_number = candidate
                try:
                    return super().save(*args, **kwargs)
                except IntegrityError:
                    attempts += 1
                    continue
            # 最終手段：タイムスタンプ含みで一意にして保存
            self.delivery_number = f"{prefix}{now.strftime('%d%H%M%S')}"
            return super().save(*args, **kwargs)
        else:
            return super().save(*args, **kwargs)


class DeliveryNoteItem(models.Model):
    """納品書明細モデル"""
    
    delivery_note = models.ForeignKey(DeliveryNote, on_delete=models.CASCADE, related_name='items', verbose_name="納品書")
    item = models.ForeignKey(Item, on_delete=models.CASCADE, null=True, blank=True, verbose_name="品目")
    item_name = models.CharField(max_length=200, verbose_name="品目名")
    item_description = models.TextField(blank=True, null=True, verbose_name="品目説明")
    quantity = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="数量")
    unit = models.CharField(max_length=20, default="個", verbose_name="単位")
    delivered_quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="実際の納品数量")
    
    class Meta:
        verbose_name = "納品書明細"
        verbose_name_plural = "納品書明細"
        ordering = ['id']
    
    def __str__(self):
        return f"{self.item_name} x {self.quantity}{self.unit}"
