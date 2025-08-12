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
    Notification, Item, Inventory, Transaction, Order, InventoryAuditLog,
    Invoice, InvoiceItem, DeliveryNote, DeliveryNoteItem
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
        'phone', 'email', 'get_approval_status_display', 'get_inventory_permission_display', 'is_active'
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
            'fields': ('name', 'phone', 'email', 'position', 'role_type', 'inventory_permission')
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
    
    def get_inventory_permission_display(self, obj):
        """在庫権限を色付きで表示"""
        permission_colors = {
            'none': '#6c757d',    # グレー
            'view': '#17a2b8',    # 青色
            'edit': '#28a745',    # 緑色
            'admin': '#dc3545',   # 赤色
        }
        color = permission_colors.get(obj.inventory_permission, '#6c757d')
        return format_html(
            '<span style="color: {}; font-weight: bold;">●</span> {}',
            color,
            obj.get_inventory_permission_display()
        )
    get_inventory_permission_display.short_description = '在庫権限'
    
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


# ===== 発注管理機能の管理画面 =====

@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    """品目管理画面"""
    list_display = [
        'item_code', 'item_name', 'organization', 'current_stock_display', 
        'threshold', 'unit', 'order_url_display', 'is_active', 'created_at'
    ]
    list_filter = ['organization', 'is_active', 'created_at']
    search_fields = ['item_code', 'item_name', 'organization__name']
    list_editable = ['threshold', 'is_active']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('基本情報', {
            'fields': ('item_code', 'item_name', 'unit', 'organization', 'is_active')
        }),
        ('在庫管理', {
            'fields': ('threshold',)
        }),
        ('発注情報', {
            'fields': ('order_url',)
        }),
        ('システム情報', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def current_stock_display(self, obj):
        """現在の在庫数を表示"""
        stock = obj.current_stock
        if obj.is_low_stock:
            return format_html(
                '<span style="color: #dc3545; font-weight: bold;">⚠ {}{}（不足）</span>',
                stock, obj.unit
            )
        else:
            return format_html('{}{}', stock, obj.unit)
    current_stock_display.short_description = '現在在庫'
    
    def order_url_display(self, obj):
        """発注先URLを表示"""
        if obj.order_url:
            return format_html(
                '<a href="{}" target="_blank">🔗 発注サイト</a>',
                obj.order_url
            )
        return '-'
    order_url_display.short_description = '発注先'


@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    """在庫管理画面"""
    list_display = [
        'item_display', 'item_code', 'organization', 'current_stock_display', 
        'threshold_display', 'status_display', 'last_updated'
    ]
    list_filter = ['item__organization', 'last_updated']
    search_fields = ['item__item_code', 'item__item_name', 'item__organization__name']
    readonly_fields = ['last_updated']
    
    def item_display(self, obj):
        """品目名を表示"""
        return obj.item.item_name
    item_display.short_description = '品目名'
    
    def item_code(self, obj):
        """品目コードを表示"""
        return obj.item.item_code
    item_code.short_description = '品目コード'
    
    def organization(self, obj):
        """組織を表示"""
        return obj.item.organization.name
    organization.short_description = '組織'
    
    def current_stock_display(self, obj):
        """在庫数を表示"""
        return format_html('{}{}', obj.current_stock, obj.item.unit)
    current_stock_display.short_description = '在庫数'
    
    def threshold_display(self, obj):
        """閾値を表示"""
        return format_html('{}{}', obj.item.threshold, obj.item.unit)
    threshold_display.short_description = '閾値'
    
    def status_display(self, obj):
        """在庫状況を表示"""
        if obj.item.is_low_stock:
            return format_html('<span style="color: #dc3545; font-weight: bold;">⚠ 不足</span>')
        else:
            return format_html('<span style="color: #28a745;">✓ 充足</span>')
    status_display.short_description = '状況'


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    """入出庫履歴管理画面"""
    list_display = [
        'transaction_date', 'item_display', 'item_code', 'transaction_type_display', 
        'quantity_display', 'user_display', 'notes_short'
    ]
    list_filter = ['transaction_type', 'transaction_date', 'item__organization']
    search_fields = ['item__item_code', 'item__item_name', 'notes', 'user__username']
    readonly_fields = ['transaction_date']
    date_hierarchy = 'transaction_date'
    
    def item_display(self, obj):
        """品目名を表示"""
        return obj.item.item_name
    item_display.short_description = '品目名'
    
    def item_code(self, obj):
        """品目コードを表示"""
        return obj.item.item_code
    item_code.short_description = '品目コード'
    
    def transaction_type_display(self, obj):
        """トランザクションタイプを色付きで表示"""
        colors = {
            'in': '#28a745',    # 緑
            'out': '#ffc107',   # 黄
            'adjustment': '#17a2b8'  # 青
        }
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            colors.get(obj.transaction_type, '#6c757d'),
            obj.get_transaction_type_display()
        )
    transaction_type_display.short_description = 'タイプ'
    
    def quantity_display(self, obj):
        """数量を表示"""
        return format_html('{}{}', obj.quantity, obj.item.unit)
    quantity_display.short_description = '数量'
    
    def user_display(self, obj):
        """担当者を表示"""
        return obj.user.username if obj.user else '-'
    user_display.short_description = '担当者'
    
    def notes_short(self, obj):
        """備考の短縮表示"""
        if obj.notes:
            return obj.notes[:30] + '...' if len(obj.notes) > 30 else obj.notes
        return '-'
    notes_short.short_description = '備考'


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """発注履歴管理画面"""
    list_display = [
        'order_date', 'item_display', 'item_code', 'ordered_quantity_display',
        'status_display', 'supplier_url_display', 'user_display', 'delivery_date'
    ]
    list_filter = ['status', 'order_date', 'delivery_date', 'item__organization']
    search_fields = ['item__item_code', 'item__item_name', 'notes', 'user__username']
    readonly_fields = ['order_date']
    date_hierarchy = 'order_date'
    # list_editable = ['status']  # list_displayにstatus_displayがあるため無効化
    
    fieldsets = (
        ('発注情報', {
            'fields': ('item', 'ordered_quantity', 'supplier_url', 'status')
        }),
        ('日時情報', {
            'fields': ('order_date', 'delivery_date')
        }),
        ('担当者・備考', {
            'fields': ('user', 'notes')
        }),
    )
    
    def item_display(self, obj):
        """品目名を表示"""
        return obj.item.item_name
    item_display.short_description = '品目名'
    
    def item_code(self, obj):
        """品目コードを表示"""
        return obj.item.item_code
    item_code.short_description = '品目コード'
    
    def ordered_quantity_display(self, obj):
        """発注数量を表示"""
        return format_html('{}{}', obj.ordered_quantity, obj.item.unit)
    ordered_quantity_display.short_description = '発注数量'
    
    def status_display(self, obj):
        """ステータスを色付きで表示"""
        colors = {
            'ordered': '#007bff',     # 青
            'delivered': '#28a745',   # 緑
            'cancelled': '#dc3545'    # 赤
        }
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            colors.get(obj.status, '#6c757d'),
            obj.get_status_display()
        )
    status_display.short_description = 'ステータス'
    
    def supplier_url_display(self, obj):
        """発注先URLを表示"""
        if obj.supplier_url:
            return format_html(
                '<a href="{}" target="_blank">🔗 発注サイト</a>',
                obj.supplier_url
            )
        return '-'
    supplier_url_display.short_description = '発注先'
    
    def user_display(self, obj):
        """担当者を表示"""
        return obj.user.username if obj.user else '-'
    user_display.short_description = '担当者'
    
    actions = ['mark_as_delivered', 'mark_as_cancelled']
    
    def mark_as_delivered(self, request, queryset):
        """選択した発注を納品済みにする"""
        updated = 0
        for order in queryset:
            if order.status == 'ordered':
                order.status = 'delivered'
                order.delivery_date = timezone.now()
                order.save()
                updated += 1
        
        if updated:
            messages.success(request, f'{updated}件の発注を納品済みにしました。')
        else:
            messages.warning(request, '発注済みの発注が選択されていません。')
    mark_as_delivered.short_description = '選択した発注を納品済みにする'
    
    def mark_as_cancelled(self, request, queryset):
        """選択した発注をキャンセルにする"""
        updated = queryset.exclude(status='delivered').update(status='cancelled')
        if updated:
            messages.success(request, f'{updated}件の発注をキャンセルしました。')
        else:
            messages.warning(request, 'キャンセル可能な発注が選択されていません。')
    mark_as_cancelled.short_description = '選択した発注をキャンセルする'


