from django import forms
from django.db.models import Q
from .models import CultivationLayout, CultivationPlan, CultivationLog, Plot, ShelfCrop, CultivationSection, CropImage, Crop

class CultivationLayoutForm(forms.ModelForm):
    # OCR機能統合フィールド
    enable_ocr = forms.BooleanField(
        required=False,
        initial=False,
        label='OCR機能を使用する',
        help_text='画像から棚番号を自動認識してレイアウトを生成します',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    ocr_file = forms.FileField(
        required=False,
        label='OCR用画像/PDF',
        help_text='棚番号が記載された画像またはPDFファイル（最大10MB）',
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.pdf,.png,.jpg,.jpeg,.tiff,.bmp'
        })
    )
    
    auto_generate_sections = forms.BooleanField(
        required=False,
        initial=True,
        label='区画を自動生成する',
        help_text='OCR結果から栽培区画を自動的に作成します',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    ocr_confidence_threshold = forms.IntegerField(
        required=False,
        initial=70,
        min_value=50,
        max_value=100,
        label='OCR信頼度閾値',
        help_text='この値以上の信頼度を持つテキストのみを使用します（50-100%）',
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': '50',
            'max': '100',
            'step': '5'
        })
    )
    
    class Meta:
        model = CultivationLayout
        fields = ['name', 'layout_image', 'import_file']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '例: 温室A、栽培棟1'
            }),
            'layout_image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
            'import_file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.csv,.xlsx,.json'
            }),
        }
        labels = {
            'name': 'レイアウト名',
            'layout_image': 'レイアウト画像',
            'import_file': 'インポートファイル',
        }
        help_texts = {
            'name': '栽培レイアウトの名前を入力してください',
            'layout_image': '既存のレイアウト画像がある場合にアップロード',
            'import_file': '既存データがある場合にインポート（CSV、Excel、JSON形式）',
        }
    
    def clean_ocr_file(self):
        """OCRファイルのバリデーション"""
        ocr_file = self.cleaned_data.get('ocr_file')
        enable_ocr = self.cleaned_data.get('enable_ocr')
        
        if enable_ocr and not ocr_file:
            raise forms.ValidationError('OCR機能を使用する場合、OCR用ファイルが必要です。')
        
        if ocr_file:
            # ファイルサイズチェック（10MB制限）
            if ocr_file.size > 10 * 1024 * 1024:
                raise forms.ValidationError('ファイルサイズは10MB以下にしてください。')
            
            # ファイル形式チェック
            allowed_extensions = ['.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.bmp']
            file_name = ocr_file.name.lower()
            
            if not any(file_name.endswith(ext) for ext in allowed_extensions):
                raise forms.ValidationError(
                    f'対応ファイル形式: {", ".join(allowed_extensions)}'
                )
        
        return ocr_file
    
    def clean(self):
        """フォーム全体のバリデーション"""
        cleaned_data = super().clean()
        enable_ocr = cleaned_data.get('enable_ocr')
        ocr_file = cleaned_data.get('ocr_file')
        auto_generate_sections = cleaned_data.get('auto_generate_sections')
        
        # OCR機能使用時の必須チェック
        if enable_ocr:
            if not ocr_file:
                self.add_error('ocr_file', 'OCR機能を使用する場合、ファイルをアップロードしてください。')
        
        # OCRファイルがある場合は自動でOCR機能を有効化
        if ocr_file and not enable_ocr:
            cleaned_data['enable_ocr'] = True
        
        return cleaned_data

class CropForm(forms.ModelForm):
    """作物名管理用フォーム"""
    class Meta:
        model = Crop
        fields = ['name', 'color', 'days_to_pre_planting', 'days_to_planting', 'days_to_harvest']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '例: レタス、トマト、バジル'
            }),
            'color': forms.TextInput(attrs={
                'class': 'form-control',
                'type': 'color',
                'value': '#28a745'
            }),
            'days_to_pre_planting': forms.NumberInput(attrs={
                'class': 'form-control', 'min': 0, 'style': 'max-width:100px;'
            }),
            'days_to_planting': forms.NumberInput(attrs={
                'class': 'form-control', 'min': 0, 'style': 'max-width:100px;'
            }),
            'days_to_harvest': forms.NumberInput(attrs={
                'class': 'form-control', 'min': 0, 'style': 'max-width:100px;'
            }),
        }
        labels = {
            'name': '作物名',
            'color': '表示色',
        }
        help_texts = {
            'name': '栽培する作物の名前を入力してください',
            'color': '栽培計画画面で表示される色を選択してください',
        }

