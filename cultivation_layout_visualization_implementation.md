# 栽培レイアウト図表示機能実装計画

## 1. 概要

既存のOCR機能により図面から棚番号と位置情報を抽出し、栽培レイアウトを自動生成する機能は実装済みです。この実装では、OCR結果を元に視覚的な栽培レイアウト図を生成・表示する機能を追加します。

## 2. 現在の実装状況

### 2.1 既存のOCR機能
- **OCRユーティリティ**: `cultivation/ocr_utils.py`（687行）
- **レイアウト生成**: `LayoutGenerator`クラスで`CultivationLayout`と`CultivationSection`を自動生成
- **棚情報抽出**: 棚番号パターンマッチング、グリッド座標変換
- **品質検証**: 信頼度フィルタリング、検証機能

### 2.2 データ構造
```python
# OCR結果の棚情報
shelf_info = {
    "shelf_number": "A1",
    "text_bbox": {"x": 100, "y": 200, "width": 30, "height": 20},
    "confidence": 85,
    "shape": {...},
    "position": {"grid_x": 1, "grid_y": 2, "pixel_x": 130, "pixel_y": 210}
}

# 生成されるレイアウト
layout_result = {
    "success": True,
    "layout": "<CultivationLayout object>",
    "sections": ["<CultivationSection object>", ...],
    "sections_count": 5
}
```

## 3. 栽培レイアウト図表示機能の実装

### 3.1 実装方針
1. **SVG形式での図表示**: スケーラブルで高品質な図表示
2. **リアルタイム更新**: OCR結果に応じて即座に図を更新
3. **インタラクティブ機能**: 区画クリックで詳細情報表示
4. **レスポンシブデザイン**: モバイル対応

### 3.2 実装コンポーネント

#### A. レイアウト図生成クラス (`cultivation/layout_visualizer.py`)
```python
class LayoutVisualizer:
    def __init__(self, layout_data, ocr_results):
        self.layout_data = layout_data
        self.ocr_results = ocr_results
        self.svg_width = 800
        self.svg_height = 600
        
    def generate_svg(self) -> str:
        """SVG形式の栽培レイアウト図を生成"""
        pass
        
    def create_section_element(self, section, position) -> str:
        """個別区画のSVG要素を生成"""
        pass
        
    def add_labels_and_annotations(self) -> str:
        """ラベルと注釈を追加"""
        pass
        
    def generate_legend(self) -> str:
        """凡例を生成"""
        pass
```

#### B. ビュー関数の拡張 (`cultivation/views.py`)
```python
def ocr_preview_with_layout(request):
    """OCR結果と栽培レイアウト図を表示"""
    # 既存のOCR処理
    ocr_result = process_ocr_file(request)
    
    # レイアウト図生成
    visualizer = LayoutVisualizer(layout_data, ocr_result)
    svg_content = visualizer.generate_svg()
    
    context = {
        'ocr_result': ocr_result,
        'layout_svg': svg_content,
        'sections': sections,
        'layout': layout
    }
    return render(request, 'cultivation/layout_preview.html', context)
```

#### C. HTMLテンプレート (`cultivation/templates/cultivation/layout_preview.html`)
```html
<div class="layout-preview-container">
    <!-- OCR結果表示 -->
    <div class="ocr-results-panel">
        <h3>OCR処理結果</h3>
        <div class="ocr-stats">
            <p>検出された区画数: {{ sections|length }}</p>
            <p>平均信頼度: {{ ocr_result.average_confidence }}%</p>
        </div>
        <div class="ocr-text-list">
            {% for shelf in ocr_result.shelf_info %}
            <div class="shelf-item" data-shelf="{{ shelf.shelf_number }}">
                <span class="shelf-number">{{ shelf.shelf_number }}</span>
                <span class="confidence">{{ shelf.confidence }}%</span>
            </div>
            {% endfor %}
        </div>
    </div>
    
    <!-- 栽培レイアウト図表示 -->
    <div class="layout-visualization-panel">
        <h3>栽培レイアウト図</h3>
        <div class="layout-svg-container">
            {{ layout_svg|safe }}
        </div>
        <div class="layout-controls">
            <button class="btn btn-primary" onclick="zoomIn()">拡大</button>
            <button class="btn btn-secondary" onclick="zoomOut()">縮小</button>
            <button class="btn btn-info" onclick="resetView()">リセット</button>
        </div>
    </div>
</div>

<!-- 区画詳細モーダル -->
<div id="sectionModal" class="modal">
    <div class="modal-content">
        <span class="close">&times;</span>
        <h2>区画詳細</h2>
        <div id="sectionDetails"></div>
    </div>
</div>
```

