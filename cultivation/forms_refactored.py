"""
Cultivation アプリケーションのリファクタリングされたフォーム
"""
from django import forms
from django.core.exceptions import ValidationError
from datetime import timedelta
from .models import (
    CultivationLayout, CultivationPlan, CultivationLog, Plot, 
    ShelfCrop, CultivationSection, CropImage, Crop
)
from .constants import Limits, Colors

class BootstrapFormMixin:
    """Bootstrapスタイルを適用するミックスイン"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            self.apply_bootstrap_style(field_name, field)
    
    def apply_bootstrap_style(self, field_name, field):
        """フィールドにBootstrapスタイルを適用"""
        widget = field.widget
        
        # 基本的なCSSクラス
        base_classes = {
            forms.TextInput: 'form-control',
            forms.EmailInput: 'form-control',
            forms.NumberInput: 'form-control',
            forms.DateInput: 'form-control',
            forms.TimeInput: 'form-control',
            forms.DateTimeInput: 'form-control',
            forms.Textarea: 'form-control',
            forms.Select: 'form-select',
            forms.FileInput: 'form-control',
            forms.CheckboxInput: 'form-check-input',
            forms.RadioSelect: 'form-check-input',
        }
        
        # ウィジェットタイプに応じてクラスを設定
        for widget_type, css_class in base_classes.items():
            if isinstance(widget, widget_type):
                current_class = widget.attrs.get('class', '')
                if css_class not in current_class:
                    widget.attrs['class'] = f"{current_class} {css_class}".strip()
                break

class ValidationMixin:
    """バリデーション用ミックスイン"""
    
    def clean_name(self):
        """名前フィールドのバリデーション"""
        name = self.cleaned_data.get('name')
        if name:
            name = name.strip()
            if len(name) < 2:
                raise ValidationError("名前は2文字以上で入力してください。")
            if len(name) > Limits.NAME_MAX_LENGTH:
                raise ValidationError(f"名前は{Limits.NAME_MAX_LENGTH}文字以下で入力してください。")
        return name
    
    def clean_description(self):
        """説明フィールドのバリデーション"""
        description = self.cleaned_data.get('description')
        if description:
            description = description.strip()
            if len(description) > Limits.DESCRIPTION_MAX_LENGTH:
                raise ValidationError(f"説明は{Limits.DESCRIPTION_MAX_LENGTH}文字以下で入力してください。")
        return description

class DateValidationMixin:
    """日付バリデーション用ミックスイン"""
    
    def clean(self):
        cleaned_data = super().clean()
        sowing_date = cleaned_data.get('sowing_date')
        planting_date = cleaned_data.get('planting_date')
        harvest_date_planned = cleaned_data.get('harvest_date_planned')
        
        # 日付の論理的な順序をチェック
        if sowing_date and planting_date:
            if sowing_date > planting_date:
                raise ValidationError("播種日は定植日より前である必要があります。")
        
        if planting_date and harvest_date_planned:
            if planting_date > harvest_date_planned:
                raise ValidationError("定植日は収穫予定日より前である必要があります。")
        
        if sowing_date and harvest_date_planned:
            if sowing_date > harvest_date_planned:
                raise ValidationError("播種日は収穫予定日より前である必要があります。")
        
        return cleaned_data

class CultivationLayoutForm(BootstrapFormMixin, ValidationMixin, forms.ModelForm):
    """栽培レイアウトフォーム"""
    
    class Meta:
        model = CultivationLayout
        fields = ['name', 'description', 'layout_image', 'import_file']
        widgets = {
            'name': forms.TextInput(attrs={
                'placeholder': '例: 春季レイアウト2025'
            }),
            'description': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'レイアウトの説明（任意）'
            }),
            'layout_image': forms.FileInput(attrs={
                'accept': 'image/*'
            }),
            'import_file': forms.FileInput(attrs={
                'accept': '.pdf,.xlsx,.xls,.png,.jpg,.jpeg'
            }),
        }
        help_texts = {
            'name': 'レイアウトの名前を入力してください',
            'layout_image': 'レイアウト図をアップロードしてください（PNG, JPG対応）',
            'import_file': 'PDF、Excel、画像ファイルから自動レイアウト作成（任意）'
        }

class CropForm(BootstrapFormMixin, ValidationMixin, forms.ModelForm):
    """作物フォーム"""
    
    class Meta:
        model = Crop
        fields = ['name', 'variety', 'type', 'color', 'cultivation_days', 'description']
        widgets = {
            'name': forms.TextInput(attrs={
                'placeholder': '例: レタス、トマト、バジル'
            }),
            'variety': forms.TextInput(attrs={
                'placeholder': '例: サニーレタス、ミニトマト'
            }),
            'type': forms.Select(),
            'color': forms.TextInput(attrs={
                'type': 'color',
                'value': Colors.DEFAULT_GREEN
            }),
            'cultivation_days': forms.NumberInput(attrs={
                'min': Limits.MIN_CULTIVATION_DAYS,
                'max': Limits.MAX_CULTIVATION_DAYS,
                'placeholder': '例: 30'
            }),
            'description': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': '作物の特徴や注意事項（任意）'
            }),
        }
        help_texts = {
            'name': '栽培する作物の名前を入力してください',
            'variety': '品種名を入力してください（任意）',
            'type': '栽培タイプを選択してください',
            'color': '栽培計画画面で表示される色を選択してください',
            'cultivation_days': '播種/定植から収穫までの標準的な日数',
        }

class CultivationSectionForm(BootstrapFormMixin, ValidationMixin, forms.ModelForm):
    """栽培区画フォーム"""
    
    class Meta:
        model = CultivationSection
        fields = ['name', 'row', 'column', 'description']
        widgets = {
            'name': forms.TextInput(attrs={
                'placeholder': '例: A-1, B-2'
            }),
            'row': forms.NumberInput(attrs={
                'min': 1,
                'placeholder': '行番号'
            }),
            'column': forms.NumberInput(attrs={
                'min': 1,
                'placeholder': '列番号'
            }),
            'description': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': '区画の説明（任意）'
            }),
        }
        help_texts = {
            'name': '区画の識別名を入力してください',
            'row': '行番号（1から始まる）',
            'column': '列番号（1から始まる）',
        }
    
    def clean(self):
        cleaned_data = super().clean()
        row = cleaned_data.get('row')
        column = cleaned_data.get('column')
        
        # 同じレイアウト内での重複チェック（新規作成時）
        if hasattr(self, 'layout') and row and column:
            existing = CultivationSection.objects.filter(
                layout=self.layout,
                row=row,
                column=column
            )
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise ValidationError(f"行{row}列{column}の区画は既に存在します。")
        
        return cleaned_data

class CultivationPlanForm(BootstrapFormMixin, DateValidationMixin, forms.ModelForm):
    """栽培計画フォーム"""
    
    cultivation_period_days = forms.IntegerField(
        label="栽培期間（日数）",
        required=False,
        min_value=Limits.MIN_CULTIVATION_DAYS,
        max_value=Limits.MAX_CULTIVATION_DAYS,
        help_text="播種日または定植日から収穫予定日までの日数を入力すると、収穫予定日が自動計算されます",
        widget=forms.NumberInput(attrs={
            'placeholder': '例: 30',
            'id': 'cultivation_period_days'
        })
    )
    
    class Meta:
        model = CultivationPlan
        fields = [
            'crop', 'sowing_date', 'planting_date', 'harvest_date_planned',
            'cultivation_period_days', 'notes'
        ]
        widgets = {
            'crop': forms.Select(attrs={
                'id': 'crop_select'
            }),
            'sowing_date': forms.DateInput(attrs={
                'type': 'date',
                'id': 'sowing_date'
            }),
            'planting_date': forms.DateInput(attrs={
                'type': 'date',
                'id': 'planting_date'
            }),
            'harvest_date_planned': forms.DateInput(attrs={
                'type': 'date',
                'id': 'harvest_date_planned'
            }),
            'notes': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': '栽培に関するメモ（任意）'
            }),
        }
        help_texts = {
            'crop': '栽培する作物を選択してください',
            'sowing_date': '種をまく日付（任意）',
            'planting_date': '苗を植える日付（任意）',
            'harvest_date_planned': '収穫予定日',
        }
    
    def __init__(self, *args, **kwargs):
        organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)
        
        # 作物の選択肢を設定
        crop_qs = Crop.objects.all().order_by('name')
        if organization:
            from django.db.models import Q
            crop_qs = crop_qs.filter(Q(organization=organization) | Q(organization__isnull=True))
        self.fields['crop'].queryset = crop_qs
        
        # 編集時に現在の栽培期間を表示
        if self.instance and self.instance.pk:
            period = self.instance.growth_period_days
            if period:
                self.fields['cultivation_period_days'].initial = period
    
    def clean(self):
        cleaned_data = super().clean()
        cultivation_period_days = cleaned_data.get('cultivation_period_days')
        harvest_date_planned = cleaned_data.get('harvest_date_planned')
        
        # 栽培期間が指定された場合、収穫予定日を自動計算
        if cultivation_period_days and not harvest_date_planned:
            sowing_date = cleaned_data.get('sowing_date')
            planting_date = cleaned_data.get('planting_date')
            start_date = planting_date or sowing_date
            
            if start_date:
                calculated_harvest_date = start_date + timedelta(days=cultivation_period_days)
                cleaned_data['harvest_date_planned'] = calculated_harvest_date
        
        return cleaned_data

class CultivationLogForm(BootstrapFormMixin, forms.ModelForm):
    """栽培ログフォーム"""
    
    class Meta:
        model = CultivationLog
        fields = ['status', 'memo', 'log_image']
        widgets = {
            'status': forms.Select(),
            'memo': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': '栽培ログのメモ（任意）'
            }),
            'log_image': forms.FileInput(attrs={
                'accept': 'image/*'
            }),
        }
        help_texts = {
            'status': '現在の生育段階を選択してください',
            'log_image': '作物の写真をアップロードしてください（任意）',
        }

class PlotForm(BootstrapFormMixin, ValidationMixin, forms.ModelForm):
    """棚区画フォーム"""
    
    class Meta:
        model = Plot
        fields = ['shelf_number', 'x_position', 'y_position', 'levels']
        widgets = {
            'shelf_number': forms.TextInput(attrs={
                'placeholder': '例: A-1, B-2'
            }),
            'x_position': forms.NumberInput(attrs={
                'min': 0,
                'placeholder': '横位置 (0から始まる)'
            }),
            'y_position': forms.NumberInput(attrs={
                'min': 0,
                'placeholder': '縦位置 (0から始まる)'
            }),
            'levels': forms.NumberInput(attrs={
                'min': 1,
                'placeholder': '段数'
            }),
        }
        help_texts = {
            'shelf_number': '棚の識別番号を入力してください',
            'x_position': 'グリッド表示での横位置',
            'y_position': 'グリッド表示での縦位置',
            'levels': '棚の段数',
        }
    
    def clean(self):
        cleaned_data = super().clean()
        x_position = cleaned_data.get('x_position')
        y_position = cleaned_data.get('y_position')
        
        # 同じ座標の重複チェック
        if x_position is not None and y_position is not None:
            existing = Plot.objects.filter(
                x_position=x_position,
                y_position=y_position
            )
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise ValidationError(f"座標({x_position}, {y_position})の棚は既に存在します。")
        
        return cleaned_data

class ShelfCropForm(BootstrapFormMixin, ValidationMixin, forms.ModelForm):
    """棚栽培作物フォーム"""
    
    class Meta:
        model = ShelfCrop
        fields = ['variety', 'planting_date', 'expected_harvest_date', 'notes']
        widgets = {
            'variety': forms.TextInput(attrs={
                'placeholder': '例: レタス, ほうれん草'
            }),
            'planting_date': forms.DateInput(attrs={
                'type': 'date'
            }),
            'expected_harvest_date': forms.DateInput(attrs={
                'type': 'date'
            }),
            'notes': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': '備考があれば入力してください'
            }),
        }
        help_texts = {
            'variety': '作物の品種名を入力してください',
            'planting_date': '植付けした日付',
            'expected_harvest_date': '収穫予定日',
        }
    
    def clean(self):
        cleaned_data = super().clean()
        planting_date = cleaned_data.get('planting_date')
        expected_harvest_date = cleaned_data.get('expected_harvest_date')
        
        if planting_date and expected_harvest_date:
            if planting_date > expected_harvest_date:
                raise ValidationError("植付日は収穫予定日より前である必要があります。")
        
        return cleaned_data

class CropImageForm(BootstrapFormMixin, forms.ModelForm):
    """作物画像フォーム"""
    
    class Meta:
        model = CropImage
        fields = ['image', 'notes']
        widgets = {
            'image': forms.FileInput(attrs={
                'accept': 'image/*'
            }),
            'notes': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': '画像の説明（任意）'
            }),
        }
        help_texts = {
            'image': '作物の写真をアップロードしてください',
            'notes': '画像の説明や撮影時の状況など',
        }
    
    def clean_image(self):
        image = self.cleaned_data.get('image')
        if image:
            # ファイルサイズチェック（5MB以下）
            if image.size > 5 * 1024 * 1024:
                raise ValidationError("画像ファイルは5MB以下にしてください。")
            
            # ファイル形式チェック
            allowed_types = ['image/jpeg', 'image/png', 'image/gif']
            if hasattr(image, 'content_type') and image.content_type not in allowed_types:
                raise ValidationError("JPEG、PNG、GIF形式の画像ファイルのみ対応しています。")
        
        return image

class BulkSectionCreateForm(BootstrapFormMixin, forms.Form):
    """区画一括作成フォーム"""
    
    rows = forms.IntegerField(
        label="行数",
        min_value=1,
        max_value=20,
        initial=3,
        widget=forms.NumberInput(attrs={
            'placeholder': '例: 3'
        }),
        help_text="作成する行数を入力してください"
    )
    
    columns = forms.IntegerField(
        label="列数",
        min_value=1,
        max_value=20,
        initial=5,
        widget=forms.NumberInput(attrs={
            'placeholder': '例: 5'
        }),
        help_text="作成する列数を入力してください"
    )
    
    name_prefix = forms.CharField(
        label="区画名プレフィックス",
        max_length=10,
        initial="区画",
        widget=forms.TextInput(attrs={
            'placeholder': '例: 区画, A'
        }),
        help_text="区画名の前に付ける文字列"
    )
    
    start_row = forms.IntegerField(
        label="開始行番号",
        min_value=1,
        initial=1,
        widget=forms.NumberInput(attrs={
            'placeholder': '例: 1'
        }),
        help_text="区画番号の開始行"
    )
    
    start_column = forms.IntegerField(
        label="開始列番号",
        min_value=1,
        initial=1,
        widget=forms.NumberInput(attrs={
            'placeholder': '例: 1'
        }),
        help_text="区画番号の開始列"
    )

class SearchForm(BootstrapFormMixin, forms.Form):
    """検索フォーム"""
    
    query = forms.CharField(
        label="検索キーワード",
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'レイアウト名、作物名、区画名で検索...'
        })
    )
    
    status = forms.ChoiceField(
        label="ステータス",
        choices=[
            ('', '全て'),
            ('active', '栽培中'),
            ('harvest_ready', '収穫可能'),
            ('completed', '完了'),
        ],
        required=False
    )
    
    date_from = forms.DateField(
        label="開始日",
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date'
        })
    )
    
    date_to = forms.DateField(
        label="終了日",
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date'
        })
    )
