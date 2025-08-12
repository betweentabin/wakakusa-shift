from django.contrib import admin
from django.utils.html import format_html
from .models import CultivationLayout, CultivationSection, CultivationPlan, CultivationLog, Crop, Plot, ShelfCrop, CropImage

@admin.register(Crop)
class CropAdmin(admin.ModelAdmin):
    list_display = ('name', 'color')
    search_fields = ('name',)

@admin.register(CultivationLayout)
class CultivationLayoutAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')
    search_fields = ('name',)

@admin.register(CultivationSection)
class CultivationSectionAdmin(admin.ModelAdmin):
    list_display = ('name', 'layout', 'row', 'column', 'created_at')
    list_filter = ('layout',)
    search_fields = ('name',)

@admin.register(CultivationPlan)
class CultivationPlanAdmin(admin.ModelAdmin):
    list_display = ('crop', 'section', 'sowing_date', 'planting_date', 'harvest_date_planned')
    list_filter = ('section__layout', 'section', 'crop')
    search_fields = ('crop__name',)
    date_hierarchy = 'created_at'

@admin.register(CultivationLog)
class CultivationLogAdmin(admin.ModelAdmin):
    list_display = ('plan', 'status', 'log_date')
    list_filter = ('status', 'plan__section__layout')
    search_fields = ('plan__crop__name',)
    date_hierarchy = 'log_date'


class CropImageInline(admin.TabularInline):
    model = CropImage
    extra = 1
    fields = ('image', 'capture_date', 'notes')
    readonly_fields = ('image_preview',)
    
    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-height: 100px;"/>', obj.image.url)
        return "画像なし"
    image_preview.short_description = "プレビュー"


@admin.register(Plot)
class PlotAdmin(admin.ModelAdmin):
    list_display = ('shelf_number', 'layout', 'x_position', 'y_position', 'levels', 'get_3d_position', 'get_current_crop')
    list_filter = ('layout', 'levels', 'is_active')
    search_fields = ('shelf_number',)
    ordering = ('layout', 'y_position', 'x_position')
    
    fieldsets = (
        ('基本情報', {
            'fields': ('layout', 'section', 'shelf_number', 'is_active')
        }),
        ('グリッド位置', {
            'fields': ('x_position', 'y_position')
        }),
        ('物理的な寸法', {
            'fields': ('width', 'depth', 'levels', 'height_per_level', 'base_height')
        }),
        ('2D平面図座標', {
            'fields': ('svg_x', 'svg_y'),
            'classes': ('collapse',)
        }),
        ('3D表示座標', {
            'fields': ('threejs_x', 'threejs_y', 'threejs_z'),
            'description': '3D表示での位置座標（メートル単位）。レイアウトごとに調整できます。'
        }),
        ('その他', {
            'fields': ('maintenance_notes',),
            'classes': ('collapse',)
        }),
    )
    
    def get_current_crop(self, obj):
        current_crop = obj.shelf_crops.first()
        if current_crop:
            return f"{current_crop.variety} (植付: {current_crop.planting_date})"
        return "空き"
    get_current_crop.short_description = "現在の作物"
    
    def get_3d_position(self, obj):
        return f"({obj.threejs_x:.1f}, {obj.threejs_y:.1f}, {obj.threejs_z:.1f})"
    get_3d_position.short_description = "3D座標"


@admin.register(ShelfCrop)
class ShelfCropAdmin(admin.ModelAdmin):
    list_display = ('variety', 'plot', 'planting_date', 'expected_harvest_date', 'days_until_harvest', 'image_count')
    list_filter = ('planting_date', 'expected_harvest_date', 'plot')
    search_fields = ('variety', 'plot__shelf_number')
    date_hierarchy = 'planting_date'
    inlines = [CropImageInline]
    readonly_fields = ('created_at', 'updated_at', 'days_until_harvest')
    
    fieldsets = (
        ('基本情報', {
            'fields': ('variety', 'plot')
        }),
        ('日付情報', {
            'fields': ('planting_date', 'expected_harvest_date', 'days_until_harvest')
        }),
        ('その他', {
            'fields': ('notes', 'created_at', 'updated_at')
        }),
    )
    
    def image_count(self, obj):
        count = obj.images.count()
        return f"{count}枚"
    image_count.short_description = "画像数"


@admin.register(CropImage)
class CropImageAdmin(admin.ModelAdmin):
    list_display = ('crop', 'capture_date', 'image_preview', 'notes')
    list_filter = ('capture_date', 'crop__variety')
    search_fields = ('crop__variety', 'notes')
    date_hierarchy = 'capture_date'
    readonly_fields = ('uploaded_at', 'image_preview_large')
    
    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-height: 50px;"/>', obj.image.url)
        return "画像なし"
    image_preview.short_description = "サムネイル"
    
    def image_preview_large(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-width: 500px;"/>', obj.image.url)
        return "画像なし"
    image_preview_large.short_description = "画像プレビュー"
