from django.contrib import admin
from django.utils import timezone
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.utils.html import format_html
from django.template.response import TemplateResponse
from .models import Staff, ShiftType, Shift, ShiftTemplate, ShiftTemplateDetail


@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'phone', 'position', 'approval_status_display', 'is_active', 'created_at']
    list_filter = ['approval_status', 'is_active', 'created_at', 'approved_at']
    search_fields = ['name', 'email', 'phone']
    readonly_fields = ['created_at', 'updated_at', 'approved_at', 'approved_by']
    
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
            'fields': ('name', 'email', 'phone', 'position', 'is_active')
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