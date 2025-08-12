"""
Cultivation アプリケーションのリファクタリングされたモデル
"""
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from .models_base import CultivationBaseModel, TimestampedModel, NamedModel
from .constants import Colors, Limits, CropStatus

class CropType(models.TextChoices):
    """作物タイプ"""
    FIELD = 'field', '露地栽培'
    HYDROPONIC = 'hydroponic', '水耕栽培'
    GREENHOUSE = 'greenhouse', '温室栽培'

class Crop(CultivationBaseModel):
    """統合された作物モデル"""
    type = models.CharField(
        "栽培タイプ", 
        max_length=20, 
        choices=CropType.choices,
        default=CropType.FIELD
    )
    variety = models.CharField("品種", max_length=Limits.NAME_MAX_LENGTH, blank=True)
    color = models.CharField(
        "色コード", 
        max_length=7, 
        default=Colors.DEFAULT_GRAY,
        help_text="例: #FFFFFF"
    )
    cultivation_days = models.PositiveIntegerField(
        "栽培期間（日）",
        validators=[
            MinValueValidator(Limits.MIN_CULTIVATION_DAYS),
            MaxValueValidator(Limits.MAX_CULTIVATION_DAYS)
        ],
        blank=True,
        null=True
    )
    
    class Meta:
        verbose_name = "作物"
        verbose_name_plural = "作物"
        unique_together = ('name', 'variety', 'type')
        ordering = ['type', 'name', 'variety']
    
    def __str__(self):
        parts = [self.name]
        if self.variety:
            parts.append(f"({self.variety})")
        if self.type != CropType.FIELD:
            parts.append(f"[{self.get_type_display()}]")
        return " ".join(parts)

class CultivationLayout(CultivationBaseModel):
    """栽培レイアウト"""
    layout_image = models.ImageField(
        "レイアウト図", 
        upload_to='layouts/%Y/%m/', 
        blank=True, 
        null=True
    )
    import_file = models.FileField(
        "インポートファイル", 
        upload_to='imports/%Y/%m/', 
        blank=True, 
        null=True,
        help_text="PDF、Excel、画像ファイルをアップロードして自動的にレイアウトを作成"
    )
    
    class Meta:
        verbose_name = "栽培レイアウト"
        verbose_name_plural = "栽培レイアウト"
    
    def get_statistics(self):
        """レイアウトの統計情報を取得"""
        from django.db.models import Count, Q
        
        return self.sections.aggregate(
            total_sections=Count('id'),
            active_plans=Count(
                'plans',
                filter=Q(
                    plans__crop__isnull=False,
                    plans__harvest_date_actual__isnull=True
                )
            ),
            harvest_ready=Count(
                'plans',
                filter=Q(
                    plans__harvest_date_planned__lte=timezone.now().date(),
                    plans__harvest_date_actual__isnull=True
                )
            )
        )

class CultivationSection(CultivationBaseModel):
    """栽培区画"""
    layout = models.ForeignKey(
        CultivationLayout, 
        on_delete=models.CASCADE, 
        related_name='sections', 
        verbose_name="レイアウト"
    )
    row = models.PositiveIntegerField(
        "行番号", 
        validators=[MinValueValidator(1)], 
        default=1
    )
    column = models.PositiveIntegerField(
        "列番号", 
        validators=[MinValueValidator(1)], 
        default=1
    )
    
    class Meta:
        verbose_name = "栽培区画"
        verbose_name_plural = "栽培区画"
        unique_together = ('layout', 'row', 'column')
        ordering = ['row', 'column']
    
    def get_current_plan(self):
        """現在の栽培計画を取得"""
        return self.plans.filter(harvest_date_actual__isnull=True).first()
    
    def is_occupied(self):
        """区画が使用中かどうか"""
        return self.get_current_plan() is not None