@admin.register(InventoryAuditLog)
class InventoryAuditLogAdmin(admin.ModelAdmin):
    """監査ログ管理画面"""
    list_display = [
        'timestamp', 'organization', 'user', 'get_action_display_with_icon',
        'target_model', 'description', 'ip_address'
    ]
    list_filter = [
        'organization', 'action', 'target_model', 'timestamp'
    ]
    search_fields = [
        'user__username', 'description', 'ip_address'
    ]
    ordering = ['-timestamp']
    readonly_fields = [
        'organization', 'user', 'action', 'target_model', 'target_id',
        'description', 'old_values', 'new_values', 'ip_address',
        'user_agent', 'timestamp', 'formatted_old_values', 'formatted_new_values'
    ]
    
    fieldsets = (
        ('基本情報', {
            'fields': ('timestamp', 'organization', 'user', 'action')
        }),
        ('対象情報', {
            'fields': ('target_model', 'target_id', 'description')
        }),
        ('変更内容', {
            'fields': ('formatted_old_values', 'formatted_new_values'),
            'classes': ('collapse',)
        }),
        ('接続情報', {
            'fields': ('ip_address', 'user_agent'),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        """監査ログは手動作成を禁止"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """監査ログは編集を禁止"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """監査ログは削除を禁止"""
        return False
    
    def get_action_display_with_icon(self, obj):
        """操作種別をアイコン付きで表示"""
        action_icons = {
            'item_create': '🆕',
            'item_update': '✏️',
            'item_delete': '🗑️',
            'inventory_in': '📥',
            'inventory_out': '📤',
            'inventory_adjust': '🔧',
            'order_create': '🛒',
            'order_update': '📝',
            'order_cancel': '❌',
            'user_login': '🔐',
            'user_logout': '🔓',
            'permission_change': '👤',
        }
        icon = action_icons.get(obj.action, '📋')
        return f"{icon} {obj.get_action_display()}"
    get_action_display_with_icon.short_description = '操作種別'
    
    def formatted_old_values(self, obj):
        """変更前データを整形して表示"""
        if not obj.old_values:
            return '-'
        
        import json
        try:
            formatted = json.dumps(obj.old_values, ensure_ascii=False, indent=2)
            return format_html('<pre style="font-size: 12px;">{}</pre>', formatted)
        except:
            return str(obj.old_values)
    formatted_old_values.short_description = '変更前データ'
    
    def formatted_new_values(self, obj):
        """変更後データを整形して表示"""
        if not obj.new_values:
            return '-'
        
        import json
        try:
            formatted = json.dumps(obj.new_values, ensure_ascii=False, indent=2)
            return format_html('<pre style="font-size: 12px;">{}</pre>', formatted)
        except:
            return str(obj.new_values)
    formatted_new_values.short_description = '変更後データ'
    
    def get_queryset(self, request):
        """関連オブジェクトをプリフェッチ"""
        return super().get_queryset(request).select_related('organization', 'user')


# ===== 請求書・納品書発行機能の管理画面 =====

class InvoiceItemInline(admin.TabularInline):
    """請求書明細のインライン"""
    model = InvoiceItem
    extra = 1
    fields = ['item_name', 'item_description', 'quantity', 'unit', 'unit_price', 'amount']
    readonly_fields = ['amount']


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    """請求書管理画面"""
    list_display = [
        'invoice_number', 'bill_to_name', 'organization', 'issue_date', 
        'total_amount', 'status', 'created_by', 'created_at'
    ]
    list_filter = ['organization', 'status', 'issue_date', 'created_at']
    search_fields = ['invoice_number', 'bill_to_name', 'bill_to_contact']
    list_editable = ['status']
    readonly_fields = ['invoice_number', 'subtotal', 'tax_amount', 'total_amount', 'created_at', 'updated_at']
    inlines = [InvoiceItemInline]
    
    fieldsets = (
        ('請求書情報', {
            'fields': ('invoice_number', 'organization', 'order', 'status')
        }),
        ('請求先情報', {
            'fields': ('bill_to_name', 'bill_to_address', 'bill_to_contact', 'bill_to_phone', 'bill_to_email')
        }),
        ('請求内容', {
            'fields': ('issue_date', 'due_date', 'tax_rate', 'subtotal', 'tax_amount', 'total_amount')
        }),
        ('その他', {
            'fields': ('payment_date', 'notes', 'created_by')
        }),
        ('システム情報', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('organization', 'created_by', 'order')


class DeliveryNoteItemInline(admin.TabularInline):
    """納品書明細のインライン"""
    model = DeliveryNoteItem
    extra = 1
    fields = ['item_name', 'item_description', 'quantity', 'unit', 'delivered_quantity']


@admin.register(DeliveryNote)
class DeliveryNoteAdmin(admin.ModelAdmin):
    """納品書管理画面"""
    list_display = [
        'delivery_number', 'deliver_to_name', 'organization', 'issue_date', 
        'delivery_date', 'status', 'created_by', 'created_at'
    ]
    list_filter = ['organization', 'status', 'issue_date', 'delivery_date', 'created_at']
    search_fields = ['delivery_number', 'deliver_to_name', 'deliver_to_contact']
    list_editable = ['status']
    readonly_fields = ['delivery_number', 'created_at', 'updated_at']
    inlines = [DeliveryNoteItemInline]
    
    fieldsets = (
        ('納品書情報', {
            'fields': ('delivery_number', 'organization', 'order', 'invoice', 'status')
        }),
        ('納品先情報', {
            'fields': ('deliver_to_name', 'deliver_to_address', 'deliver_to_contact', 'deliver_to_phone')
        }),
        ('納品内容', {
            'fields': ('issue_date', 'delivery_date', 'actual_delivery_date')
        }),
        ('その他', {
            'fields': ('notes', 'created_by')
        }),
        ('システム情報', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('organization', 'created_by', 'order', 'invoice') 