from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator
from django.db.models.signals import post_save
from django.dispatch import receiver
from shift_management.models import Organization

class Crop(models.Model):
    """作物（品種マスタ）"""
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        verbose_name="組織",
        related_name='crops',
        null=True,
        blank=True,
    )
    name = models.CharField("作物名", max_length=100)
    color = models.CharField("色コード", max_length=7, default="#808080", help_text="例: #FFFFFF")

    # 標準工程日数（播種日を起点に自動計算）
    days_to_pre_planting = models.PositiveIntegerField(
        "播種→仮植 標準日数", default=0, blank=True,
        help_text="播種日から仮植日までの標準日数（0=仮植なし）")
    days_to_planting = models.PositiveIntegerField(
        "播種→定植 標準日数", default=0, blank=True,
        help_text="播種日から定植日までの標準日数（0=未設定）")
    days_to_harvest = models.PositiveIntegerField(
        "播種→収穫 標準日数", default=0, blank=True,
        help_text="播種日から収穫予定日までの標準日数（0=未設定）")

    class Meta:
        verbose_name = "作物"
        verbose_name_plural = "作物"
        unique_together = ['organization', 'name']
        ordering = ['organization', 'name']

    def __str__(self):
        if self.organization:
            return f"{self.name} ({self.organization.name})"
        return self.name

class CultivationLayout(models.Model):
    """栽培レイアウト"""
    name = models.CharField("レイアウト名", max_length=100)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        verbose_name="組織",
        related_name='cultivation_layouts',
        null=True,  # 一時的にnullを許可（マイグレーション用）
        blank=True
    )
    layout_image = models.ImageField("レイアウト図", upload_to='layouts/', blank=True, null=True)
    import_file = models.FileField("インポートファイル", upload_to='imports/', blank=True, null=True,
                                   help_text="PDF、Excel、画像ファイルをアップロードして自動的にレイアウトを作成")
    created_at = models.DateTimeField("作成日", default=timezone.now)

    class Meta:
        unique_together = ['name', 'organization']  # 組織内でレイアウト名はユニーク

    def __str__(self):
        return f"{self.name} ({self.organization.name})"

class CultivationSection(models.Model):
    """栽培区画"""
    layout = models.ForeignKey(CultivationLayout, on_delete=models.CASCADE, related_name='sections', verbose_name="レイアウト")
    name = models.CharField("区画名", max_length=100)
    row = models.PositiveIntegerField("行番号", validators=[MinValueValidator(1)], default=1)
    column = models.PositiveIntegerField("列番号", validators=[MinValueValidator(1)], default=1)
    description = models.TextField("説明", blank=True, null=True)
    created_at = models.DateTimeField("作成日", default=timezone.now)

    class Meta:
        unique_together = ('layout', 'row', 'column')
        ordering = ['row', 'column']

    def __str__(self):
        return self.name

