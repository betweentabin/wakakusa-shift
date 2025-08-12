/**
 * 栽培レイアウト図表示用JavaScript
 * OCR結果とレイアウト図の連携、インタラクティブ機能を提供
 */

class LayoutVisualization {
    constructor() {
        this.currentZoom = 1;
        this.minZoom = 0.5;
        this.maxZoom = 3;
        this.zoomStep = 0.2;
        this.currentShelf = null;
        this.gridVisible = true;
        this.labelsVisible = true;
        
        this.initializeEventListeners();
        this.setupModalHandlers();
        this.setupKeyboardShortcuts();
    }
    
    /**
     * イベントリスナーの初期化
     */
    initializeEventListeners() {
        // 区画要素のクリックイベント
        document.querySelectorAll('.section-rect').forEach(rect => {
            rect.addEventListener('click', (e) => {
                this.handleSectionClick(e);
            });
            
            rect.addEventListener('mouseenter', (e) => {
                this.handleSectionHover(e, true);
            });
            
            rect.addEventListener('mouseleave', (e) => {
                this.handleSectionHover(e, false);
            });
        });
        
        // OCR結果一覧とレイアウト図の連携
        document.querySelectorAll('.shelf-item').forEach(item => {
            item.addEventListener('mouseenter', (e) => {
                this.highlightSection(e.target.dataset.shelf, true);
            });
            
            item.addEventListener('mouseleave', (e) => {
                this.highlightSection(e.target.dataset.shelf, false);
            });
            
            item.addEventListener('click', (e) => {
                this.selectShelfItem(e.target.dataset.shelf);
            });
        });
        
        // SVGコンテナのホイールイベント（ズーム）
        const svgContainer = document.getElementById('layoutSvgContainer');
        if (svgContainer) {
            svgContainer.addEventListener('wheel', (e) => {
                e.preventDefault();
                if (e.deltaY > 0) {
                    this.zoomOut();
                } else {
                    this.zoomIn();
                }
            });
        }
    }
    
    /**
     * モーダルハンドラーの設定
     */
    setupModalHandlers() {
        // 区画詳細モーダル
        const sectionModal = document.getElementById('sectionModal');
        if (sectionModal) {
            sectionModal.addEventListener('hidden.bs.modal', () => {
                this.clearAllHighlights();
            });
        }
        
        // エクスポートモーダル
        const exportModal = document.getElementById('exportModal');
        if (exportModal) {
            exportModal.addEventListener('show.bs.modal', () => {
                this.prepareExportModal();
            });
        }
    }
    