class CultivationPlan(CultivationBaseModel):
    """栽培計画"""
    section = models.ForeignKey(
        CultivationSection, 
        on_delete=models.CASCADE, 
        related_name='plans', 
        verbose_name="区画"
    )
    crop = models.ForeignKey(
        Crop, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name="作物"
    )
    sowing_date = models.DateField("播種日", blank=True, null=True)
    planting_date = models.DateField("定植日", blank=True, null=True)
    harvest_date_actual = models.DateField("収穫日", blank=True, null=True)
    harvest_date_planned = models.DateField("収穫予定日", blank=True, null=True)
    notes = models.TextField("メモ", blank=True)
    
    class Meta:
        verbose_name = "栽培計画"
        verbose_name_plural = "栽培計画"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.section} - {self.crop.name if self.crop else '未設定'}"
    
    @property
    def days_since_sowing(self):
        """播種からの経過日数"""
        if self.sowing_date:
            return (timezone.now().date() - self.sowing_date).days
        return None
    
    @property
    def days_since_planting(self):
        """定植からの経過日数"""
        if self.planting_date:
            return (timezone.now().date() - self.planting_date).days
        return None
    
    @property
    def days_until_harvest(self):
        """収穫予定日までの残り日数"""
        if self.harvest_date_planned:
            return (self.harvest_date_planned - timezone.now().date()).days
        return None
    
    @property
    def days_overdue(self):
        """収穫予定日を過ぎた日数（正の値）"""
        days = self.days_until_harvest
        return max(0, -days) if days is not None else 0
    
    @property
    def growth_period_days(self):
        """栽培期間（播種または定植から収穫予定まで）"""
        start_date = self.planting_date or self.sowing_date
        if start_date and self.harvest_date_planned:
            return (self.harvest_date_planned - start_date).days
        return None
    
    @property
    def growth_progress_percentage(self):
        """成長進捗パーセンテージ"""
        total_days = self.growth_period_days
        if total_days and total_days > 0:
            elapsed_days = self.days_since_planting or self.days_since_sowing
            if elapsed_days is not None:
                return round(min(100, max(0, (elapsed_days / total_days) * 100)), 1)
        return None
    
    @property
    def is_harvest_ready(self):
        """収穫時期かどうか判定"""
        if self.harvest_date_actual:
            return False
        days_until = self.days_until_harvest
        return days_until is not None and days_until <= 0
    
    @property
    def status(self):
        """現在のステータス"""
        if self.harvest_date_actual:
            return CropStatus.HARVESTED
        elif self.is_harvest_ready:
            return CropStatus.HARVEST_READY
        elif self.planting_date:
            return CropStatus.GROWING
        elif self.sowing_date:
            return CropStatus.SEEDED
        else:
            return CropStatus.PLANNING
    
    @property
    def status_display(self):
        """栽培状況の表示用文字列"""
        if self.harvest_date_actual:
            return "収穫済み"
        elif self.is_harvest_ready:
            if self.days_overdue > 0:
                return f"収穫期限超過 ({self.days_overdue}日)"
            else:
                return "収穫可能"
        elif self.days_until_harvest is not None:
            return f"栽培中 (あと{self.days_until_harvest}日)"
        else:
            return "栽培計画中"

class CultivationLog(TimestampedModel):
    """栽培ログ"""
    plan = models.ForeignKey(
        CultivationPlan, 
        on_delete=models.CASCADE, 
        related_name='logs', 
        verbose_name="栽培計画"
    )
    log_date = models.DateTimeField("記録日", default=timezone.now)
    status = models.CharField(
        "生育段階", 
        max_length=20, 
        choices=CropStatus.CHOICES
    )
    memo = models.TextField("メモ", blank=True)
    log_image = models.ImageField(
        "写真", 
        upload_to='logs/%Y/%m/%d/', 
        blank=True, 
        null=True
    )
    
    class Meta:
        verbose_name = "栽培ログ"
        verbose_name_plural = "栽培ログ"
        ordering = ['-log_date']
    
    def __str__(self):
        crop_name = self.plan.crop.name if self.plan.crop else "未設定"
        return f"{crop_name} - {self.get_status_display()} ({self.log_date.strftime('%Y-%m-%d')})"

class Plot(TimestampedModel):
    """水耕栽培の棚区画"""
    shelf_number = models.CharField(
        "棚番号", 
        max_length=20, 
        unique=True
    )
    x_position = models.PositiveIntegerField(
        "X座標", 
        help_text="グリッド表示時の横位置"
    )
    y_position = models.PositiveIntegerField(
        "Y座標", 
        help_text="グリッド表示時の縦位置"
    )
    levels = models.PositiveIntegerField(
        "段数", 
        default=1, 
        validators=[MinValueValidator(1)]
    )
    
    class Meta:
        verbose_name = "棚区画"
        verbose_name_plural = "棚区画"
        unique_together = ('x_position', 'y_position')
        ordering = ['y_position', 'x_position']
    
    def __str__(self):
        return f"{self.shelf_number} ({self.x_position}, {self.y_position})"

class ShelfCrop(TimestampedModel):
    """棚で栽培する作物（既存との互換性のため残す）"""
    variety = models.CharField("品種", max_length=Limits.NAME_MAX_LENGTH)
    planting_date = models.DateField("植付日")
    expected_harvest_date = models.DateField("収穫予定日")
    plot = models.ForeignKey(
        Plot, 
        on_delete=models.CASCADE, 
        related_name='shelf_crops', 
        verbose_name="棚区画"
    )
    notes = models.TextField("備考", blank=True)
    
    class Meta:
        verbose_name = "棚栽培作物"
        verbose_name_plural = "棚栽培作物"
        ordering = ['-planting_date']
    
    def __str__(self):
        return f"{self.variety} - {self.plot.shelf_number}"
    
    @property
    def days_until_harvest(self):
        """収穫までの日数を計算"""
        if self.expected_harvest_date:
            return (self.expected_harvest_date - timezone.now().date()).days
        return None
    
    @property
    def days_overdue(self):
        """収穫予定日を過ぎた日数（正の値）"""
        days = self.days_until_harvest
        return max(0, -days) if days is not None else 0

class CropImage(TimestampedModel):
    """作物の画像"""
    crop = models.ForeignKey(
        ShelfCrop, 
        on_delete=models.CASCADE, 
        related_name='images', 
        verbose_name="作物"
    )
    image = models.ImageField(
        "画像", 
        upload_to='crop_images/%Y/%m/%d/'
    )
    capture_date = models.DateTimeField("撮影日時", default=timezone.now)
    notes = models.TextField("備考", blank=True)
    
    class Meta:
        verbose_name = "作物画像"
        verbose_name_plural = "作物画像"
        ordering = ['-capture_date']
    
    def __str__(self):
        return f"{self.crop.variety} - {self.capture_date.strftime('%Y-%m-%d %H:%M')}"