class CultivationSectionForm(forms.ModelForm):
    class Meta:
        model = CultivationSection
        fields = ['name', 'row', 'column', 'description']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '例: A-1, B-2'
            }),
            'row': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'placeholder': '行番号'
            }),
            'column': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'placeholder': '列番号'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': '区画の説明（任意）'
            }),
        }

class CultivationPlanForm(forms.ModelForm):
    # 栽培期間を指定するフィールドを追加
    cultivation_period_days = forms.IntegerField(
        label="栽培期間（日数）",
        required=False,
        min_value=1,
        max_value=365,
        help_text="播種日または定植日から収穫予定日までの日数を入力すると、収穫予定日が自動計算されます",
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '例: 30',
            'id': 'cultivation_period_days'
        })
    )
    
    class Meta:
        model = CultivationPlan
        fields = ['crop', 'sowing_date', 'planting_date', 'harvest_date_planned', 'cultivation_period_days', 'notes']
        widgets = {
            'crop': forms.Select(attrs={'class': 'form-select'}),
            'sowing_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date', 'id': 'sowing_date'}),
            'planting_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date', 'id': 'planting_date'}),
            'harvest_date_planned': forms.DateInput(attrs={'class': 'form-control', 'type': 'date', 'id': 'harvest_date_planned'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)
        crop_qs = Crop.objects.all().order_by('name')
        if organization:
            crop_qs = crop_qs.filter(Q(organization=organization) | Q(organization__isnull=True))
        self.fields['crop'].queryset = crop_qs

        if self.instance and self.instance.pk:
            # 編集時に現在の栽培期間を表示
            period = self.instance.growth_period_days()
            if period:
                self.fields['cultivation_period_days'].initial = period
    
    def clean(self):
        cleaned_data = super().clean()
        sowing_date = cleaned_data.get('sowing_date')
        planting_date = cleaned_data.get('planting_date')
        harvest_date_planned = cleaned_data.get('harvest_date_planned')
        cultivation_period_days = cleaned_data.get('cultivation_period_days')
        
        # 栽培期間が指定された場合、収穫予定日を自動計算
        if cultivation_period_days and not harvest_date_planned:
            start_date = planting_date or sowing_date
            if start_date:
                from datetime import timedelta
                calculated_harvest_date = start_date + timedelta(days=cultivation_period_days)
                cleaned_data['harvest_date_planned'] = calculated_harvest_date
        
        return cleaned_data

class CultivationLogForm(forms.ModelForm):
    class Meta:
        model = CultivationLog
        fields = ['status', 'memo', 'log_image']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'}),
            'memo': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'log_image': forms.FileInput(attrs={'class': 'form-control'}),
        }

class PlotForm(forms.ModelForm):
    class Meta:
        model = Plot
        fields = ['shelf_number', 'x_position', 'y_position', 'levels', 'max_plates']
        widgets = {
            'shelf_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '例: A-1, B-2'
            }),
            'x_position': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'placeholder': '横位置 (0から始まる)'
            }),
            'y_position': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'placeholder': '縦位置 (0から始まる)'
            }),
            'levels': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'placeholder': '段数'
            }),
            'max_plates': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'placeholder': '例: 14 または 8'
            }),
        }
        labels = {
            'max_plates': '最大プレート数',
        }
        help_texts = {
            'max_plates': 'このレーン（棚）に入れられるプレートの上限枚数',
        }