class CultivationPlan(models.Model):
    """栽培計画"""
    section = models.ForeignKey(CultivationSection, on_delete=models.CASCADE, related_name='plans', verbose_name="区画")
    crop = models.ForeignKey(Crop, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="作物")
    sowing_date = models.DateField("播種日", blank=True, null=True)
    planting_date = models.DateField("定植日", blank=True, null=True)
    harvest_date_actual = models.DateField("収穫日", blank=True, null=True)
    harvest_date_planned = models.DateField("収穫予定日", blank=True, null=True)
    notes = models.TextField("メモ", blank=True, null=True)
    created_at = models.DateTimeField("作成日", default=timezone.now)

    def __str__(self):
        return f"{self.section} - {self.crop.name if self.crop else '未設定'}"

    def days_since_sowing(self):
        """播種からの経過日数"""
        if self.sowing_date:
            delta = timezone.now().date() - self.sowing_date
            return delta.days
        return None
    
    def days_since_planting(self):
        """定植からの経過日数"""
        if self.planting_date:
            delta = timezone.now().date() - self.planting_date
            return delta.days
        return None
    
    def days_until_harvest(self):
        """収穫予定日までの残り日数"""
        if self.harvest_date_planned:
            delta = self.harvest_date_planned - timezone.now().date()
            return delta.days
        return None
    
    def days_overdue(self):
        """収穫予定日を過ぎた日数（正の値）"""
        days = self.days_until_harvest()
        if days is not None and days < 0:
            return -days
        return 0
    
    def growth_period_days(self):
        """栽培期間（播種または定植から収穫予定まで）"""
        start_date = self.planting_date or self.sowing_date
        if start_date and self.harvest_date_planned:
            delta = self.harvest_date_planned - start_date
            return delta.days
        return None
    
    def growth_progress_percentage(self):
        """成長進捗パーセンテージ"""
        total_days = self.growth_period_days()
        if total_days and total_days > 0:
            if self.planting_date:
                elapsed_days = self.days_since_planting()
            else:
                elapsed_days = self.days_since_sowing()
            
            if elapsed_days is not None:
                progress = min(100, max(0, (elapsed_days / total_days) * 100))
                return round(progress, 1)
        return None
    
    def is_harvest_ready(self):
        """収穫時期かどうか判定"""
        if self.harvest_date_actual:
            return False  # 既に収穫済み
        days_until = self.days_until_harvest()
        return days_until is not None and days_until <= 0
    
    def status_display(self):
        """栽培状況の表示用文字列"""
        if self.harvest_date_actual:
            return "収穫済み"
        elif self.is_harvest_ready():
            overdue = self.days_overdue()
            if overdue > 0:
                return f"収穫期限超過 ({overdue}日)"
            else:
                return "収穫可能"
        elif self.days_until_harvest() is not None:
            return f"栽培中 (あと{self.days_until_harvest()}日)"
        else:
            return "栽培計画中"

class CultivationLog(models.Model):
    """栽培ログ"""
    plan = models.ForeignKey(CultivationPlan, on_delete=models.CASCADE, related_name='logs', verbose_name="栽培計画")
    log_date = models.DateTimeField("記録日", default=timezone.now)
    
    STATUS_CHOICES = (
        ('sowing', '播種'),
        ('germination', '発芽'),
        ('planting', '定植'),
        ('growing', '成長'),
        ('harvested', '収穫'),
    )
    status = models.CharField("生育段階", max_length=20, choices=STATUS_CHOICES)
    memo = models.TextField("メモ", blank=True, null=True)
    log_image = models.ImageField("写真", upload_to='logs/', blank=True, null=True)

    def __str__(self):
        crop_name = self.plan.crop.name if self.plan.crop else "未設定"
        return f"{crop_name} - {self.get_status_display()} ({self.log_date.strftime('%Y-%m-%d')})"