#### D. CSSスタイル (`static/css/layout_visualization.css`)
```css
.layout-preview-container {
    display: grid;
    grid-template-columns: 1fr 2fr;
    gap: 20px;
    padding: 20px;
}

.layout-svg-container {
    border: 1px solid #ddd;
    border-radius: 8px;
    padding: 10px;
    background: #f9f9f9;
    overflow: auto;
}

.layout-svg-container svg {
    width: 100%;
    height: auto;
    cursor: pointer;
}

.section-rect {
    fill: #e3f2fd;
    stroke: #1976d2;
    stroke-width: 2;
    transition: all 0.3s ease;
}

.section-rect:hover {
    fill: #bbdefb;
    stroke: #0d47a1;
    stroke-width: 3;
}

.section-text {
    font-family: 'Arial', sans-serif;
    font-size: 14px;
    font-weight: bold;
    fill: #333;
    text-anchor: middle;
    dominant-baseline: middle;
}

.layout-controls {
    margin-top: 10px;
    text-align: center;
}

.ocr-results-panel {
    background: #f5f5f5;
    border-radius: 8px;
    padding: 15px;
}

.shelf-item {
    display: flex;
    justify-content: space-between;
    padding: 5px 10px;
    margin: 2px 0;
    background: white;
    border-radius: 4px;
    border-left: 4px solid #2196f3;
}

.shelf-item:hover {
    background: #e3f2fd;
}

@media (max-width: 768px) {
    .layout-preview-container {
        grid-template-columns: 1fr;
    }
}
```

#### E. JavaScript機能 (`static/js/layout_visualization.js`)
```javascript
class LayoutVisualization {
    constructor() {
        this.currentZoom = 1;
        this.initializeEventListeners();
    }
    
    initializeEventListeners() {
        // 区画クリックイベント
        document.querySelectorAll('.section-rect').forEach(rect => {
            rect.addEventListener('click', (e) => {
                this.showSectionDetails(e.target.dataset.sectionId);
            });
        });
        
        // OCR結果とレイアウト図の連携
        document.querySelectorAll('.shelf-item').forEach(item => {
            item.addEventListener('mouseenter', (e) => {
                this.highlightSection(e.target.dataset.shelf);
            });
            
            item.addEventListener('mouseleave', (e) => {
                this.unhighlightSection(e.target.dataset.shelf);
            });
        });
    }
    
    showSectionDetails(sectionId) {
        // 区画詳細をモーダルで表示
        fetch(`/cultivation/section/${sectionId}/details/`)
            .then(response => response.json())
            .then(data => {
                document.getElementById('sectionDetails').innerHTML = 
                    this.renderSectionDetails(data);
                document.getElementById('sectionModal').style.display = 'block';
            });
    }
    
    highlightSection(shelfNumber) {
        const sectionElement = document.querySelector(`[data-shelf="${shelfNumber}"]`);
        if (sectionElement) {
            sectionElement.classList.add('highlighted');
        }
    }
    
    unhighlightSection(shelfNumber) {
        const sectionElement = document.querySelector(`[data-shelf="${shelfNumber}"]`);
        if (sectionElement) {
            sectionElement.classList.remove('highlighted');
        }
    }
    
    zoomIn() {
        this.currentZoom *= 1.2;
        this.updateZoom();
    }
    
    zoomOut() {
        this.currentZoom /= 1.2;
        this.updateZoom();
    }
    
    resetView() {
        this.currentZoom = 1;
        this.updateZoom();
    }
    
    updateZoom() {
        const svg = document.querySelector('.layout-svg-container svg');
        svg.style.transform = `scale(${this.currentZoom})`;
    }
    
    renderSectionDetails(data) {
        return `
            <div class="section-info">
                <h3>${data.name}</h3>
                <p><strong>サイズ:</strong> ${data.width}cm × ${data.height}cm</p>
                <p><strong>位置:</strong> 行${data.row}, 列${data.column}</p>
                <p><strong>現在の作物:</strong> ${data.current_crop || 'なし'}</p>
                <p><strong>次回植え付け予定:</strong> ${data.next_planting || 'なし'}</p>
            </div>
        `;
    }
}

// 初期化
document.addEventListener('DOMContentLoaded', () => {
    new LayoutVisualization();
});
```

