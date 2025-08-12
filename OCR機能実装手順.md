# OCR機能実装手順書

## 概要

水耕栽培管理システムに図面解析・OCR機能を追加し、アップロードされた図面から自動的に棚レイアウトを認識・生成する機能を実装します。

## 機能要件

### 1. 図面解析機能
- PDF/画像の図面をアップロード
- 棚の位置、サイズ、番号を自動認識
- 寸法や注釈テキストの抽出
- レイアウト情報の自動生成

### 2. OCR対応ファイル形式
- **画像ファイル**: PNG, JPEG, JPG, TIFF, BMP
- **PDFファイル**: 単一ページ・複数ページ対応
- **CADファイル**: DXF形式（将来対応）

### 3. 認識対象要素
- 棚番号（テキスト）
- 棚の形状・位置（矩形検出）
- 寸法線・注釈
- グリッド線・座標系

## 実装手順

### Phase 1: 環境準備・ライブラリインストール

#### 1.1 必要ライブラリのインストール

```bash
# OCR関連ライブラリ
pip install pytesseract
pip install opencv-python
pip install Pillow
pip install pdf2image
pip install numpy

# 画像処理・解析ライブラリ
pip install scikit-image
pip install matplotlib

# テキスト処理
pip install python-levenshtein
pip install fuzzywuzzy
```

#### 1.2 Tesseract OCRエンジンのインストール

**macOS:**
```bash
brew install tesseract
brew install tesseract-lang
```

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install tesseract-ocr
sudo apt-get install tesseract-ocr-jpn
```

#### 1.3 Poppler（PDF処理用）のインストール

**macOS:**
```bash
brew install poppler
```

**Ubuntu/Debian:**
```bash
sudo apt-get install poppler-utils
```

### Phase 2: OCRモジュールの作成

#### 2.1 OCRユーティリティモジュール作成

```python
# cultivation/ocr_utils.py
import cv2
import numpy as np
import pytesseract
from PIL import Image
import pdf2image
import re
from typing import List, Dict, Tuple, Optional

