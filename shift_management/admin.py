from django.contrib import admin
from django.utils import timezone
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.utils.html import format_html
from django.template.response import TemplateResponse
from .models import (
    Staff, ShiftType, Shift, ShiftTemplate, ShiftTemplateDetail,
    LeaveRequest, ShiftProposal, StaffCompatibility, Holiday, Event, EventParticipant
)


@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ['name', 'role_type_display', 'email', 'phone', 'position', 'approval_status_display', 'is_active', 'created_at']
    list_filter = ['role_type', 'approval_status', 'is_active', 'created_at', 'approved_at']
    search_fields = ['name', 'email', 'phone']
    readonly_fields = ['created_at', 'updated_at', 'approved_at', 'approved_by']
    
    def role_type_display(self, obj):
        """権限種別をアイコン付きで表示"""
        return obj.get_role_display_with_icon()
    role_type_display.short_description = '権限種別'
    
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
    
    fieldsets = (
        ('基本情報', {
            'fields': ('name', 'email', 'phone', 'position', 'role_type', 'is_active')
        }),
        ('承認情報', {
            'fields': ('approval_status', 'approved_at', 'approved_by', 'rejection_reason')
        }),
        ('ユーザーアカウント', {
            'fields': ('user',),
            'classes': ('collapse',)
        }),
        ('システム情報', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['approve_staff', 'reject_staff']
    
    def approve_staff(self, request, queryset):
        """スタッフを承認する"""
        updated = 0
        for staff in queryset:
            if staff.approval_status == 'pending':
                staff.approval_status = 'approved'
                staff.approved_at = timezone.now()
                staff.approved_by = request.user
                staff.rejection_reason = ''  # 却下理由をクリア
                staff.save()
                updated += 1
        
        if updated:
            messages.success(request, f'{updated}件のスタッフを承認しました。')
        else:
            messages.warning(request, '承認待ちのスタッフが選択されていません。')
    
    approve_staff.short_description = '選択されたスタッフを承認する'
    
    def reject_staff(self, request, queryset):
        """スタッフを却下する"""
        updated = 0
        for staff in queryset:
            if staff.approval_status == 'pending':
                staff.approval_status = 'rejected'
                staff.approved_at = None
                staff.approved_by = None
                staff.save()
                updated += 1
        
        if updated:
            messages.success(request, f'{updated}件のスタッフを却下しました。')
        else:
            messages.warning(request, '承認待ちのスタッフが選択されていません。')
    
    reject_staff.short_description = '選択されたスタッフを却下する'
    
    def get_queryset(self, request):
        """承認待ちのスタッフを優先表示"""
        qs = super().get_queryset(request)
        return qs.order_by('approval_status', '-created_at')


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
    list_display = ['staff', 'request_type', 'start_date', 'end_date', 'priority_display', 'approval_status_display', 'created_at']
    list_filter = ['request_type', 'priority', 'approval_status', 'created_at']
    search_fields = ['staff__name', 'reason']
    date_hierarchy = 'start_date'
    readonly_fields = ['created_at', 'updated_at', 'approved_at', 'approved_by']
    
    def priority_display(self, obj):
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
        if obj.approval_status == 'pending':
            return format_html('<span style="color: orange; font-weight: bold;">🕐 承認待ち</span>')
        elif obj.approval_status == 'approved':
            return format_html('<span style="color: green; font-weight: bold;">✅ 承認済み</span>')
        elif obj.approval_status == 'rejected':
            return format_html('<span style="color: red; font-weight: bold;">❌ 却下</span>')
        return obj.approval_status
    approval_status_display.short_description = '承認状態'
    
    actions = ['approve_requests', 'reject_requests']
    
    def approve_requests(self, request, queryset):
        updated = 0
        for leave_request in queryset:
            if leave_request.approval_status == 'pending':
                leave_request.approval_status = 'approved'
                leave_request.approved_at = timezone.now()
                leave_request.approved_by = request.user
                leave_request.rejection_reason = ''
                leave_request.save()
                updated += 1
        if updated:
            messages.success(request, f'{updated}件の休み申請を承認しました。')
    approve_requests.short_description = '選択された申請を承認する'
    
    def reject_requests(self, request, queryset):
        updated = 0
        for leave_request in queryset:
            if leave_request.approval_status == 'pending':
                leave_request.approval_status = 'rejected'
                leave_request.approved_at = None
                leave_request.approved_by = None
                leave_request.save()
                updated += 1
        if updated:
            messages.success(request, f'{updated}件の休み申請を却下しました。')
    reject_requests.short_description = '選択された申請を却下する'


@admin.register(ShiftProposal)
class ShiftProposalAdmin(admin.ModelAdmin):
    list_display = ['proposed_to', 'shift_date', 'start_time', 'end_time', 'status_display', 'proposed_by_user', 'created_at']
    list_filter = ['status', 'shift_date', 'shift_type']
    search_fields = ['proposed_to__name', 'proposed_by__username']
    date_hierarchy = 'shift_date'
    readonly_fields = ['created_at', 'updated_at', 'responded_at']
    
    def status_display(self, obj):
        colors = {'pending': '#ffc107', 'accepted': '#28a745', 'declined': '#dc3545', 'expired': '#6c757d'}
        icons = {'pending': '🕐', 'accepted': '✅', 'declined': '❌', 'expired': '⏰'}
        color = colors.get(obj.status, '#6c757d')
        icon = icons.get(obj.status, '🕐')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} {}</span>',
            color, icon, obj.get_status_display()
        )
    status_display.short_description = '回答状況'
    
    def proposed_by_user(self, obj):
        return obj.proposed_by.username
    proposed_by_user.short_description = '打診者'