class Plot(models.Model):
    """水耕栽培の棚区画"""
    layout = models.ForeignKey(CultivationLayout, on_delete=models.CASCADE, related_name='plots', verbose_name="レイアウト", null=True, blank=True)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        verbose_name="組織",
        related_name='plots',
        null=True,  # 一時的にnullを許可（マイグレーション用）
        blank=True
    )
    section = models.OneToOneField(CultivationSection, on_delete=models.CASCADE, related_name='plot', verbose_name="対応区画", null=True, blank=True)
    shelf_number = models.CharField("棚番号", max_length=20)
    x_position = models.PositiveIntegerField("X座標", help_text="グリッド表示時の横位置")
    y_position = models.PositiveIntegerField("Y座標", help_text="グリッド表示時の縦位置")
    levels = models.PositiveIntegerField("段数", default=1, validators=[MinValueValidator(1)])
    
    # 平面図表示用の追加フィールド
    width = models.FloatField("幅(m)", default=1.0, validators=[MinValueValidator(0.1)], help_text="実際の棚の幅（メートル）")
    depth = models.FloatField("奥行(m)", default=0.5, validators=[MinValueValidator(0.1)], help_text="実際の棚の奥行（メートル）")
    height_per_level = models.FloatField("段間隔(m)", default=0.5, validators=[MinValueValidator(0.1)], help_text="各段の高さ間隔（メートル）")
    base_height = models.FloatField("基底高さ(m)", default=0.8, validators=[MinValueValidator(0)], help_text="床からの基本高さ（メートル）")
    
    # SVG平面図での位置座標
    svg_x = models.FloatField("SVG X座標", default=100.0, help_text="2D平面図でのX座標")
    svg_y = models.FloatField("SVG Y座標", default=100.0, help_text="2D平面図でのY座標")
    
    # 3D表示用の位置座標（レイアウト別に調整可能）
    threejs_x = models.FloatField("3D X座標", default=0.0, help_text="3D表示でのX座標（メートル単位）")
    threejs_y = models.FloatField("3D Y座標", default=0.0, help_text="3D表示でのY座標（高さ、メートル単位）")
    threejs_z = models.FloatField("3D Z座標", default=0.0, help_text="3D表示でのZ座標（奥行、メートル単位）")
    
    # レーン容量設定
    max_plates = models.PositiveIntegerField(
        "最大プレート数", default=14,
        help_text="このレーン（棚）に入れられるプレートの最大枚数（例: 14枚 or 8枚）"
    )

    # 状態管理
    is_active = models.BooleanField("使用中", default=True)
    maintenance_notes = models.TextField("メンテナンス備考", blank=True, null=True)
    
    class Meta:
        verbose_name = "棚区画"
        verbose_name_plural = "棚区画"
        unique_together = [
            ('layout', 'x_position', 'y_position'),
            # ('organization', 'shelf_number')  # 一旦コメントアウト（既存データに重複がある可能性）
        ]
        ordering = ['y_position', 'x_position']
    
    def calculate_default_3d_position(self):
        """デフォルトの3D座標を計算（レイアウト内での相対位置に基づく）"""
        if self.layout:
            # レイアウト内の他の棚との相対配置を考慮
            layout_plots = Plot.objects.filter(layout=self.layout).exclude(id=self.id if self.id else 0)
            
            # グリッド座標を3D座標に変換（メートル単位）
            # X座標: 4メートル間隔
            x = (self.x_position - 1) * 4.0
            
            # Z座標: 3メートル間隔  
            z = (self.y_position - 1) * 3.0
            
            # Y座標: 地面からの高さ（通常は0、高架棚の場合は調整）
            y = 0.0
            
            return x, y, z
        else:
            # レイアウトなしの場合はグリッド座標をそのまま使用
            return (self.x_position - 1) * 4.0, 0.0, (self.y_position - 1) * 3.0
    
    def update_3d_position_if_needed(self):
        """3D座標が未設定（デフォルト値）の場合、計算して更新"""
        if self.threejs_x == 0.0 and self.threejs_y == 0.0 and self.threejs_z == 0.0:
            x, y, z = self.calculate_default_3d_position()
            self.threejs_x = x
            self.threejs_y = y  
            self.threejs_z = z
            self.save()

    def __str__(self):
        return f"{self.shelf_number} ({self.x_position}, {self.y_position}) - {self.levels}段"
    
    def total_height(self):
        """総高さを計算"""
        return self.base_height + (self.height_per_level * self.levels)
    
    def get_level_heights(self):
        """各段の高さリストを取得"""
        heights = []
        for level in range(self.levels):
            height = self.base_height + (self.height_per_level * level)
            heights.append(round(height, 2))
        return heights
    
    def get_level_range(self):
        """レベル番号のリストを取得（テンプレート用）"""
        return range(1, self.levels + 1)
    
    def get_crops_by_level(self):
        """段別の作物情報を取得（現在栽培中の作物）"""
        crops_by_level = {}
        for level in range(1, self.levels + 1):
            # harvest_dateフィールドがある場合はそれを使用、ない場合は全ての作物を取得
            if hasattr(self, 'shelf_crops'):
                crops = self.shelf_crops.filter(level=level)
                # harvest_dateフィールドがモデルに存在する場合のみフィルタリング
                if hasattr(self.shelf_crops.model, 'harvest_date'):
                    crops = crops.filter(harvest_date__isnull=True)
                crops = crops.order_by('-planting_date')
            else:
                crops = []
            crops_by_level[level] = list(crops)
        return crops_by_level
    
    def get_status_color(self):
        """管理状況に応じた色を返す"""
        if not self.is_active:
            return '#cccccc'  # 非アクティブ：グレー
        
        # 作物の状況に応じて色分け
        crops = self.shelf_crops.all() if hasattr(self, 'shelf_crops') else []
        if not crops:
            return '#e8f5e9'  # 空き：薄緑
        
        harvest_ready = any(crop.days_until_harvest() is not None and crop.days_until_harvest() <= 0 for crop in crops)
        overdue = any(crop.days_overdue() > 0 for crop in crops)
        
        if overdue:
            return '#ffcdd2'  # 期限超過：薄赤
        elif harvest_ready:
            return '#fff3e0'  # 収穫可能：薄オレンジ
        else:
            return '#e3f2fd'  # 栽培中：薄青
    
    def get_crop_history(self, limit=10):
        """棚の作物履歴を取得"""
        return self.shelf_crops.all().order_by('-created_at')[:limit]
    
    def get_utilization_rate(self):
        """棚の利用率を計算（過去30日間）"""
        from django.utils import timezone
        from datetime import timedelta
        
        thirty_days_ago = timezone.now() - timedelta(days=30)
        total_crops = self.shelf_crops.filter(created_at__gte=thirty_days_ago).count()
        total_capacity = self.levels * 30  # 30日 × 段数
        
        if total_capacity == 0:
            return 0
        
        return min(100, (total_crops / total_capacity) * 100)
    
    def get_productivity_stats(self):
        """生産性統計を取得"""
        from django.utils import timezone
        from datetime import timedelta
        
        now = timezone.now()
        thirty_days_ago = now - timedelta(days=30)
        
        crops = self.shelf_crops.filter(created_at__gte=thirty_days_ago)
        
        stats = {
            'total_plantings': crops.count(),
            'avg_growth_days': 0,
            'successful_harvests': 0,
            'overdue_crops': 0,
        }
        
        if crops.exists():
            growth_days = []
            for crop in crops:
                if crop.expected_harvest_date and crop.planting_date:
                    days = (crop.expected_harvest_date - crop.planting_date).days
                    growth_days.append(days)
                
                if crop.days_overdue() > 0:
                    stats['overdue_crops'] += 1
                elif crop.days_until_harvest() is not None and crop.days_until_harvest() <= 0:
                    stats['successful_harvests'] += 1
            
            if growth_days:
                stats['avg_growth_days'] = sum(growth_days) / len(growth_days)
        
        return stats


