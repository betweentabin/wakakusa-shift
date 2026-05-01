"""
cultivation アプリのAPI Serializers
"""
from rest_framework import serializers
from .models import (
    CropProcess,
    CultivationSchedule,
    CropTemplate,
    CropTemplateProcess,
    ShelfCrop,
    Plot,
    Crop,
    ProcessSchedule,
    LaneConfig,
    HolidayConfig,
    Holiday
)


class CropProcessSerializer(serializers.ModelSerializer):
    """栽培工程のSerializer"""

    class Meta:
        model = CropProcess
        fields = ['id', 'organization', 'name', 'code', 'color', 'display_order',
                  'default_duration', 'description', 'is_active']
        read_only_fields = ['id']


class ShelfCropBasicSerializer(serializers.ModelSerializer):
    """棚作物の基本情報Serializer（ネストされた場合に使用）"""
    plot_shelf_number = serializers.CharField(source='plot.shelf_number', read_only=True)
    plot_level = serializers.IntegerField(source='level', read_only=True)

    class Meta:
        model = ShelfCrop
        fields = ['id', 'variety', 'planting_date', 'expected_harvest_date',
                  'plot_shelf_number', 'plot_level']
        read_only_fields = ['id']


class CultivationScheduleSerializer(serializers.ModelSerializer):
    """栽培スケジュールのSerializer"""
    process_detail = CropProcessSerializer(source='process', read_only=True)
    shelf_crop_detail = ShelfCropBasicSerializer(source='shelf_crop', read_only=True)
    duration_days = serializers.IntegerField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = CultivationSchedule
        fields = [
            'id', 'shelf_crop', 'shelf_crop_detail', 'process', 'process_detail',
            'start_date', 'end_date', 'notes', 'is_completed', 'completed_date',
            'duration_days', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'duration_days', 'is_active']

    def validate(self, data):
        """開始日と終了日の妥当性をチェック"""
        if data.get('start_date') and data.get('end_date'):
            if data['start_date'] > data['end_date']:
                raise serializers.ValidationError(
                    "開始日は終了日より前である必要があります。"
                )
        return data


class CropTemplateProcessSerializer(serializers.ModelSerializer):
    """テンプレート工程のSerializer"""
    process_detail = CropProcessSerializer(source='process', read_only=True)

    class Meta:
        model = CropTemplateProcess
        fields = [
            'id', 'template', 'process', 'process_detail',
            'duration_days', 'start_offset_days', 'display_order'
        ]
        read_only_fields = ['id']


