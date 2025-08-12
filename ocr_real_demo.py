#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OCR実演デモスクリプト
ユーザーが提供した画像を使用してOCR処理を実行し、結果を表示
"""

import os
import sys
import time
from datetime import datetime
import base64
import json

# 必要なライブラリをインポート
try:
    import cv2
    import numpy as np
    from PIL import Image, ImageEnhance
    import pytesseract
except ImportError as e:
    print(f"必要なライブラリがインストールされていません: {e}")
    print("以下のコマンドでインストールしてください:")
    print("pip install opencv-python pillow pytesseract")
    sys.exit(1)

class OCRProcessor:
    """OCR処理を行うクラス"""
    
    def __init__(self):
        self.results = {}
        self.processing_time = 0
        
    def preprocess_image(self, image_path):
        """画像の前処理"""
        try:
            # 画像を読み込み
            image = cv2.imread(image_path)
            if image is None:
                raise ValueError(f"画像を読み込めませんでした: {image_path}")
            
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
        except Exception as e:
            print(f"画像前処理エラー: {e}")
            return None
    
    def extract_text(self, processed_image):
        """テキスト抽出"""
        try:
            # Tesseractの設定
            config = '--oem 3 --psm 6 -l jpn+eng'
            
            # テキスト抽出
            text = pytesseract.image_to_string(processed_image, config=config)
            
            # 詳細データ取得
            data = pytesseract.image_to_data(processed_image, config=config, output_type=pytesseract.Output.DICT)
            
            return text, data
        except Exception as e:
            print(f"テキスト抽出エラー: {e}")
            return "", {}
    
    def analyze_layout(self, data):
        """レイアウト解析"""
        try:
            layout_info = {
                'text_blocks': [],
                'grid_structure': None,
                'dimensions': {},
                'elements': []
            }
            
            # テキストブロックの解析
            n_boxes = len(data['text'])
            for i in range(n_boxes):
                if int(data['conf'][i]) > 30:  # 信頼度30%以上
                    x, y, w, h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
                    text = data['text'][i].strip()
                    if text:
                        layout_info['text_blocks'].append({
                            'text': text,
                            'bbox': [x, y, w, h],
                            'confidence': data['conf'][i]
                        })
            
            # グリッド構造の推定
            if layout_info['text_blocks']:
                # 座標から行・列を推定
                y_positions = sorted(set([block['bbox'][1] for block in layout_info['text_blocks']]))
                x_positions = sorted(set([block['bbox'][0] for block in layout_info['text_blocks']]))
                
                layout_info['grid_structure'] = {
                    'estimated_rows': len(y_positions),
                    'estimated_cols': len(x_positions),
                    'total_elements': len(layout_info['text_blocks'])
                }
            
            return layout_info
        except Exception as e:
            print(f"レイアウト解析エラー: {e}")
            return {}
    
    def generate_cultivation_suggestions(self, text, layout_info):
        """栽培レイアウト提案生成"""
        try:
            suggestions = {
                'layout_type': '不明',
                'recommended_crops': [],
                'system_settings': {},
                'expected_yield': {}
            }
            
            # テキストから情報を抽出
            text_lower = text.lower()
            
            # レイアウトタイプの判定
            if any(keyword in text_lower for keyword in ['水耕', 'hydroponic', 'nft']):
                suggestions['layout_type'] = '水耕栽培システム'
            elif any(keyword in text_lower for keyword in ['ベビーリーフ', 'baby leaf']):
                suggestions['layout_type'] = 'ベビーリーフ栽培'
            elif any(keyword in text_lower for keyword in ['レタス', 'lettuce']):
                suggestions['layout_type'] = 'レタス栽培'
            
            # 作物提案
            if 'リーフ' in text or 'leaf' in text_lower:
                suggestions['recommended_crops'].extend(['リーフレタス', 'ベビーリーフ', 'ルッコラ'])
            if 'ハーブ' in text or 'herb' in text_lower:
                suggestions['recommended_crops'].extend(['バジル', 'パセリ', 'ミント'])
            
            # グリッド情報から提案
            if layout_info.get('grid_structure'):
                grid = layout_info['grid_structure']
                total_plots = grid.get('total_elements', 0)
                
                suggestions['system_settings'] = {
                    '総区画数': total_plots,
                    '推奨給水間隔': '2-3時間',
                    '照明時間': '14時間/日',
                    '温度管理': '18-24°C'
                }
                
                suggestions['expected_yield'] = {
                    '月間収穫予想': f'{total_plots * 3}株',
                    '年間収穫予想': f'{total_plots * 36}株'
                }
            
            return suggestions
        except Exception as e:
            print(f"栽培提案生成エラー: {e}")
            return {}
    
    def process_image(self, image_path):
        """メイン処理"""
        print(f"OCR処理開始: {image_path}")
        start_time = time.time()
        
        try:
            # 1. 画像前処理
            print("1. 画像前処理中...")
            processed_image = self.preprocess_image(image_path)
            if processed_image is None:
                return None
            
            # 2. テキスト抽出
            print("2. テキスト抽出中...")
            text, data = self.extract_text(processed_image)
            
            # 3. レイアウト解析
            print("3. レイアウト解析中...")
            layout_info = self.analyze_layout(data)
            
            # 4. 栽培提案生成
            print("4. 栽培提案生成中...")
            suggestions = self.generate_cultivation_suggestions(text, layout_info)
            
            # 処理時間計算
            self.processing_time = time.time() - start_time
            
            # 結果をまとめ
            self.results = {
                'extracted_text': text,
                'layout_analysis': layout_info,
                'cultivation_suggestions': suggestions,
                'processing_time': self.processing_time,
                'confidence_score': self._calculate_confidence(data),
                'timestamp': datetime.now().isoformat()
            }
            
            print(f"OCR処理完了 (処理時間: {self.processing_time:.2f}秒)")
            return self.results
            
        except Exception as e:
            print(f"OCR処理エラー: {e}")
            return None
    
    def _calculate_confidence(self, data):
        """平均信頼度計算"""
        try:
            confidences = [int(conf) for conf in data['conf'] if int(conf) > 0]
            return sum(confidences) / len(confidences) if confidences else 0
        except:
            return 0

def create_results_html(results, image_path):
    """結果をHTMLで表示"""
    
    # 画像をBase64エンコード
    try:
        with open(image_path, 'rb') as img_file:
            img_data = base64.b64encode(img_file.read()).decode()
        img_src = f"data:image/png;base64,{img_data}"
    except:
        img_src = ""
    
    html_content = f"""
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OCR処理結果 - 水耕栽培管理システム</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
            line-height: 1.6;
        }}
        .container {{
            background: white;
            border-radius: 12px;
            padding: 30px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #2c3e50;
            text-align: center;
            margin-bottom: 30px;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }}
        .timestamp {{
            text-align: center;
            color: #7f8c8d;
            margin-bottom: 30px;
            font-style: italic;
        }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }}
        .stat-card {{
            background: linear-gradient(135deg, #3498db, #2980b9);
            color: white;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
            box-shadow: 0 4px 15px rgba(52, 152, 219, 0.3);
        }}
        .stat-value {{
            font-size: 28px;
            font-weight: bold;
            margin-bottom: 5px;
        }}
        .stat-label {{
            font-size: 14px;
            opacity: 0.9;
        }}
        .image-section {{
            text-align: center;
            margin: 30px 0;
            padding: 20px;
            background-color: #ecf0f1;
            border-radius: 10px;
        }}
        .processed-image {{
            max-width: 100%;
            max-height: 400px;
            border: 2px solid #bdc3c7;
            border-radius: 8px;
            box-shadow: 0 4px 10px rgba(0,0,0,0.2);
        }}
        .results-section {{
            margin: 30px 0;
        }}
        .section-title {{
            font-size: 20px;
            font-weight: bold;
            color: #2c3e50;
            margin-bottom: 15px;
            padding: 10px 0;
            border-bottom: 2px solid #ecf0f1;
            display: flex;
            align-items: center;
        }}
        .section-title::before {{
            content: "📊";
            margin-right: 10px;
            font-size: 24px;
        }}
        .result-content {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            border-left: 4px solid #3498db;
            white-space: pre-wrap;
            font-family: 'Courier New', monospace;
            max-height: 300px;
            overflow-y: auto;
            line-height: 1.5;
        }}
        .json-content {{
            background: #2c3e50;
            color: #ecf0f1;
            padding: 20px;
            border-radius: 8px;
            font-family: 'Courier New', monospace;
            font-size: 12px;
            max-height: 250px;
            overflow-y: auto;
        }}
        .highlight {{
            background-color: #f39c12;
            color: white;
            padding: 2px 6px;
            border-radius: 3px;
            font-weight: bold;
        }}
        .success {{
            background-color: #27ae60;
            color: white;
            padding: 10px 20px;
            border-radius: 5px;
            text-align: center;
            margin: 20px 0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🔍 OCR処理結果レポート</h1>
        <div class="timestamp">
            処理実行日時: {results.get('timestamp', 'Unknown')}
        </div>
        
        <div class="success">
            ✅ OCR処理が正常に完了しました！
        </div>
        
        <div class="stats">
            <div class="stat-card">
                <div class="stat-value">{results.get('processing_time', 0):.2f}秒</div>
                <div class="stat-label">処理時間</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{results.get('confidence_score', 0):.1f}%</div>
                <div class="stat-label">平均信頼度</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{len(results.get('extracted_text', ''))}</div>
                <div class="stat-label">抽出文字数</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{len(results.get('layout_analysis', {}).get('text_blocks', []))}</div>
                <div class="stat-label">検出要素数</div>
            </div>
        </div>
        
        <div class="image-section">
            <h3>📷 処理対象画像</h3>
            <img src="{img_src}" alt="処理対象画像" class="processed-image">
        </div>
        
        <div class="results-section">
            <div class="section-title">抽出されたテキスト</div>
            <div class="result-content">{results.get('extracted_text', 'テキストが抽出されませんでした')}</div>
        </div>
        
        <div class="results-section">
            <div class="section-title">レイアウト解析結果</div>
            <div class="result-content">{format_layout_analysis(results.get('layout_analysis', {}))}</div>
        </div>
        
        <div class="results-section">
            <div class="section-title">栽培レイアウト提案</div>
            <div class="result-content">{format_cultivation_suggestions(results.get('cultivation_suggestions', {}))}</div>
        </div>
        
        <div class="results-section">
            <div class="section-title">詳細データ (JSON)</div>
            <div class="json-content">{json.dumps(results, ensure_ascii=False, indent=2)}</div>
        </div>
    </div>
</body>
</html>
"""
    
    return html_content

def format_layout_analysis(layout_info):
    """レイアウト解析結果をフォーマット"""
    if not layout_info:
        return "レイアウト解析データがありません"
    
    result = []
    
    # グリッド構造
    if 'grid_structure' in layout_info and layout_info['grid_structure']:
        grid = layout_info['grid_structure']
        result.append("🏗️ グリッド構造:")
        result.append(f"  - 推定行数: {grid.get('estimated_rows', 'N/A')}")
        result.append(f"  - 推定列数: {grid.get('estimated_cols', 'N/A')}")
        result.append(f"  - 総要素数: {grid.get('total_elements', 'N/A')}")
        result.append("")
    
    # テキストブロック
    if 'text_blocks' in layout_info and layout_info['text_blocks']:
        result.append("📝 検出されたテキストブロック:")
        for i, block in enumerate(layout_info['text_blocks'][:10]):  # 最大10個表示
            result.append(f"  {i+1}. '{block['text']}' (信頼度: {block['confidence']:.1f}%)")
        
        if len(layout_info['text_blocks']) > 10:
            result.append(f"  ... 他 {len(layout_info['text_blocks']) - 10} 個のブロック")
    
    return "\\n".join(result) if result else "解析結果がありません"

def format_cultivation_suggestions(suggestions):
    """栽培提案をフォーマット"""
    if not suggestions:
        return "栽培提案データがありません"
    
    result = []
    
    # レイアウトタイプ
    result.append(f"🌱 レイアウトタイプ: {suggestions.get('layout_type', '不明')}")
    result.append("")
    
    # 推奨作物
    if suggestions.get('recommended_crops'):
        result.append("🥬 推奨作物:")
        for crop in suggestions['recommended_crops']:
            result.append(f"  - {crop}")
        result.append("")
    
    # システム設定
    if suggestions.get('system_settings'):
        result.append("⚙️ システム設定:")
        for key, value in suggestions['system_settings'].items():
            result.append(f"  - {key}: {value}")
        result.append("")
    
    # 収穫予想
    if suggestions.get('expected_yield'):
        result.append("📈 収穫予想:")
        for key, value in suggestions['expected_yield'].items():
            result.append(f"  - {key}: {value}")
    
    return "\\n".join(result) if result else "提案データがありません"

def main():
    """メイン実行関数"""
    # 画像ファイルのパス
    image_path = "スクリーンショット 2025-07-15 1.37.27.png"
    
    if not os.path.exists(image_path):
        print(f"エラー: 画像ファイルが見つかりません: {image_path}")
        return
    
    # OCR処理実行
    processor = OCRProcessor()
    results = processor.process_image(image_path)
    
    if results is None:
        print("OCR処理に失敗しました")
        return
    
    # 結果をHTMLで保存
    html_content = create_results_html(results, image_path)
    output_file = f"ocr_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"\\n✅ OCR処理完了!")
    print(f"📊 結果ファイル: {output_file}")
    print(f"⏱️  処理時間: {results['processing_time']:.2f}秒")
    print(f"📈 信頼度: {results['confidence_score']:.1f}%")
    print(f"📝 抽出文字数: {len(results['extracted_text'])}")
    
    return output_file

if __name__ == "__main__":
    output_file = main() 