### 3.3 実装手順

#### Phase 1: レイアウト図生成機能
1. **`LayoutVisualizer`クラス実装**
   - SVG生成ロジック
   - 座標変換とスケーリング
   - 区画の矩形描画

2. **ビュー関数の拡張**
   - 既存のOCR処理結果を活用
   - レイアウト図生成の統合

#### Phase 2: UI実装
1. **HTMLテンプレート作成**
   - レスポンシブレイアウト
   - OCR結果とレイアウト図の連携表示

2. **CSSスタイル適用**
   - 見やすいデザイン
   - ホバー効果とアニメーション

#### Phase 3: インタラクティブ機能
1. **JavaScript実装**
   - 区画クリック処理
   - ズーム機能
   - OCR結果との連携

2. **詳細情報表示**
   - モーダルウィンドウ
   - 区画詳細情報

#### Phase 4: 統合とテスト
1. **既存システムとの統合**
   - URL設定
   - 権限制御

2. **動作テスト**
   - 各種画像での動作確認
   - レスポンシブデザインテスト

## 4. 技術仕様

### 4.1 使用技術
- **バックエンド**: Django, Python
- **フロントエンド**: HTML5, CSS3, JavaScript
- **図表示**: SVG
- **既存機能**: OCR (pytesseract, OpenCV)

### 4.2 パフォーマンス考慮
- **SVGキャッシュ**: 生成済みSVGの再利用
- **遅延読み込み**: 大きな図面での部分読み込み
- **圧縮**: SVGの最適化

### 4.3 セキュリティ考慮
- **XSS対策**: SVG内容のサニタイズ
- **認証**: 既存の権限システムとの統合
- **ファイルアップロード**: 既存のバリデーション活用

## 5. 想定される問題と対策

### 5.1 精度の問題
- **OCR認識ミス**: 手動修正機能の提供
- **座標ずれ**: 調整機能の実装

### 5.2 表示の問題
- **大きな図面**: ズーム・パン機能
- **モバイル対応**: レスポンシブデザイン

### 5.3 パフォーマンスの問題
- **重い処理**: 非同期処理とプログレス表示
- **メモリ使用量**: キャッシュ管理

## 6. 今後の拡張可能性

### 6.1 機能拡張
- **3D表示**: Three.jsを使った立体的な表示
- **アニメーション**: 栽培計画の時系列表示
- **印刷機能**: PDF出力機能

### 6.2 データ連携
- **センサーデータ**: 環境データとの連携
- **作物データ**: 成長データとの統合
- **在庫管理**: 種子・資材管理との連携

## 7. 実装スケジュール

### Week 1: 基本機能実装
- [ ] `LayoutVisualizer`クラス実装
- [ ] SVG生成ロジック開発
- [ ] 基本的なHTMLテンプレート作成

### Week 2: UI改善
- [ ] CSSスタイル適用
- [ ] レスポンシブデザイン対応
- [ ] 基本的なインタラクティブ機能

### Week 3: 高度な機能
- [ ] ズーム・パン機能
- [ ] 区画詳細表示
- [ ] OCR結果との連携強化

### Week 4: 最適化とテスト
- [ ] パフォーマンス最適化
- [ ] 包括的なテスト
- [ ] ドキュメント整備

## 8. 成功指標

### 8.1 機能指標
- [ ] OCR結果から自動的に栽培レイアウト図が生成される
- [ ] 区画クリックで詳細情報が表示される
- [ ] モバイルデバイスでも正常に動作する

### 8.2 品質指標
- [ ] 処理時間が3秒以内
- [ ] 各種ブラウザでの表示に問題なし
- [ ] レスポンシブデザインが適切に動作

### 8.3 ユーザビリティ指標
- [ ] 直感的な操作が可能
- [ ] OCR結果との連携がスムーズ
- [ ] 視覚的に分かりやすい表示

---

この実装により、OCR機能で抽出した情報を視覚的に分かりやすく表示し、栽培管理の効率化を実現します。