class ShelfCrop(models.Model):
    """棚で栽培する作物"""
    variety = models.CharField("品種", max_length=100)
    sowing_date = models.DateField("播種日", blank=True, null=True)
    pre_planting_date = models.DateField("仮植日", blank=True, null=True)
    planting_date = models.DateField("定植日", blank=True, null=True)
    expected_harvest_date = models.DateField("収穫予定日", blank=True, null=True)
    harvest_date = models.DateField("収穫日", blank=True, null=True)
    harvest_quantity = models.DecimalField(
        "収穫量", max_digits=8, decimal_places=2, blank=True, null=True,
        help_text="実際の収穫量")
    harvest_unit = models.CharField(
        "収穫単位", max_length=20, default="kg", blank=True,
        help_text="例: kg, 箱, 束")
    plate_count = models.PositiveIntegerField("プレート数", default=0, help_text="このレーン・段に入れているプレートの枚数")
    plot = models.ForeignKey(Plot, on_delete=models.CASCADE, related_name='shelf_crops', verbose_name="棚区画")
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        verbose_name="組織",
        related_name='shelf_crops',
        null=True,  # 一時的にnullを許可（マイグレーション用）
        blank=True
    )
    level = models.PositiveIntegerField("段数", default=1, validators=[MinValueValidator(1)], help_text="棚の何段目か")
    notes = models.TextField("備考", blank=True, null=True)
    created_at = models.DateTimeField("登録日時", auto_now_add=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)
    
    class Meta:
        verbose_name = "棚栽培作物"
        verbose_name_plural = "棚栽培作物"
        ordering = ['-planting_date']
    
    def __str__(self):
        return f"{self.variety} - {self.plot.shelf_number}"
    
    def days_until_harvest(self):
        """収穫までの日数を計算"""
        if self.expected_harvest_date:
            delta = self.expected_harvest_date - timezone.now().date()
            return delta.days
        return None

    def days_overdue(self):
        """収穫予定日を過ぎた日数（正の値）"""
        days = self.days_until_harvest()
        if days is not None and days < 0:
            return -days
        return 0

    def get_growth_status(self):
        """生育状態を返す: harvested / harvest_ready / planted / pre_planted / sowing / empty"""
        today = timezone.now().date()
        if self.harvest_date:
            return 'harvested'
        if self.expected_harvest_date and self.expected_harvest_date <= today:
            return 'harvest_ready'
        if self.planting_date and self.planting_date <= today:
            return 'planted'
        if self.pre_planting_date and self.pre_planting_date <= today:
            return 'pre_planted'
        if self.sowing_date:
            return 'sowing'
        return 'empty'

    def is_today_action(self):
        """今日が何かの作業日かどうかを返す"""
        today = timezone.now().date()
        return {
            'is_sowing_today': self.sowing_date == today,
            'is_pre_planting_today': self.pre_planting_date == today,
            'is_planting_today': self.planting_date == today,
            'is_harvest_today': self.expected_harvest_date == today,
            'any': (
                self.sowing_date == today or
                self.pre_planting_date == today or
                self.planting_date == today or
                self.expected_harvest_date == today
            ),
        }

    def growth_progress_percentage(self):
        """成長進度をパーセンテージで計算"""
        if not self.expected_harvest_date or not self.planting_date:
            return 0
        
        total_days = (self.expected_harvest_date - self.planting_date).days
        if total_days <= 0:
            return 100
        
        elapsed_days = (timezone.now().date() - self.planting_date).days
        progress = min(100, max(0, (elapsed_days / total_days) * 100))
        return round(progress, 1)