class DocumentOCR:
    """図面・文書のOCR処理クラス"""
    
    def __init__(self):
        # Tesseractの設定
        self.tesseract_config = '--oem 3 --psm 6 -l jpn+eng'
        
    def process_uploaded_file(self, file_path: str) -> Dict:
        """アップロードされたファイルを処理"""
        file_extension = file_path.lower().split('.')[-1]
        
        if file_extension == 'pdf':
            return self.process_pdf(file_path)
        elif file_extension in ['png', 'jpg', 'jpeg', 'tiff', 'bmp']:
            return self.process_image(file_path)
        else:
            raise ValueError(f"未対応のファイル形式: {file_extension}")
    
    def process_pdf(self, pdf_path: str) -> Dict:
        """PDFファイルの処理"""
        try:
            # PDFを画像に変換
            pages = pdf2image.convert_from_path(pdf_path, dpi=300)
            results = []
            
            for i, page in enumerate(pages):
                page_result = self.process_pil_image(page)
                page_result['page_number'] = i + 1
                results.append(page_result)
            
            return {
                'success': True,
                'pages': results,
                'total_pages': len(pages)
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def process_image(self, image_path: str) -> Dict:
        """画像ファイルの処理"""
        try:
            image = Image.open(image_path)
            result = self.process_pil_image(image)
            return {
                'success': True,
                'pages': [result],
                'total_pages': 1
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def process_pil_image(self, pil_image: Image.Image) -> Dict:
        """PIL画像の処理"""
        # OpenCV形式に変換
        cv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
        
        # 前処理
        processed_image = self.preprocess_image(cv_image)
        
        # OCR実行
        ocr_result = self.extract_text(processed_image)
        
        # 図形検出
        shapes = self.detect_shapes(processed_image)
        
        # 棚情報の抽出
        shelf_info = self.extract_shelf_information(ocr_result, shapes)
        
        return {
            'ocr_text': ocr_result,
            'shapes': shapes,
            'shelf_info': shelf_info,
            'image_size': pil_image.size
        }
    
    def preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """画像の前処理"""
        # グレースケール変換
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # ノイズ除去
        denoised = cv2.fastNlMeansDenoising(gray)
        
        # コントラスト強化
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        enhanced = clahe.apply(denoised)
        
        # 二値化
        _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        return binary
    
    def extract_text(self, image: np.ndarray) -> List[Dict]:
        """テキスト抽出"""
        try:
            # OCR実行（詳細情報付き）
            data = pytesseract.image_to_data(image, config=self.tesseract_config, output_type=pytesseract.Output.DICT)
            
            texts = []
            for i in range(len(data['text'])):
                if int(data['conf'][i]) > 30:  # 信頼度30%以上
                    text = data['text'][i].strip()
                    if text:
                        texts.append({
                            'text': text,
                            'confidence': int(data['conf'][i]),
                            'bbox': {
                                'x': data['left'][i],
                                'y': data['top'][i],
                                'width': data['width'][i],
                                'height': data['height'][i]
                            }
                        })
            
            return texts
        except Exception as e:
            print(f"OCRエラー: {e}")
            return []
    
    def detect_shapes(self, image: np.ndarray) -> List[Dict]:
        """図形検出（矩形・円など）"""
        shapes = []
        
        # 輪郭検出
        contours, _ = cv2.findContours(image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for contour in contours:
            # 面積フィルタ
            area = cv2.contourArea(contour)
            if area < 100:  # 小さすぎる図形は除外
                continue
            
            # 矩形近似
            epsilon = 0.02 * cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, epsilon, True)
            
            # バウンディングボックス
            x, y, w, h = cv2.boundingRect(contour)
            
            shape_info = {
                'type': 'unknown',
                'bbox': {'x': x, 'y': y, 'width': w, 'height': h},
                'area': area,
                'vertices': len(approx)
            }
            
            # 形状判定
            if len(approx) == 4:
                # 矩形の可能性
                aspect_ratio = w / h
                if 0.8 <= aspect_ratio <= 1.2:
                    shape_info['type'] = 'square'
                else:
                    shape_info['type'] = 'rectangle'
            elif len(approx) > 8:
                shape_info['type'] = 'circle'
            
            shapes.append(shape_info)
        
        return shapes
    
    def extract_shelf_information(self, ocr_texts: List[Dict], shapes: List[Dict]) -> List[Dict]:
        """棚情報の抽出・マッチング"""
        shelves = []
        
        # 棚番号パターン
        shelf_patterns = [
            r'[A-Z]\d+',  # A1, B2など
            r'\d+[A-Z]',  # 1A, 2Bなど
            r'棚\d+',     # 棚1, 棚2など
            r'\d+番',     # 1番, 2番など
            r'\d+',       # 単純な数字
        ]
        
        for text_info in ocr_texts:
            text = text_info['text']
            
            # 棚番号パターンマッチング
            for pattern in shelf_patterns:
                if re.match(pattern, text):
                    # 近くの図形を探す
                    nearby_shape = self.find_nearby_shape(text_info['bbox'], shapes)
                    
                    shelf_info = {
                        'shelf_number': text,
                        'text_bbox': text_info['bbox'],
                        'confidence': text_info['confidence'],
                        'shape': nearby_shape
                    }
                    
                    # 座標変換（実際の座標系に変換）
                    if nearby_shape:
                        shelf_info['position'] = self.calculate_grid_position(nearby_shape['bbox'])
                    
                    shelves.append(shelf_info)
                    break
        
        return shelves
    
    def find_nearby_shape(self, text_bbox: Dict, shapes: List[Dict], max_distance: int = 100) -> Optional[Dict]:
        """テキストに最も近い図形を見つける"""
        text_center_x = text_bbox['x'] + text_bbox['width'] // 2
        text_center_y = text_bbox['y'] + text_bbox['height'] // 2
        
        closest_shape = None
        min_distance = float('inf')
        
        for shape in shapes:
            shape_center_x = shape['bbox']['x'] + shape['bbox']['width'] // 2
            shape_center_y = shape['bbox']['y'] + shape['bbox']['height'] // 2
            
            distance = np.sqrt((text_center_x - shape_center_x)**2 + (text_center_y - shape_center_y)**2)
            
            if distance < min_distance and distance <= max_distance:
                min_distance = distance
                closest_shape = shape
        
        return closest_shape
    
    def calculate_grid_position(self, bbox: Dict) -> Dict:
        """バウンディングボックスからグリッド位置を計算"""
        # 簡単な例：画像サイズを基準にした相対位置
        # 実際の実装では、図面のスケールや基準点を考慮する必要がある
        
        center_x = bbox['x'] + bbox['width'] // 2
        center_y = bbox['y'] + bbox['height'] // 2
        
        # グリッド座標に変換（仮の実装）
        grid_x = center_x // 100  # 100ピクセルごとに1グリッド
        grid_y = center_y // 100
        
        return {
            'grid_x': int(grid_x),
            'grid_y': int(grid_y),
            'pixel_x': center_x,
            'pixel_y': center_y
        }

class LayoutGenerator:
    """OCR結果からレイアウトを生成するクラス"""
    
    def __init__(self):
        pass
    
    def generate_layout_from_ocr(self, ocr_result: Dict, layout_name: str) -> Dict:
        """OCR結果からCultivationLayoutとCultivationSectionを生成"""
        from .models import CultivationLayout, CultivationSection
        
        try:
            # レイアウト作成
            layout = CultivationLayout.objects.create(name=layout_name)
            
            created_sections = []
            
            # 各ページの棚情報を処理
            for page in ocr_result.get('pages', []):
                for shelf in page.get('shelf_info', []):
                    if shelf.get('position'):
                        # 区画作成
                        section = CultivationSection.objects.create(
                            layout=layout,
                            name=shelf['shelf_number'],
                            row=shelf['position']['grid_y'] + 1,  # 1-based indexing
                            column=shelf['position']['grid_x'] + 1,
                            description=f"OCRで自動生成 (信頼度: {shelf['confidence']}%)"
                        )
                        created_sections.append(section)
            
            return {
                'success': True,
                'layout': layout,
                'sections': created_sections,
                'sections_count': len(created_sections)
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
```

#### 2.2 フォーム拡張

```python
# cultivation/forms.py（既存ファイルに追加）

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
        initial=True
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
        
    def clean_ocr_file(self):
        ocr_file = self.cleaned_data.get('ocr_file')
        if ocr_file:
            # ファイルサイズチェック（10MB制限）
            if ocr_file.size > 10 * 1024 * 1024:
                raise forms.ValidationError("ファイルサイズは10MB以下にしてください。")
            
            # ファイル形式チェック
            allowed_extensions = ['.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.bmp']
            file_extension = ocr_file.name.lower().split('.')[-1]
            if f'.{file_extension}' not in allowed_extensions:
                raise forms.ValidationError("対応していないファイル形式です。")
        
        return ocr_file
```

### Phase 3: ビュー関数の実装

#### 3.1 OCR機能付きレイアウト作成ビュー

```python
# cultivation/views.py（既存ファイルに追加）

import os
from django.conf import settings
from .ocr_utils import DocumentOCR, LayoutGenerator

def layout_create_with_ocr(request):
    """OCR機能付きレイアウト作成"""
    if request.method == 'POST':
        form = OCRLayoutForm(request.POST, request.FILES)
        if form.is_valid():
            layout = form.save(commit=False)
            layout.save()
            
            ocr_file = form.cleaned_data.get('ocr_file')
            auto_generate = form.cleaned_data.get('auto_generate_sections')
            confidence_threshold = form.cleaned_data.get('ocr_confidence_threshold')
            
            if ocr_file and auto_generate:
                # OCR処理実行
                result = process_ocr_file(ocr_file, layout, confidence_threshold)
                
                if result['success']:
                    messages.success(
                        request, 
                        f"レイアウトを作成し、{result['sections_count']}個の区画を自動生成しました。"
                    )
                else:
                    messages.warning(
                        request, 
                        f"レイアウトは作成されましたが、OCR処理でエラーが発生しました: {result['error']}"
                    )
            else:
                messages.success(request, "レイアウトを作成しました。")
            
            return redirect('cultivation:layout_detail', layout_id=layout.id)
    else:
        form = OCRLayoutForm()
    
    return render(request, 'cultivation/layout_create_ocr.html', {'form': form})

def process_ocr_file(uploaded_file, layout, confidence_threshold):
    """アップロードされたファイルのOCR処理"""
    try:
        # 一時ファイルとして保存
        temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp_ocr')
        os.makedirs(temp_dir, exist_ok=True)
        
        temp_file_path = os.path.join(temp_dir, uploaded_file.name)
        
        with open(temp_file_path, 'wb+') as destination:
            for chunk in uploaded_file.chunks():
                destination.write(chunk)
        
        # OCR処理実行
        ocr = DocumentOCR()
        ocr_result = ocr.process_uploaded_file(temp_file_path)
        
        if ocr_result['success']:
            # レイアウト生成
            generator = LayoutGenerator()
            layout_result = generator.generate_layout_from_ocr(ocr_result, layout.name)
            
            # 一時ファイル削除
            os.remove(temp_file_path)
            
            return layout_result
        else:
            # 一時ファイル削除
            os.remove(temp_file_path)
            return ocr_result
            
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

def ocr_preview(request):
    """OCR結果のプレビュー表示"""
    if request.method == 'POST' and request.FILES.get('file'):
        uploaded_file = request.FILES['file']
        
        try:
            # OCR処理（プレビューのみ）
            result = process_ocr_file_preview(uploaded_file)
            return JsonResponse(result)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({'success': False, 'error': 'ファイルが指定されていません'})

def process_ocr_file_preview(uploaded_file):
    """OCRプレビュー処理（レイアウト作成なし）"""
    temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp_ocr')
    os.makedirs(temp_dir, exist_ok=True)
    
    temp_file_path = os.path.join(temp_dir, uploaded_file.name)
    
    with open(temp_file_path, 'wb+') as destination:
        for chunk in uploaded_file.chunks():
            destination.write(chunk)
    
    ocr = DocumentOCR()
    result = ocr.process_uploaded_file(temp_file_path)
    
    # 一時ファイル削除
    os.remove(temp_file_path)
    
    return result
```

### Phase 4: テンプレートの作成

#### 4.1 OCR機能付きレイアウト作成画面

```html
<!-- cultivation/templates/cultivation/layout_create_ocr.html -->
{% extends "base.html" %}

{% block title %}OCR機能付きレイアウト作成{% endblock %}

{% block extra_css %}
<style>
    .ocr-preview {
        border: 2px dashed #dee2e6;
        border-radius: 8px;
        padding: 20px;
        text-align: center;
        margin: 20px 0;
        background-color: #f8f9fa;
    }
    
    .ocr-preview.dragover {
        border-color: #007bff;
        background-color: #e3f2fd;
    }
    
    .preview-results {
        max-height: 400px;
        overflow-y: auto;
        border: 1px solid #dee2e6;
        border-radius: 4px;
        padding: 15px;
        background-color: white;
    }
    
    .shelf-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 8px 12px;
        margin: 4px 0;
        background-color: #f8f9fa;
        border-radius: 4px;
        border-left: 4px solid #28a745;
    }
    
    .confidence-badge {
        font-size: 0.8em;
        padding: 2px 6px;
        border-radius: 3px;
    }
    
    .confidence-high { background-color: #d4edda; color: #155724; }
    .confidence-medium { background-color: #fff3cd; color: #856404; }
    .confidence-low { background-color: #f8d7da; color: #721c24; }
</style>
{% endblock %}

{% block content %}
<div class="container mt-4">
    <div class="row">
        <div class="col-md-8">
            <h2><i class="fas fa-magic me-2"></i>OCR機能付きレイアウト作成</h2>
            
            <form method="post" enctype="multipart/form-data" id="ocrForm">
                {% csrf_token %}
                
                <div class="card mb-4">
                    <div class="card-header">
                        <h5 class="mb-0">基本情報</h5>
                    </div>
                    <div class="card-body">
                        <div class="mb-3">
                            {{ form.name.label_tag }}
                            {{ form.name }}
                            {% if form.name.errors %}
                                <div class="text-danger">{{ form.name.errors }}</div>
                            {% endif %}
                        </div>
                        
                        <div class="mb-3">
                            {{ form.layout_image.label_tag }}
                            {{ form.layout_image }}
                            <div class="form-text">{{ form.layout_image.help_text }}</div>
                            {% if form.layout_image.errors %}
                                <div class="text-danger">{{ form.layout_image.errors }}</div>
                            {% endif %}
                        </div>
                    </div>
                </div>
                
                <div class="card mb-4">
                    <div class="card-header">
                        <h5 class="mb-0">OCR自動解析</h5>
                    </div>
                    <div class="card-body">
                        <div class="mb-3">
                            {{ form.ocr_file.label_tag }}
                            <div class="ocr-preview" id="dropZone">
                                <i class="fas fa-cloud-upload-alt fa-3x text-muted mb-3"></i>
                                <p class="mb-2">図面ファイルをドラッグ&ドロップ、またはクリックして選択</p>
                                <p class="text-muted small">対応形式: PDF, PNG, JPEG, TIFF (最大10MB)</p>
                                {{ form.ocr_file }}
                            </div>
                            {% if form.ocr_file.errors %}
                                <div class="text-danger">{{ form.ocr_file.errors }}</div>
                            {% endif %}
                        </div>
                        
                        <div class="row">
                            <div class="col-md-6">
                                <div class="mb-3">
                                    <div class="form-check">
                                        {{ form.auto_generate_sections }}
                                        {{ form.auto_generate_sections.label_tag }}
                                    </div>
                                    <div class="form-text">{{ form.auto_generate_sections.help_text }}</div>
                                </div>
                            </div>
                            <div class="col-md-6">
                                <div class="mb-3">
                                    {{ form.ocr_confidence_threshold.label_tag }}
                                    {{ form.ocr_confidence_threshold }}
                                    <div class="form-text">{{ form.ocr_confidence_threshold.help_text }}</div>
                                </div>
                            </div>
                        </div>
                        
                        <button type="button" class="btn btn-info" id="previewBtn" disabled>
                            <i class="fas fa-eye me-1"></i>OCR結果をプレビュー
                        </button>
                    </div>
                </div>
                
                <!-- OCRプレビュー結果 -->
                <div class="card mb-4" id="previewCard" style="display: none;">
                    <div class="card-header">
                        <h5 class="mb-0">OCR解析結果</h5>
                    </div>
                    <div class="card-body">
                        <div id="previewResults" class="preview-results">
                            <!-- プレビュー結果がここに表示される -->
                        </div>
                    </div>
                </div>
                
                <div class="d-flex gap-2">
                    <button type="submit" class="btn btn-primary">
                        <i class="fas fa-save me-1"></i>レイアウトを作成
                    </button>
                    <a href="{% url 'cultivation:cultivation_top' %}" class="btn btn-secondary">
                        <i class="fas fa-arrow-left me-1"></i>戻る
                    </a>
                </div>
            </form>
        </div>
        
        <div class="col-md-4">
            <div class="card">
                <div class="card-header">
                    <h5 class="mb-0">OCR機能について</h5>
                </div>
                <div class="card-body">
                    <h6>対応ファイル形式</h6>
                    <ul class="list-unstyled">
                        <li><i class="fas fa-file-pdf text-danger me-2"></i>PDF</li>
                        <li><i class="fas fa-file-image text-success me-2"></i>PNG, JPEG</li>
                        <li><i class="fas fa-file-image text-info me-2"></i>TIFF, BMP</li>
                    </ul>
                    
                    <h6 class="mt-3">認識対象</h6>
                    <ul class="list-unstyled">
                        <li><i class="fas fa-hashtag text-primary me-2"></i>棚番号</li>
                        <li><i class="fas fa-square text-warning me-2"></i>棚の形状・位置</li>
                        <li><i class="fas fa-ruler text-secondary me-2"></i>寸法・注釈</li>
                    </ul>
                    
                    <h6 class="mt-3">使用のコツ</h6>
                    <ul class="small">
                        <li>高解像度の画像を使用</li>
                        <li>文字がはっきり見える図面</li>
                        <li>背景色と文字のコントラストが明確</li>
                        <li>余白や不要な要素を除去</li>
                    </ul>
                </div>
            </div>
        </div>
    </div>
</div>

<script>
document.addEventListener('DOMContentLoaded', function() {
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('{{ form.ocr_file.id_for_label }}');
    const previewBtn = document.getElementById('previewBtn');
    const previewCard = document.getElementById('previewCard');
    const previewResults = document.getElementById('previewResults');
    
    // ドラッグ&ドロップ機能
    dropZone.addEventListener('dragover', function(e) {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });
    
    dropZone.addEventListener('dragleave', function(e) {
        e.preventDefault();
        dropZone.classList.remove('dragover');
    });
    
    dropZone.addEventListener('drop', function(e) {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            fileInput.files = files;
            handleFileSelect();
        }
    });
    
    dropZone.addEventListener('click', function() {
        fileInput.click();
    });
    
    fileInput.addEventListener('change', handleFileSelect);
    
    function handleFileSelect() {
        if (fileInput.files.length > 0) {
            const fileName = fileInput.files[0].name;
            dropZone.innerHTML = `
                <i class="fas fa-file-alt fa-2x text-success mb-2"></i>
                <p class="mb-0">${fileName}</p>
                <p class="text-muted small">クリックして別のファイルを選択</p>
            `;
            previewBtn.disabled = false;
        }
    }
    
    // OCRプレビュー
    previewBtn.addEventListener('click', function() {
        if (fileInput.files.length === 0) return;
        
        const formData = new FormData();
        formData.append('file', fileInput.files[0]);
        formData.append('csrfmiddlewaretoken', document.querySelector('[name=csrfmiddlewaretoken]').value);
        
        previewBtn.disabled = true;
        previewBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>解析中...';
        
        fetch('{% url "cultivation:ocr_preview" %}', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            displayPreviewResults(data);
            previewBtn.disabled = false;
            previewBtn.innerHTML = '<i class="fas fa-eye me-1"></i>OCR結果をプレビュー';
        })
        .catch(error => {
            console.error('Error:', error);
            previewBtn.disabled = false;
            previewBtn.innerHTML = '<i class="fas fa-eye me-1"></i>OCR結果をプレビュー';
        });
    });
    
    function displayPreviewResults(data) {
        if (!data.success) {
            previewResults.innerHTML = `
                <div class="alert alert-danger">
                    <i class="fas fa-exclamation-triangle me-2"></i>
                    エラー: ${data.error}
                </div>
            `;
            previewCard.style.display = 'block';
            return;
        }
        
        let html = '';
        let totalShelves = 0;
        
        data.pages.forEach((page, pageIndex) => {
            if (data.total_pages > 1) {
                html += `<h6>ページ ${page.page_number}</h6>`;
            }
            
            if (page.shelf_info.length === 0) {
                html += '<p class="text-muted">棚情報が検出されませんでした。</p>';
            } else {
                page.shelf_info.forEach(shelf => {
                    const confidenceClass = shelf.confidence >= 80 ? 'confidence-high' : 
                                          shelf.confidence >= 60 ? 'confidence-medium' : 'confidence-low';
                    
                    html += `
                        <div class="shelf-item">
                            <span>
                                <strong>${shelf.shelf_number}</strong>
                                ${shelf.position ? ` (${shelf.position.grid_x}, ${shelf.position.grid_y})` : ''}
                            </span>
                            <span class="confidence-badge ${confidenceClass}">
                                ${shelf.confidence}%
                            </span>
                        </div>
                    `;
                    totalShelves++;
                });
            }
        });
        
        if (totalShelves > 0) {
            html = `
                <div class="alert alert-success mb-3">
                    <i class="fas fa-check-circle me-2"></i>
                    ${totalShelves}個の棚が検出されました
                </div>
                ${html}
            `;
        }
        
        previewResults.innerHTML = html;
        previewCard.style.display = 'block';
    }
});
</script>
{% endblock %}
```

### Phase 5: URL設定

#### 5.1 URLs追加

```python
# cultivation/urls.py（既存ファイルに追加）

urlpatterns = [
    # ... 既存のURL設定 ...
    
    # OCR機能
    path('layouts/create-ocr/', views.layout_create_with_ocr, name='layout_create_ocr'),
    path('ocr/preview/', views.ocr_preview, name='ocr_preview'),
]
```

### Phase 6: 設定とテスト

#### 6.1 settings.py設定

```python
# settings.py（既存ファイルに追加）

# OCR設定
OCR_SETTINGS = {
    'TESSERACT_CMD': '/usr/local/bin/tesseract',  # Tesseractのパス
    'TEMP_DIR': os.path.join(BASE_DIR, 'media', 'temp_ocr'),
    'MAX_FILE_SIZE': 10 * 1024 * 1024,  # 10MB
    'SUPPORTED_FORMATS': ['.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.bmp'],
    'DEFAULT_CONFIDENCE_THRESHOLD': 60,
}

# メディアファイル設定（既存の場合は確認）
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
```

#### 6.2 requirements.txt更新

```txt
# 既存のパッケージに追加
pytesseract==0.3.10
opencv-python==4.8.1.78
Pillow==10.0.1
pdf2image==1.16.3
numpy==1.24.3
scikit-image==0.21.0
matplotlib==3.7.2
python-Levenshtein==0.21.1
fuzzywuzzy==0.18.0
```

### Phase 7: デプロイメントと運用

#### 7.1 本番環境での設定

```bash
# 本番サーバーでのTesseractインストール
sudo apt-get update
sudo apt-get install tesseract-ocr tesseract-ocr-jpn poppler-utils

# Pythonパッケージインストール
pip install -r requirements.txt
```

#### 7.2 パフォーマンス最適化

```python
# cultivation/ocr_utils.py（最適化版）

class OptimizedDocumentOCR(DocumentOCR):
    """最適化されたOCRクラス"""
    
    def __init__(self):
        super().__init__()
        # キャッシュ設定
        self.cache_enabled = True
        self.cache_duration = 3600  # 1時間
    
    def process_with_cache(self, file_path: str) -> Dict:
        """キャッシュ機能付きの処理"""
        import hashlib
        
        # ファイルハッシュを計算
        with open(file_path, 'rb') as f:
            file_hash = hashlib.md5(f.read()).hexdigest()
        
        cache_key = f"ocr_result_{file_hash}"
        
        # キャッシュから取得を試行
        if self.cache_enabled:
            from django.core.cache import cache
            cached_result = cache.get(cache_key)
            if cached_result:
                return cached_result
        
        # OCR処理実行
        result = self.process_uploaded_file(file_path)
        
        # 結果をキャッシュに保存
        if self.cache_enabled and result.get('success'):
            from django.core.cache import cache
            cache.set(cache_key, result, self.cache_duration)
        
        return result
```

## トラブルシューティング

### よくある問題と解決方法

1. **Tesseractが見つからない**
   ```bash
   # パスを確認
   which tesseract
   # 環境変数を設定
   export TESSERACT_CMD=/usr/local/bin/tesseract
   ```

2. **日本語OCRの精度が低い**
   - 日本語言語パックのインストール確認
   - 画像の前処理パラメータ調整
   - フォントサイズと解像度の確認

3. **メモリ使用量が多い**
   - 画像サイズの制限
   - バッチ処理の実装
   - キャッシュ機能の活用

4. **処理時間が長い**
   - 非同期処理の実装（Celery等）
   - 画像の前処理最適化
   - OCR設定の調整

## 今後の拡張計画

1. **AI/機械学習の導入**
   - カスタムモデルの訓練
   - 図面特化の認識精度向上

2. **CADファイル対応**
   - DXF形式の直接読み込み
   - ベクターデータの活用

3. **リアルタイム処理**
   - WebSocketを使った進捗表示
   - 段階的な結果表示

4. **多言語対応**
   - 英語図面の対応
   - 多言語UI

この実装手順に従って、段階的にOCR機能を追加していくことで、図面から自動的にレイアウトを生成できる高度な水耕栽培管理システムが完成します。 