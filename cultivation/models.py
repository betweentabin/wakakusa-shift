from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator
from django.db.models.signals import post_save
from django.dispatch import receiver

class Crop(models.Model):
    """作物"""
    name = models.CharField("作物名", max_length=100, unique=True)
    color = models.CharField("色コード", max_length=7, default="#808080", help_text="例: #FFFFFF")

    def __str__(self):
        return self.name

class CultivationLayout(models.Model):
    """栽培レイアウト"""
    name = models.CharField("レイアウト名", max_length=100)
    layout_image = models.ImageField("レイアウト図", upload_to='layouts/', blank=True, null=True)
    import_file = models.FileField("インポートファイル", upload_to='imports/', blank=True, null=True, 
                                   help_text="PDF、Excel、画像ファイルをアップロードして自動的にレイアウトを作成")
    created_at = models.DateTimeField("作成日", default=timezone.now)

    def __str__(self):
        return self.name

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
    
    # 状態管理
    is_active = models.BooleanField("使用中", default=True)
    maintenance_notes = models.TextField("メンテナンス備考", blank=True, null=True)
    
    class Meta:
        verbose_name = "棚区画"
        verbose_name_plural = "棚区画"
        unique_together = ('layout', 'x_position', 'y_position')
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
    planting_date = models.DateField("植付日")
    expected_harvest_date = models.DateField("収穫予定日")
    harvest_date = models.DateField("収穫日", blank=True, null=True)
    plot = models.ForeignKey(Plot, on_delete=models.CASCADE, related_name='shelf_crops', verbose_name="棚区画")
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