    /**
     * キーボードショートカットの設定
     */
    setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
                return;
            }
            
            switch(e.key) {
                case '+':
                case '=':
                    e.preventDefault();
                    this.zoomIn();
                    break;
                case '-':
                    e.preventDefault();
                    this.zoomOut();
                    break;
                case '0':
                    e.preventDefault();
                    this.resetView();
                    break;
                case 'g':
                    e.preventDefault();
                    this.toggleGrid();
                    break;
                case 'l':
                    e.preventDefault();
                    this.toggleLabels();
                    break;
                case 'Escape':
                    this.clearAllHighlights();
                    break;
            }
        });
    }
    
    /**
     * 区画クリック処理
     */
    handleSectionClick(event) {
        const rect = event.target;
        const shelfNumber = rect.dataset.shelf;
        const confidence = parseFloat(rect.dataset.confidence);
        const gridX = parseInt(rect.dataset.gridX);
        const gridY = parseInt(rect.dataset.gridY);
        
        // 既存のハイライトをクリア
        this.clearAllHighlights();
        
        // 選択された区画をハイライト
        rect.classList.add('highlighted');
        
        // 対応するリストアイテムもハイライト
        const listItem = document.querySelector(`[data-shelf="${shelfNumber}"]`);
        if (listItem) {
            listItem.classList.add('highlighted');
        }
        
        // 区画詳細を表示
        this.showSectionDetails(shelfNumber, confidence, gridX, gridY);
    }
    
    /**
     * 区画ホバー処理
     */
    handleSectionHover(event, isEnter) {
        const rect = event.target;
        const shelfNumber = rect.dataset.shelf;
        
        if (isEnter) {
            // ツールチップ表示
            this.showTooltip(event, shelfNumber, rect.dataset.confidence);
        } else {
            // ツールチップ非表示
            this.hideTooltip();
        }
    }
    
    /**
     * 区画詳細表示
     */
    showSectionDetails(shelfNumber, confidence, gridX, gridY) {
        const modalElement = document.getElementById('sectionModal');
        const detailsElement = document.getElementById('sectionDetails');
        
        if (!modalElement || !detailsElement) return;
        
        // 現在選択中の区画を記録
        modalElement.dataset.currentShelf = shelfNumber;
        
        // 詳細情報を生成
        const detailsHtml = this.generateSectionDetailsHtml(shelfNumber, confidence, gridX, gridY);
        detailsElement.innerHTML = detailsHtml;
        
        // モーダルを表示
        const modal = new bootstrap.Modal(modalElement);
        modal.show();
    }
    
    /**
     * 区画詳細HTMLの生成
     */
    generateSectionDetailsHtml(shelfNumber, confidence, gridX, gridY) {
        const confidenceClass = this.getConfidenceClass(confidence);
        const confidenceLabel = this.getConfidenceLabel(confidence);
        
        return `
            <div class="section-info">
                <h3>${shelfNumber}</h3>
                <div class="row">
                    <div class="col-md-6">
                        <p><strong>グリッド位置:</strong> ${gridX}, ${gridY}</p>
                        <p><strong>信頼度:</strong> 
                            <span class="badge bg-${confidenceClass}">${confidence}%</span>
                            <small class="text-muted">(${confidenceLabel})</small>
                        </p>
                    </div>
                    <div class="col-md-6">
                        <p><strong>状態:</strong> <span class="badge bg-secondary">未設定</span></p>
                        <p><strong>最終更新:</strong> ${new Date().toLocaleDateString()}</p>
                    </div>
                </div>
                <hr>
                <div class="cultivation-info">
                    <h6>栽培情報</h6>
                    <p><strong>現在の作物:</strong> <span class="text-muted">なし</span></p>
                    <p><strong>次回植え付け予定:</strong> <span class="text-muted">なし</span></p>
                    <p><strong>推奨作物:</strong> <span class="text-muted">レタス、ほうれん草</span></p>
                </div>
                <div class="mt-3">
                    <small class="text-muted">
                        <i class="fas fa-info-circle"></i>
                        この情報はOCR処理により自動生成されました。
                    </small>
                </div>
            </div>
        `;
    }
    
    /**
     * 信頼度に応じたクラス名を取得
     */
    getConfidenceClass(confidence) {
        if (confidence >= 80) return 'success';
        if (confidence >= 60) return 'warning';
        return 'danger';
    }
    
    /**
     * 信頼度に応じたラベルを取得
     */
    getConfidenceLabel(confidence) {
        if (confidence >= 80) return '高信頼度';
        if (confidence >= 60) return '中信頼度';
        return '低信頼度';
    }
    
    /**
     * 区画のハイライト表示
     */
    highlightSection(shelfNumber, highlight) {
        const sectionElement = document.querySelector(`[data-shelf="${shelfNumber}"].section-rect`);
        const listItem = document.querySelector(`[data-shelf="${shelfNumber}"].shelf-item`);
        
        if (highlight) {
            if (sectionElement) sectionElement.classList.add('highlighted');
            if (listItem) listItem.classList.add('highlighted');
        } else {
            if (sectionElement) sectionElement.classList.remove('highlighted');
            if (listItem) listItem.classList.remove('highlighted');
        }
    }
    
    /**
     * 棚アイテムの選択
     */
    selectShelfItem(shelfNumber) {
        // 対応する区画要素を探してクリック
        const sectionElement = document.querySelector(`[data-shelf="${shelfNumber}"].section-rect`);
        if (sectionElement) {
            sectionElement.click();
        }
    }
    
    /**
     * すべてのハイライトをクリア
     */
    clearAllHighlights() {
        document.querySelectorAll('.highlighted').forEach(element => {
            element.classList.remove('highlighted');
        });
    }
    
    /**
     * ツールチップ表示
     */
    showTooltip(event, shelfNumber, confidence) {
        this.hideTooltip(); // 既存のツールチップを削除
        
        const tooltip = document.createElement('div');
        tooltip.id = 'sectionTooltip';
        tooltip.className = 'tooltip-custom';
        tooltip.innerHTML = `
            <div class="tooltip-content">
                <strong>${shelfNumber}</strong><br>
                信頼度: ${confidence}%
            </div>
        `;
        
        document.body.appendChild(tooltip);
        
        // 位置を設定
        const rect = event.target.getBoundingClientRect();
        tooltip.style.position = 'fixed';
        tooltip.style.left = rect.right + 10 + 'px';
        tooltip.style.top = rect.top + 'px';
        tooltip.style.zIndex = '9999';
        tooltip.style.background = '#333';
        tooltip.style.color = 'white';
        tooltip.style.padding = '8px 12px';
        tooltip.style.borderRadius = '4px';
        tooltip.style.fontSize = '12px';
        tooltip.style.pointerEvents = 'none';
        tooltip.style.opacity = '0';
        tooltip.style.transition = 'opacity 0.3s ease';
        
        // アニメーション
        setTimeout(() => {
            tooltip.style.opacity = '1';
        }, 10);
    }
    
    /**
     * ツールチップ非表示
     */
    hideTooltip() {
        const tooltip = document.getElementById('sectionTooltip');
        if (tooltip) {
            tooltip.remove();
        }
    }
    
    /**
     * ズームイン
     */
    zoomIn() {
        if (this.currentZoom < this.maxZoom) {
            this.currentZoom += this.zoomStep;
            this.updateZoom();
        }
    }
    
    /**
     * ズームアウト
     */
    zoomOut() {
        if (this.currentZoom > this.minZoom) {
            this.currentZoom -= this.zoomStep;
            this.updateZoom();
        }
    }
    
    /**
     * ビューをリセット
     */
    resetView() {
        this.currentZoom = 1;
        this.updateZoom();
    }
    
    /**
     * ズームの更新
     */
    updateZoom() {
        const svg = document.querySelector('.layout-svg-container svg');
        if (svg) {
            svg.style.transform = `scale(${this.currentZoom})`;
        }
        
        // ズームボタンの状態を更新
        const zoomInBtn = document.querySelector('[onclick="zoomIn()"]');
        const zoomOutBtn = document.querySelector('[onclick="zoomOut()"]');
        
        if (zoomInBtn) {
            zoomInBtn.disabled = this.currentZoom >= this.maxZoom;
        }
        if (zoomOutBtn) {
            zoomOutBtn.disabled = this.currentZoom <= this.minZoom;
        }
    }
    
    /**
     * グリッドの表示/非表示
     */
    toggleGrid() {
        this.gridVisible = !this.gridVisible;
        const gridLines = document.querySelectorAll('line');
        gridLines.forEach(line => {
            line.style.display = this.gridVisible ? 'block' : 'none';
        });
        
        // ボタンの状態を更新
        const gridBtn = document.querySelector('[onclick="toggleGrid()"]');
        if (gridBtn) {
            gridBtn.classList.toggle('active', this.gridVisible);
        }
    }
    
    /**
     * ラベルの表示/非表示
     */
    toggleLabels() {
        this.labelsVisible = !this.labelsVisible;
        const labels = document.querySelectorAll('.section-text');
        labels.forEach(label => {
            label.style.display = this.labelsVisible ? 'block' : 'none';
        });
        
        // ボタンの状態を更新
        const labelBtn = document.querySelector('[onclick="toggleLabels()"]');
        if (labelBtn) {
            labelBtn.classList.toggle('active', this.labelsVisible);
        }
    }
    
    /**
     * エクスポートモーダルの準備
     */
    prepareExportModal() {
        // 現在の設定を反映
        document.getElementById('includeGrid').checked = this.gridVisible;
        document.getElementById('includeLegend').checked = true;
    }
    
    /**
     * レイアウトの統計情報を取得
     */
    getLayoutStatistics() {
        const sections = document.querySelectorAll('.section-rect');
        const total = sections.length;
        
        if (total === 0) {
            return {
                total: 0,
                avgConfidence: 0,
                highConfidence: 0,
                mediumConfidence: 0,
                lowConfidence: 0
            };
        }
        
        let totalConfidence = 0;
        let high = 0, medium = 0, low = 0;
        
        sections.forEach(section => {
            const confidence = parseFloat(section.dataset.confidence);
            totalConfidence += confidence;
            
            if (confidence >= 80) high++;
            else if (confidence >= 60) medium++;
            else low++;
        });
        
        return {
            total: total,
            avgConfidence: (totalConfidence / total).toFixed(1),
            highConfidence: high,
            mediumConfidence: medium,
            lowConfidence: low
        };
    }
    
    /**
     * 検索機能
     */
    searchSections(query) {
        const sections = document.querySelectorAll('.shelf-item');
        const results = [];
        
        sections.forEach(section => {
            const shelfNumber = section.dataset.shelf;
            if (shelfNumber.toLowerCase().includes(query.toLowerCase())) {
                results.push(section);
                section.style.display = 'flex';
            } else {
                section.style.display = 'none';
            }
        });
        
        return results;
    }
    
    /**
     * レイアウトの検証
     */
    validateLayout() {
        const sections = document.querySelectorAll('.section-rect');
        const issues = [];
        
        sections.forEach(section => {
            const confidence = parseFloat(section.dataset.confidence);
            const shelfNumber = section.dataset.shelf;
            
            if (confidence < 60) {
                issues.push({
                    type: 'low_confidence',
                    shelf: shelfNumber,
                    confidence: confidence,
                    message: `${shelfNumber}の信頼度が低い (${confidence}%)`
                });
            }
        });
        
        return issues;
    }
}

// グローバル関数（HTMLから呼び出し用）
let layoutViz;

function zoomIn() {
    layoutViz.zoomIn();
}

function zoomOut() {
    layoutViz.zoomOut();
}

function resetView() {
    layoutViz.resetView();
}

function toggleGrid() {
    layoutViz.toggleGrid();
}

function toggleLabels() {
    layoutViz.toggleLabels();
}

// 初期化
document.addEventListener('DOMContentLoaded', () => {
    layoutViz = new LayoutVisualization();
    
    // 初期統計情報の表示
    const stats = layoutViz.getLayoutStatistics();
    console.log('Layout Statistics:', stats);
    
    // レイアウト検証
    const issues = layoutViz.validateLayout();
    if (issues.length > 0) {
        console.warn('Layout Issues:', issues);
    }
});