@admin.register(StaffCompatibility)
class StaffCompatibilityAdmin(admin.ModelAdmin):
    list_display = ['staff1', 'staff2', 'compatibility_display', 'set_by_user', 'created_at']
    list_filter = ['compatibility_level', 'created_at']
    search_fields = ['staff1__name', 'staff2__name']
    
    def compatibility_display(self, obj):
        colors = {1: '#dc3545', 2: '#ffc107', 3: '#6c757d', 4: '#28a745'}
        icons = {1: '❌', 2: '⚠️', 3: '➖', 4: '✅'}
        color = colors.get(obj.compatibility_level, '#6c757d')
        icon = icons.get(obj.compatibility_level, '➖')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} {}</span>',
            color, icon, obj.get_compatibility_level_display()
        )
    compatibility_display.short_description = '相性レベル'
    
    def set_by_user(self, obj):
        return obj.set_by.username
    set_by_user.short_description = '設定者'


@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    list_display = ['date', 'name', 'holiday_type_display', 'is_active']
    list_filter = ['holiday_type', 'is_active', 'date']
    search_fields = ['name']
    date_hierarchy = 'date'
    
    def holiday_type_display(self, obj):
        colors = {'national': '#dc3545', 'company': '#007bff', 'regional': '#28a745'}
        color = colors.get(obj.holiday_type, '#6c757d')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.get_holiday_type_display()
        )
    holiday_type_display.short_description = '祝日種別'


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ['title', 'event_type', 'start_datetime', 'end_datetime', 'location', 'created_by_user']
    list_filter = ['event_type', 'start_datetime']
    search_fields = ['title', 'description', 'location']
    date_hierarchy = 'start_datetime'
    readonly_fields = ['created_at', 'updated_at']
    
    def created_by_user(self, obj):
        return obj.created_by.username
    created_by_user.short_description = '作成者'


@admin.register(EventParticipant)
class EventParticipantAdmin(admin.ModelAdmin):
    list_display = ['event', 'staff', 'status_display', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['event__title', 'staff__name']
    
    def status_display(self, obj):
        colors = {'invited': '#ffc107', 'accepted': '#28a745', 'declined': '#dc3545', 'maybe': '#6c757d'}
        icons = {'invited': '📧', 'accepted': '✅', 'declined': '❌', 'maybe': '❓'}
        color = colors.get(obj.status, '#6c757d')
        icon = icons.get(obj.status, '📧')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} {}</span>',
            color, icon, obj.get_status_display()
        )
    status_display.short_description = '参加状況' 