class CultivationAlert(models.Model):
    """栽培アラート通知"""
    TYPE_OVERDUE        = 'overdue'
    TYPE_HARVEST_TODAY  = 'harvest_today'
    TYPE_PLANTING_TODAY = 'planting_today'
    TYPE_SOWING_TODAY   = 'sowing_today'
    TYPE_PRE_TODAY      = 'pre_planting_today'
    TYPE_CHOICES = [
        (TYPE_OVERDUE,        '収穫遅延'),
        (TYPE_HARVEST_TODAY,  '本日収穫予定'),
        (TYPE_PLANTING_TODAY, '本日定植予定'),
        (TYPE_SOWING_TODAY,   '本日播種予定'),
        (TYPE_PRE_TODAY,      '本日仮植予定'),
    ]
    PRIORITY_HIGH   = 'high'
    PRIORITY_NORMAL = 'normal'
    PRIORITY_CHOICES = [
        (PRIORITY_HIGH,   '高'),
        (PRIORITY_NORMAL, '通常'),
    ]

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE,
        related_name='cultivation_alerts', verbose_name='組織',
    )
    alert_type = models.CharField('種別', max_length=30, choices=TYPE_CHOICES)
    priority   = models.CharField('優先度', max_length=10, choices=PRIORITY_CHOICES,
                                  default=PRIORITY_NORMAL)
    alert_date = models.DateField('対象日')
    variety    = models.CharField('品種', max_length=100)
    shelf_number = models.CharField('棚番号', max_length=100, blank=True)
    level      = models.PositiveIntegerField('段数', null=True, blank=True)
    overdue_days = models.IntegerField('遅延日数', default=0)
    message    = models.CharField('メッセージ', max_length=255)
    is_read    = models.BooleanField('既読', default=False)
    shelf_crop = models.ForeignKey(
        'ShelfCrop', on_delete=models.CASCADE,
        null=True, blank=True, related_name='alerts',
    )
    created_at = models.DateTimeField('生成日時', auto_now_add=True)

    class Meta:
        verbose_name = '栽培アラート'
        verbose_name_plural = '栽培アラート'
        ordering = ['-priority', '-alert_date', 'alert_type']
        unique_together = [['organization', 'alert_type', 'alert_date',
                            'shelf_crop']]

    def __str__(self):
        return f"[{self.get_alert_type_display()}] {self.variety} {self.alert_date}"