class PlotInlineForm(forms.ModelForm):
    """レーンマスター設定用の軽量フォーム（表内インライン編集）"""
    class Meta:
        model = Plot
        fields = ['shelf_number', 'levels', 'max_plates']
        widgets = {
            'shelf_number': forms.TextInput(attrs={
                'class': 'form-control form-control-sm',
                'style': 'width:110px',
            }),
            'levels': forms.NumberInput(attrs={
                'class': 'form-control form-control-sm',
                'style': 'width:70px',
                'min': '1', 'max': '20',
            }),
            'max_plates': forms.NumberInput(attrs={
                'class': 'form-control form-control-sm',
                'style': 'width:70px',
                'min': '1',
            }),
        }


class BulkAddLanesForm(forms.Form):
    """レーン一括追加フォーム"""
    prefix_text = forms.CharField(
        label='棚番号プレフィックス', max_length=20,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '例: A-'}),
    )
    start_number = forms.IntegerField(
        label='開始番号', initial=1, min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
    )
    count = forms.IntegerField(
        label='追加本数', min_value=1, max_value=100,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
    )
    levels = forms.IntegerField(
        label='段数', initial=3, min_value=1, max_value=20,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
    )
    max_plates = forms.IntegerField(
        label='最大プレート数', initial=14, min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
    )


class ShelfCropForm(forms.ModelForm):
    class Meta:
        model = ShelfCrop
        fields = [
            'variety',
            'sowing_date',
            'pre_planting_date',
            'planting_date',
            'expected_harvest_date',
            'harvest_date',
            'plate_count',
            'start_plate',
            'level',
            'notes',
        ]
        widgets = {
            'variety': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '例: レタス, ほうれん草'
            }),
            'sowing_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'pre_planting_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'planting_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'expected_harvest_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'harvest_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'plate_count': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'placeholder': '例: 10'
            }),
            'start_plate': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'placeholder': '例: 1'
            }),
            'level': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'readonly': True,
                'style': 'background-color: #f8f9fa;'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': '備考があれば入力してください'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['level'].required = False

class CropImageForm(forms.ModelForm):
    class Meta:
        model = CropImage
        fields = ['image', 'notes']
        widgets = {
            'image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': '画像の説明（任意）'
            }),
        }


class OCRLayoutForm(forms.ModelForm):
    """OCR機能付きレイアウト作成フォーム"""
    
    ocr_file = forms.FileField(
        label="図面ファイル",
        help_text="PDF、画像ファイル（PNG, JPEG, TIFF）をアップロードして自動解析",
        required=False,
        widget=forms.FileInput(attrs={
            'accept': '.pdf,.png,.jpg,.jpeg,.tiff,.bmp',
            'class': 'form-control'
        })
    )
    
    auto_generate_sections = forms.BooleanField(
        label="区画を自動生成",
        help_text="OCR結果から自動的に区画を作成します",
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    ocr_confidence_threshold = forms.IntegerField(
        label="OCR信頼度閾値",
        help_text="この値以上の信頼度のテキストのみ使用（30-100）",
        min_value=30,
        max_value=100,
        initial=60,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    
    class Meta:
        model = CultivationLayout
        fields = ['name', 'layout_image', 'ocr_file', 'auto_generate_sections', 'ocr_confidence_threshold']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '例: 春季レイアウト2025'
            }),
            'layout_image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
        }
        help_texts = {
            'name': 'レイアウトの名前を入力してください',
            'layout_image': 'レイアウト図をアップロードしてください（PNG, JPG対応）'
        }
        
    def clean_ocr_file(self):
        ocr_file = self.cleaned_data.get('ocr_file')
        if ocr_file:
            # ファイルサイズチェック（10MB制限）
            max_size = 10 * 1024 * 1024  # 10MB
            if ocr_file.size > max_size:
                raise forms.ValidationError("ファイルサイズは10MB以下にしてください。")
            
            # ファイル形式チェック
            allowed_extensions = ['.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.bmp']
            file_name = ocr_file.name.lower()
            if not any(file_name.endswith(ext) for ext in allowed_extensions):
                raise forms.ValidationError("対応していないファイル形式です。PDF、PNG、JPEG、TIFFファイルのみサポートしています。")
        
        return ocr_file 
