from django.contrib import admin
from shift_management.models import Staff, ShiftType, Shift, ShiftTemplate, ShiftTemplateDetail

@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ('name', 'position', 'phone', 'email', 'is_active')
    search_fields = ('name', 'position', 'phone', 'email')
    list_filter = ('is_active', 'position')

@admin.register(ShiftType)
class ShiftTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_time', 'end_time', 'color')
    search_fields = ('name',)

@admin.register(Shift)
class ShiftAdmin(admin.ModelAdmin):
    list_display = ('staff', 'date', 'start_time', 'end_time', 'shift_type')
    search_fields = ('staff__name', 'notes')
    list_filter = ('date', 'shift_type', 'staff')
    date_hierarchy = 'date'

@admin.register(ShiftTemplate)
class ShiftTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active')
    search_fields = ('name', 'description')
    list_filter = ('is_active',)

@admin.register(ShiftTemplateDetail)
class ShiftTemplateDetailAdmin(admin.ModelAdmin):
    list_display = ('template', 'staff', 'weekday', 'shift_type', 'start_time', 'end_time')
    search_fields = ('template__name', 'staff__name')
    list_filter = ('weekday', 'shift_type', 'template')