class HarvestTarget(models.Model):
    """品種×月の収穫目標"""
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        verbose_name="組織",
        related_name='harvest_targets',
    )
    crop_name = models.CharField("品種名", max_length=100)
    year  = models.PositiveIntegerField("年")
    month = models.PositiveIntegerField("月")
    target_quantity = models.DecimalField("目標量", max_digits=10, decimal_places=2)
    unit = models.CharField("単位", max_length=20, default="kg")

    class Meta:
        verbose_name = "収穫目標"
        verbose_name_plural = "収穫目標"
        unique_together = [['organization', 'crop_name', 'year', 'month']]
        ordering = ['year', 'month', 'crop_name']

    def __str__(self):
        return f"{self.crop_name} {self.year}/{self.month:02d} 目標{self.target_quantity}{self.unit}"


class CropImage(models.Model):
    """作物の画像"""
    crop = models.ForeignKey(ShelfCrop, on_delete=models.CASCADE, related_name='images', verbose_name="作物")
    image = models.ImageField("画像", upload_to='crop_images/%Y/%m/%d/')
    capture_date = models.DateTimeField("撮影日時", default=timezone.now)
    notes = models.TextField("備考", blank=True, null=True)
    uploaded_at = models.DateTimeField("アップロード日時", auto_now_add=True)
    
    class Meta:
        verbose_name = "作物画像"
        verbose_name_plural = "作物画像"
        ordering = ['-capture_date']
    
    def __str__(self):
        return f"{self.crop.variety} - {self.capture_date.strftime('%Y-%m-%d %H:%M')}"


# ==========================================
# スケジュール管理モデル
# ==========================================

class CropProcess(models.Model):
    """作物の栽培工程マスター"""
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        verbose_name="組織",
        related_name='crop_processes',
        null=True,
        blank=True,
        help_text="nullの場合は全組織共通"
    )
    name = models.CharField("工程名", max_length=50)
    code = models.CharField("工程コード", max_length=20)
    color = models.CharField("表示色", max_length=7, default="#808080", help_text="例: #4CAF50")
    display_order = models.PositiveIntegerField("表示順", default=0)
    default_duration = models.PositiveIntegerField("デフォルト期間", default=7, help_text="日数")
    description = models.TextField("説明", blank=True)
    is_active = models.BooleanField("有効", default=True)

    class Meta:
        verbose_name = "栽培工程"
        verbose_name_plural = "栽培工程"
        ordering = ['display_order']
        unique_together = ['organization', 'code']

    def __str__(self):
        return self.name


class CultivationSchedule(models.Model):
    """栽培スケジュール - 各工程の期間を管理"""
    shelf_crop = models.ForeignKey(
        ShelfCrop,
        on_delete=models.CASCADE,
        related_name='schedules',
        verbose_name="棚作物"
    )
    process = models.ForeignKey(
        CropProcess,
        on_delete=models.CASCADE,
        verbose_name="工程"
    )
    start_date = models.DateField("開始日")
    end_date = models.DateField("終了日")
    notes = models.TextField("備考", blank=True)
    is_completed = models.BooleanField("完了", default=False)
    completed_date = models.DateField("完了日", null=True, blank=True)
    created_at = models.DateTimeField("作成日時", auto_now_add=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)

    class Meta:
        verbose_name = "栽培スケジュール"
        verbose_name_plural = "栽培スケジュール"
        ordering = ['start_date', 'process__display_order']

    def __str__(self):
        return f"{self.shelf_crop.variety} - {self.process.name} ({self.start_date})"

    def duration_days(self):
        """工程の期間（日数）"""
        return (self.end_date - self.start_date).days + 1

    def is_active(self):
        """現在進行中の工程かどうか"""
        today = timezone.now().date()
        return self.start_date <= today <= self.end_date and not self.is_completed