class CropTemplateSerializer(serializers.ModelSerializer):
    """栽培テンプレートのSerializer"""
    processes = CropTemplateProcessSerializer(many=True, read_only=True)
    crop_name = serializers.CharField(source='crop.name', read_only=True)

    class Meta:
        model = CropTemplate
        fields = [
            'id', 'crop', 'crop_name', 'name', 'description',
            'is_default', 'processes', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class PlotBasicSerializer(serializers.ModelSerializer):
    """棚の基本情報Serializer"""

    class Meta:
        model = Plot
        fields = ['id', 'shelf_number', 'x_position', 'y_position', 'levels']
        read_only_fields = ['id']


class ShelfCropWithSchedulesSerializer(serializers.ModelSerializer):
    """スケジュール付き棚作物Serializer"""
    schedules = CultivationScheduleSerializer(many=True, read_only=True)
    plot_detail = PlotBasicSerializer(source='plot', read_only=True)

    class Meta:
        model = ShelfCrop
        fields = [
            'id', 'variety', 'planting_date', 'expected_harvest_date',
            'harvest_date', 'level', 'notes', 'plot', 'plot_detail', 'schedules'
        ]
        read_only_fields = ['id']


class ScheduleCreateFromTemplateSerializer(serializers.Serializer):
    """テンプレートからスケジュールを作成するためのSerializer"""
    shelf_crop_id = serializers.IntegerField()
    template_id = serializers.IntegerField()
    start_date = serializers.DateField()

    def validate_shelf_crop_id(self, value):
        """ShelfCropの存在確認"""
        if not ShelfCrop.objects.filter(id=value).exists():
            raise serializers.ValidationError("指定された棚作物が見つかりません。")
        return value

    def validate_template_id(self, value):
        """テンプレートの存在確認"""
        if not CropTemplate.objects.filter(id=value).exists():
            raise serializers.ValidationError("指定されたテンプレートが見つかりません。")
        return value


class ShelfCropSerializer(serializers.ModelSerializer):
    """棚作物のSerializer（CRUD用）"""
    plot_detail = PlotBasicSerializer(source='plot', read_only=True)
    days_until_harvest = serializers.IntegerField(read_only=True)
    growth_progress_percentage = serializers.FloatField(read_only=True)

    class Meta:
        model = ShelfCrop
        fields = [
            'id', 'variety', 'planting_date', 'expected_harvest_date',
            'harvest_date', 'plot', 'plot_detail', 'organization',
            'level', 'notes', 'created_at', 'updated_at',
            'days_until_harvest', 'growth_progress_percentage'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, data):
        """植付日と収穫予定日の妥当性をチェック"""
        if data.get('planting_date') and data.get('expected_harvest_date'):
            if data['planting_date'] > data['expected_harvest_date']:
                raise serializers.ValidationError(
                    "植付日は収穫予定日より前である必要があります。"
                )
        return data


# ==========================================
# ガントチャート機能用シリアライザー
# ==========================================

class ProcessScheduleSerializer(serializers.ModelSerializer):
    """工程スケジュール（ガントチャートの帯）のSerializer"""
    process_detail = CropProcessSerializer(source='process', read_only=True)
    plot_detail = PlotBasicSerializer(source='plot', read_only=True)
    duration_days = serializers.IntegerField(read_only=True)

    class Meta:
        model = ProcessSchedule
        fields = [
            'id', 'organization', 'plot', 'plot_detail', 'level', 'group_name',
            'process', 'process_detail', 'start_date', 'end_date',
            'parent_schedule', 'is_linked', 'notes', 'duration_days',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'duration_days']

    def validate(self, data):
        """開始日と終了日の妥当性をチェック"""
        if data.get('start_date') and data.get('end_date'):
            if data['start_date'] > data['end_date']:
                raise serializers.ValidationError(
                    "開始日は終了日より前である必要があります。"
                )
        return data


class ProcessScheduleMoveSerializer(serializers.Serializer):
    """スケジュール移動用のSerializer"""
    days_offset = serializers.IntegerField(help_text="移動する日数（正で後ろ、負で前）")
    move_children = serializers.BooleanField(default=True, help_text="連携する子スケジュールも移動するか")


class LaneConfigSerializer(serializers.ModelSerializer):
    """レーン設定のSerializer"""
    plot_detail = PlotBasicSerializer(source='plot', read_only=True)

    class Meta:
        model = LaneConfig
        fields = ['id', 'organization', 'plot', 'plot_detail', 'level', 'max_overlap']
        read_only_fields = ['id']


class HolidaySerializer(serializers.ModelSerializer):
    """個別休日のSerializer"""

    class Meta:
        model = Holiday
        fields = ['id', 'holiday_config', 'date', 'name']
        read_only_fields = ['id']


class HolidayConfigSerializer(serializers.ModelSerializer):
    """休日設定のSerializer"""
    holidays = HolidaySerializer(many=True, read_only=True)
    off_days = serializers.ListField(source='get_off_days', read_only=True)

    class Meta:
        model = HolidayConfig
        fields = [
            'id', 'organization', 'sunday_off', 'monday_off', 'tuesday_off',
            'wednesday_off', 'thursday_off', 'friday_off', 'saturday_off',
            'skip_holidays', 'holidays', 'off_days'
        ]
        read_only_fields = ['id']


class GanttDataSerializer(serializers.Serializer):
    """ガントチャート表示用の統合データSerializer"""
    lanes = serializers.ListField(child=serializers.DictField())
    schedules = ProcessScheduleSerializer(many=True)
    processes = CropProcessSerializer(many=True)
    holiday_config = HolidayConfigSerializer(allow_null=True)
    date_range = serializers.DictField()
