from django.contrib import admin
from django.utils import timezone
from django.contrib import messages
from django.utils.html import format_html
from django.db.models import Count
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    Organization, Staff, ShiftType, Shift, ShiftTemplate, ShiftTemplateDetail,
    LeaveRequest, ShiftProposal, StaffCompatibility, Holiday, Event, EventParticipant,
    Notification
)


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    """組織管理画面"""
    list_display = [
        'name', 'code', 'get_staff_count', 'contact_email', 
        'contact_phone', 'is_active', 'created_at'
    ]
    list_filter = ['is_active', 'created_at', 'timezone']
    search_fields = ['name', 'code', 'contact_email']
    ordering = ['name']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('基本情報', {
            'fields': ('name', 'code', 'description', 'is_active')
        }),
        ('設定', {
            'fields': ('timezone', 'currency')
        }),
        ('連絡先', {
            'fields': ('contact_email', 'contact_phone', 'address')
        }),
        ('システム情報', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_staff_count(self, obj):
        """スタッフ数を表示"""
        count = obj.get_active_staff_count()
        total = obj.staff_set.count()
        if count > 0:
            url = reverse('admin:shift_management_staff_changelist') + f'?organization__id__exact={obj.id}'
            return format_html(
                '<a href="{}" style="color: #0066cc;">{}/{}名</a>',
                url, count, total
            )
        return f"{count}/{total}名"
    get_staff_count.short_description = 'スタッフ数（有効/総数）'
    
    def get_queryset(self, request):
        """スタッフ数を事前に取得してパフォーマンス向上"""
        return super().get_queryset(request).annotate(
            staff_count=Count('staff')
        )

@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    """スタッフ管理画面（組織対応版）"""
    list_display = [
        'name', 'organization', 'get_role_display_with_icon', 
        'phone', 'email', 'get_approval_status_display', 'is_active'
    ]
    list_filter = [
        'organization', 'role_type', 'approval_status', 
        'is_active', 'created_at'
    ]
    search_fields = ['name', 'email', 'phone', 'organization__name']
    ordering = ['organization', 'name']
    readonly_fields = ['created_at', 'updated_at', 'approved_at']
    
    fieldsets = (
        ('組織情報', {
            'fields': ('organization',)
        }),
        ('基本情報', {
            'fields': ('name', 'phone', 'email', 'position', 'role_type')
        }),
        ('ユーザーアカウント', {
            'fields': ('user',),
            'classes': ('collapse',)
        }),
        ('承認情報', {
            'fields': ('approval_status', 'approved_by', 'approved_at', 'rejection_reason')
        }),
        ('システム情報', {
            'fields': ('is_active', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_approval_status_display(self, obj):
        """承認状態を色付きで表示"""
        status_colors = {
            'pending': '#ffc107',    # 黄色
            'approved': '#28a745',   # 緑色
            'rejected': '#dc3545',   # 赤色
        }
        color = status_colors.get(obj.approval_status, '#6c757d')
        return format_html(
            '<span style="color: {}; font-weight: bold;">●</span> {}',
            color,
            obj.get_approval_status_display()
        )
    get_approval_status_display.short_description = '承認状態'
    
    def get_queryset(self, request):
        """組織でプリフェッチしてパフォーマンス向上"""
        return super().get_queryset(request).select_related('organization', 'user')
    
    # 一括承認アクション
    actions = ['approve_staff', 'reject_staff']
    
    def approve_staff(self, request, queryset):
        """選択したスタッフを一括承認"""
        updated = queryset.filter(approval_status='pending').update(
            approval_status='approved',
            approved_by=request.user,
            approved_at=timezone.now()
        )
        self.message_user(request, f'{updated}件のスタッフを承認しました。')
    approve_staff.short_description = '選択したスタッフを承認'
    
    def reject_staff(self, request, queryset):
        """選択したスタッフを一括却下"""
        updated = queryset.filter(approval_status='pending').update(
            approval_status='rejected'
        )
        self.message_user(request, f'{updated}件のスタッフを却下しました。')
    reject_staff.short_description = '選択したスタッフを却下'


@admin.register(ShiftType)
class ShiftTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'start_time', 'end_time', 'color']
    search_fields = ['name']


@admin.register(Shift)
class ShiftAdmin(admin.ModelAdmin):
    list_display = ['staff_name', 'date', 'shift_type', 'time_display', 'approval_status_display', 'created_by_display', 'created_at']
    list_filter = ['approval_status', 'date', 'shift_type', 'is_deleted_with_reason', 'deletion_reason', 'created_by']
    search_fields = ['staff__name']
    date_hierarchy = 'date'
    readonly_fields = ['created_at', 'updated_at', 'approved_at', 'approved_by', 'created_by']
    
    def changelist_view(self, request, extra_context=None):
        """承認待ちシフトの件数を表示"""
        extra_context = extra_context or {}
        
        # 承認待ちシフトの件数を取得
        pending_count = Shift.objects.filter(approval_status='pending').count()
        approved_count = Shift.objects.filter(approval_status='approved').count()
        rejected_count = Shift.objects.filter(approval_status='rejected').count()
        
        extra_context.update({
            'pending_shifts_count': pending_count,
            'approved_shifts_count': approved_count,
            'rejected_shifts_count': rejected_count,
        })
        
        return super().changelist_view(request, extra_context=extra_context)
    
    def staff_name(self, obj):
        """スタッフ名を表示"""
        return obj.staff.name
    staff_name.short_description = 'スタッフ'
    
    def time_display(self, obj):
        """時間を見やすく表示"""
        if obj.start_time and obj.end_time:
            return f"{obj.start_time.strftime('%H:%M')} - {obj.end_time.strftime('%H:%M')}"
        return "-"
    time_display.short_description = '時間'
    
    def approval_status_display(self, obj):
        """承認状態を色付きで表示"""
        if obj.approval_status == 'pending':
            return format_html('<span style="background-color: #fff3cd; color: #856404; padding: 2px 8px; border-radius: 4px; font-weight: bold;">🕐 承認待ち</span>')
        elif obj.approval_status == 'approved':
            return format_html('<span style="background-color: #d4edda; color: #155724; padding: 2px 8px; border-radius: 4px; font-weight: bold;">✅ 承認済み</span>')
        elif obj.approval_status == 'rejected':
            return format_html('<span style="background-color: #f8d7da; color: #721c24; padding: 2px 8px; border-radius: 4px; font-weight: bold;">❌ 却下</span>')
        return obj.approval_status
    approval_status_display.short_description = '承認状態'
    
    def created_by_display(self, obj):
        """作成者を表示"""
        if obj.created_by:
            if hasattr(obj.created_by, 'staff') and obj.created_by.staff:
                return f"{obj.created_by.staff.name} (スタッフ)"
            else:
                return f"{obj.created_by.username} (管理者)"
        return "システム"
    created_by_display.short_description = '作成者'
    
    fieldsets = (
        ('基本情報', {
            'fields': ('staff', 'shift_type', 'date', 'start_time', 'end_time', 'notes')
        }),
        ('承認情報', {
            'fields': ('approval_status', 'approved_at', 'approved_by', 'rejection_reason'),
            'classes': ('wide',)
        }),
        ('事由情報', {
            'fields': ('is_deleted_with_reason', 'deletion_reason'),
            'classes': ('collapse',)
        }),
        ('システム情報', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['approve_shifts', 'reject_shifts']
    
    def approve_shifts(self, request, queryset):
        """シフトを承認する"""
        updated = 0
        for shift in queryset:
            if shift.approval_status == 'pending':
                shift.approval_status = 'approved'
                shift.approved_at = timezone.now()
                shift.approved_by = request.user
                shift.rejection_reason = ''  # 却下理由をクリア
                shift.save()
                updated += 1
        
        if updated:
            messages.success(request, f'✅ {updated}件のシフトを承認しました。カレンダーに表示されるようになります。')
        else:
            messages.warning(request, '承認待ちのシフトが選択されていません。')
    
    approve_shifts.short_description = '✅ 選択されたシフトを承認する'
    
    def reject_shifts(self, request, queryset):
        """シフトを却下する"""
        updated = 0
        for shift in queryset:
            if shift.approval_status == 'pending':
                shift.approval_status = 'rejected'
                shift.approved_at = None
                shift.approved_by = None
                shift.save()
                updated += 1
        
        if updated:
            messages.success(request, f'❌ {updated}件のシフトを却下しました。カレンダーには表示されません。')
        else:
            messages.warning(request, '承認待ちのシフトが選択されていません。')
    
    reject_shifts.short_description = '❌ 選択されたシフトを却下する'
    
    def get_queryset(self, request):
        """承認待ちのシフトを優先表示"""
        qs = super().get_queryset(request)
        return qs.select_related('staff', 'shift_type', 'created_by').order_by('approval_status', '-created_at')
    
    class Media:
        css = {
            'all': ('admin/css/shift_admin.css',)
        }


@admin.register(ShiftTemplate)
class ShiftTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name']


@admin.register(ShiftTemplateDetail)
class ShiftTemplateDetailAdmin(admin.ModelAdmin):
    list_display = ['template', 'staff', 'weekday', 'shift_type', 'start_time', 'end_time']
    list_filter = ['template', 'weekday', 'shift_type']
    search_fields = ['template__name', 'staff__name']


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    """休み・通院申請管理画面"""
    list_display = [
        'staff_name', 'request_type', 'start_date', 'end_date', 
        'get_duration_days', 'priority_display', 'approval_status_display', 'created_at'
    ]
    list_filter = ['request_type', 'priority', 'approval_status', 'created_at']
    search_fields = ['staff__name', 'user__username', 'reason']
    date_hierarchy = 'start_date'
    readonly_fields = ['created_at', 'updated_at', 'approved_at', 'approved_by']
    
    fieldsets = (
        ('申請者情報', {
            'fields': ('user', 'staff')
        }),
        ('申請内容', {
            'fields': ('request_type', 'start_date', 'end_date', 'reason', 'priority')
        }),
        ('承認情報', {
            'fields': ('approval_status', 'approved_by', 'approved_at', 'rejection_reason')
        }),
        ('システム情報', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def staff_name(self, obj):
        return obj.staff.name
    staff_name.short_description = 'スタッフ'
    
    def priority_display(self, obj):
        """緊急度を色付きアイコン付きで表示"""
        colors = {'low': '#6c757d', 'medium': '#ffc107', 'high': '#dc3545'}
        icons = {'low': '📝', 'medium': '⚠️', 'high': '🚨'}
        color = colors.get(obj.priority, '#6c757d')
        icon = icons.get(obj.priority, '📝')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} {}</span>',
            color, icon, obj.get_priority_display()
        )
    priority_display.short_description = '緊急度'
    
    def approval_status_display(self, obj):
        """承認状態を色付きで表示"""
        if obj.approval_status == 'pending':
            return format_html('<span style="color: orange; font-weight: bold;">🕐 承認待ち</span>')
        elif obj.approval_status == 'approved':
            return format_html('<span style="color: green; font-weight: bold;">✅ 承認済み</span>')
        elif obj.approval_status == 'rejected':
            return format_html('<span style="color: red; font-weight: bold;">❌ 却下</span>')
        return obj.approval_status
    approval_status_display.short_description = '承認状態'
    
    # 一括承認・拒否アクション
    actions = ['approve_requests', 'reject_requests']
    
    def approve_requests(self, request, queryset):
        """選択された申請を承認する"""
        from django.utils import timezone
        from shift_management.views import create_shift_from_leave_request
        
        updated = 0
        for leave_request in queryset:
            if leave_request.approval_status == 'pending':
                leave_request.approval_status = 'approved'
                leave_request.approved_at = timezone.now()
                leave_request.approved_by = request.user
                leave_request.rejection_reason = ''  # 却下理由をクリア
                leave_request.save()
                
                # カレンダーにシフトを反映
                create_shift_from_leave_request(leave_request)
                
                # 通知作成
                try:
                    from shift_management.models import create_notification
                    create_notification(
                        recipient=leave_request.user,
                        notification_type='leave_approved',
                        title='休暇申請が承認されました',
                        message=f'{leave_request.get_request_type_display()}の申請が承認されました。',
                        leave_request=leave_request
                    )
                except:
                    pass  # 通知作成に失敗しても処理は継続
                
                updated += 1
        
        if updated:
            messages.success(request, f'{updated}件の休み申請を承認しました。カレンダーに反映されます。')
        else:
            messages.warning(request, '承認待ちの申請が選択されていません。')
    approve_requests.short_description = '選択された申請を承認する'
    
    def reject_requests(self, request, queryset):
        """選択された申請を却下する"""
        updated = 0
        for leave_request in queryset:
            if leave_request.approval_status == 'pending':
                leave_request.approval_status = 'rejected'
                leave_request.approved_at = None
                leave_request.approved_by = None
                leave_request.rejection_reason = '管理者により一括却下'
                leave_request.save()
                
                # 通知作成
                try:
                    from shift_management.models import create_notification
                    create_notification(
                        recipient=leave_request.user,
                        notification_type='leave_rejected',
                        title='休暇申請が却下されました',
                        message=f'{leave_request.get_request_type_display()}の申請が却下されました。理由: 管理者により一括却下',
                        leave_request=leave_request
                    )
                except:
                    pass  # 通知作成に失敗しても処理は継続
                
                updated += 1
        
        if updated:
            messages.success(request, f'{updated}件の休み申請を却下しました。')
        else:
            messages.warning(request, '承認待ちの申請が選択されていません。')
    reject_requests.short_description = '選択された申請を却下する'
    
    def get_queryset(self, request):
        """承認待ちの申請を最初に表示"""
        qs = super().get_queryset(request)
        return qs.select_related('user', 'staff', 'approved_by').order_by(
            'approval_status',  # pending, approved, rejected の順
            '-priority',  # 緊急度の高い順
            '-created_at'  # 新しい順
        )


@admin.register(ShiftProposal)
class ShiftProposalAdmin(admin.ModelAdmin):
    """シフト打診管理画面"""
    list_display = [
        'proposed_to_name', 'shift_date', 'time_display', 
        'position', 'status_display', 'response_deadline', 'created_at'
    ]
    list_filter = ['status', 'shift_date', 'created_at']
    search_fields = ['proposed_to__name', 'message', 'position']
    date_hierarchy = 'shift_date'
    readonly_fields = ['created_at', 'updated_at', 'responded_at']
    
    def proposed_to_name(self, obj):
        return obj.proposed_to.name
    proposed_to_name.short_description = '打診先'
    
    def time_display(self, obj):
        return f"{obj.start_time.strftime('%H:%M')} - {obj.end_time.strftime('%H:%M')}"
    time_display.short_description = '時間'
    
    def status_display(self, obj):
        """ステータスを色付きで表示"""
        status_colors = {
            'pending': ('#ffc107', '⏳'),
            'accepted': ('#28a745', '✅'),
            'declined': ('#dc3545', '❌'),
            'expired': ('#6c757d', '⏰'),
        }
        color, icon = status_colors.get(obj.status, ('#6c757d', ''))
        return format_html(
            '<span style="color: {};">{} {}</span>',
            color, icon, obj.get_status_display()
        )
    status_display.short_description = '回答状況'


@admin.register(StaffCompatibility)
class StaffCompatibilityAdmin(admin.ModelAdmin):
    """スタッフ間相性設定管理画面"""
    list_display = ['staff1', 'staff2', 'compatibility_display', 'set_by', 'created_at']
    list_filter = ['compatibility_level', 'created_at']
    search_fields = ['staff1__name', 'staff2__name', 'reason']
    
    def compatibility_display(self, obj):
        """相性レベルを色付きで表示"""
        colors = {
            1: '#dc3545',  # 避ける - 赤
            2: '#ffc107',  # 注意 - 黄
            3: '#6c757d',  # 普通 - グレー
            4: '#28a745',  # 良好 - 緑
        }
        color = colors.get(obj.compatibility_level, '#6c757d')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.get_compatibility_level_display()
        )
    compatibility_display.short_description = '相性レベル'


@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    """祝日・休日管理画面"""
    list_display = ['date', 'name', 'holiday_type', 'is_active']
    list_filter = ['holiday_type', 'is_active', 'date']
    search_fields = ['name']
    date_hierarchy = 'date'
    ordering = ['date']


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    """イベント管理画面"""
    list_display = [
        'title', 'organization', 'event_type', 'start_datetime', 
        'end_datetime', 'location', 'participant_count', 'created_by'
    ]
    list_filter = ['organization', 'event_type', 'start_datetime']
    search_fields = ['title', 'description', 'location']
    date_hierarchy = 'start_datetime'
    readonly_fields = ['created_at', 'updated_at']
    
    def participant_count(self, obj):
        count = obj.participants.count()
        return f"{count}名"
    participant_count.short_description = '参加者数'
    
    fieldsets = (
        ('基本情報', {
            'fields': ('organization', 'title', 'description', 'event_type')
        }),
        ('日時・場所', {
            'fields': ('start_datetime', 'end_datetime', 'location')
        }),
        ('システム情報', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(EventParticipant)
class EventParticipantAdmin(admin.ModelAdmin):
    """イベント参加者管理画面"""
    list_display = ['event', 'staff', 'status_display', 'created_at']
    list_filter = ['status', 'event__event_type', 'created_at']
    search_fields = ['event__title', 'staff__name']
    
    def status_display(self, obj):
        """参加状況を色付きで表示"""
        status_colors = {
            'invited': ('#6c757d', '📨'),
            'accepted': ('#28a745', '✅'),
            'declined': ('#dc3545', '❌'),
            'maybe': ('#ffc107', '❓'),
        }
        color, icon = status_colors.get(obj.status, ('#6c757d', ''))
        return format_html(
            '<span style="color: {};">{} {}</span>',
            color, icon, obj.get_status_display()
        )
    status_display.short_description = '参加状況'


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """通知管理画面"""
    list_display = [
        'recipient', 'notification_type', 'title', 
        'is_read_display', 'created_at'
    ]
    list_filter = ['notification_type', 'is_read', 'created_at']
    search_fields = ['recipient__username', 'title', 'message']
    readonly_fields = ['created_at']
    
    def is_read_display(self, obj):
        """既読状態を表示"""
        if obj.is_read:
            return format_html('<span style="color: #6c757d;">✓ 既読</span>')
        else:
            return format_html('<span style="color: #007bff; font-weight: bold;">● 未読</span>')
    is_read_display.short_description = '既読'
    
    actions = ['mark_as_read', 'mark_as_unread']
    
    def mark_as_read(self, request, queryset):
        """選択した通知を既読にする"""
        updated = queryset.update(is_read=True)
        messages.success(request, f'{updated}件の通知を既読にしました。')
    mark_as_read.short_description = '選択した通知を既読にする'
    
    def mark_as_unread(self, request, queryset):
        """選択した通知を未読にする"""
        updated = queryset.update(is_read=False)
        messages.success(request, f'{updated}件の通知を未読にしました。')
    mark_as_unread.short_description = '選択した通知を未読にする' 