class CropTemplate(models.Model):
    """作物の標準栽培テンプレート"""
    crop = models.ForeignKey(
        Crop,
        on_delete=models.CASCADE,
        related_name='templates',
        verbose_name="作物"
    )
    name = models.CharField("テンプレート名", max_length=100)
    description = models.TextField("説明", blank=True)
    is_default = models.BooleanField("デフォルト", default=False)
    created_at = models.DateTimeField("作成日時", auto_now_add=True)

    class Meta:
        verbose_name = "栽培テンプレート"
        verbose_name_plural = "栽培テンプレート"
        unique_together = ['crop', 'name']

    def __str__(self):
        return f"{self.crop.name} - {self.name}"


class CropTemplateProcess(models.Model):
    """テンプレートに含まれる工程"""
    template = models.ForeignKey(
        CropTemplate,
        on_delete=models.CASCADE,
        related_name='processes',
        verbose_name="テンプレート"
    )
    process = models.ForeignKey(
        CropProcess,
        on_delete=models.CASCADE,
        verbose_name="工程"
    )
    duration_days = models.PositiveIntegerField("標準日数")
    start_offset_days = models.PositiveIntegerField("開始オフセット日数", default=0)
    display_order = models.PositiveIntegerField("表示順", default=0)

    class Meta:
        verbose_name = "テンプレート工程"
        verbose_name_plural = "テンプレート工程"
        ordering = ['display_order']

    def __str__(self):
        return f"{self.template.name} - {self.process.name}"


# ==========================================
# ガントチャート機能用モデル
# ==========================================

class ProcessSchedule(models.Model):
    """工程スケジュール（ガントチャートの帯）"""
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        verbose_name="組織",
        related_name='process_schedules'
    )
    plot = models.ForeignKey(
        Plot,
        on_delete=models.CASCADE,
        verbose_name="棚",
        related_name='process_schedules'
    )
    level = models.PositiveIntegerField("段", null=True, blank=True, help_text="nullなら棚全体")
    group_name = models.CharField("グループ名", max_length=100, blank=True, help_text="任意のグループ名")

    process = models.ForeignKey(
        CropProcess,
        on_delete=models.CASCADE,
        verbose_name="工程",
        related_name='process_schedules'
    )
    start_date = models.DateField("開始日")
    end_date = models.DateField("終了日")

    # 連携設定
    parent_schedule = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='child_schedules',
        verbose_name="親スケジュール"
    )
    is_linked = models.BooleanField("連携有効", default=True, help_text="前後の工程と連携して移動するか")

    # メモ・備考
    notes = models.TextField("備考", blank=True)

    created_at = models.DateTimeField("作成日時", auto_now_add=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)

    class Meta:
        verbose_name = "工程スケジュール"
        verbose_name_plural = "工程スケジュール"
        ordering = ['plot', 'level', 'start_date']

    def __str__(self):
        level_str = f"-{self.level}段" if self.level else ""
        return f"{self.plot.shelf_number}{level_str} {self.process.name} ({self.start_date}〜{self.end_date})"

    def duration_days(self):
        """期間（日数）"""
        return (self.end_date - self.start_date).days + 1

    def move_schedule(self, days_offset, move_children=True):
        """スケジュールを移動（連携する子スケジュールも移動）"""
        from datetime import timedelta
        self.start_date += timedelta(days=days_offset)
        self.end_date += timedelta(days=days_offset)
        self.save()

        if move_children and self.is_linked:
            for child in self.child_schedules.filter(is_linked=True):
                child.move_schedule(days_offset, move_children=True)


class LaneConfig(models.Model):
    """レーン（棚/グループ）の設定"""
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        verbose_name="組織",
        related_name='lane_configs'
    )
    plot = models.ForeignKey(
        Plot,
        on_delete=models.CASCADE,
        verbose_name="棚",
        related_name='lane_configs'
    )
    level = models.PositiveIntegerField("段", null=True, blank=True, help_text="nullなら棚全体のデフォルト")

    max_overlap = models.PositiveIntegerField("最大重ね本数", default=1, help_text="1=重ね禁止")

    class Meta:
        verbose_name = "レーン設定"
        verbose_name_plural = "レーン設定"
        unique_together = ['organization', 'plot', 'level']

    def __str__(self):
        level_str = f"-{self.level}段" if self.level else ""
        return f"{self.plot.shelf_number}{level_str} (最大{self.max_overlap}本)"


class HolidayConfig(models.Model):
    """休日・非稼働日設定（曜日ベース）"""
    organization = models.OneToOneField(
        Organization,
        on_delete=models.CASCADE,
        verbose_name="組織",
        related_name='holiday_config'
    )

    sunday_off = models.BooleanField("日曜休み", default=True)
    monday_off = models.BooleanField("月曜休み", default=False)
    tuesday_off = models.BooleanField("火曜休み", default=False)
    wednesday_off = models.BooleanField("水曜休み", default=False)
    thursday_off = models.BooleanField("木曜休み", default=False)
    friday_off = models.BooleanField("金曜休み", default=False)
    saturday_off = models.BooleanField("土曜休み", default=True)

    # 休日をスキップするかどうか
    skip_holidays = models.BooleanField("休日スキップ", default=False, help_text="工程期間計算時に休日を除外するか")

    class Meta:
        verbose_name = "休日設定"
        verbose_name_plural = "休日設定"

    def __str__(self):
        return f"{self.organization.name}の休日設定"

    def get_off_days(self):
        """休みの曜日リスト（0=月曜, 6=日曜）を返す"""
        off_days = []
        if self.monday_off:
            off_days.append(0)
        if self.tuesday_off:
            off_days.append(1)
        if self.wednesday_off:
            off_days.append(2)
        if self.thursday_off:
            off_days.append(3)
        if self.friday_off:
            off_days.append(4)
        if self.saturday_off:
            off_days.append(5)
        if self.sunday_off:
            off_days.append(6)
        return off_days

    def is_holiday(self, date):
        """指定日が休日かどうか"""
        # 曜日チェック
        if date.weekday() in self.get_off_days():
            return True
        # 個別休日チェック
        return self.holidays.filter(date=date).exists()


class Holiday(models.Model):
    """個別の休日"""
    holiday_config = models.ForeignKey(
        HolidayConfig,
        on_delete=models.CASCADE,
        verbose_name="休日設定",
        related_name='holidays'
    )
    date = models.DateField("日付")
    name = models.CharField("名称", max_length=100, blank=True, help_text="祝日名など")

    class Meta:
        verbose_name = "個別休日"
        verbose_name_plural = "個別休日"
        unique_together = ['holiday_config', 'date']
        ordering = ['date']

    def __str__(self):
        return f"{self.date} {self.name}"


# シグナル: 区画作成時に自動的に対応する棚を作成
@receiver(post_save, sender=CultivationSection)
def create_plot_for_section(sender, instance, created, **kwargs):
    """区画作成時に対応する棚を自動作成"""
    if created:
        # 区画名に基づいて棚番号を生成
        shelf_number = f"棚-{instance.name}"

        # 対応する棚を作成
        Plot.objects.create(
            layout=instance.layout,
            section=instance,
            shelf_number=shelf_number,
            x_position=instance.column,  # 区画の列番号を使用
            y_position=instance.row,     # 区画の行番号を使用
            levels=3,  # デフォルトで3段
            width=1.2,
            depth=0.6,
            height_per_level=0.4,
            base_height=0.8,
            svg_x=50 + (instance.column - 1) * 120,  # 区画位置に基づく
            svg_y=50 + (instance.row - 1) * 80
        )
