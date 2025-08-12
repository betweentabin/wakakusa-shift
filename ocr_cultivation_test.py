#!/usr/bin/env python3
"""
栽培区画認識OCR機能テストスクリプト
改良されたOCR機能の精度向上を検証
"""

import os
import sys
import django
from pathlib import Path
import time
import json
from typing import List, Dict, Any

# Djangoプロジェクトのパスを追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Django設定
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings.development')
django.setup()

# OCRユーティリティをインポート
from cultivation.ocr_utils import DocumentOCR

class OCRCultivationTester:
    """栽培区画OCR機能テスター"""
    
    def __init__(self):
        self.ocr = DocumentOCR(debug_mode=True)
        self.test_results = []
        
    def run_comprehensive_test(self):
        """包括的テスト実行"""
        print("🌱 栽培区画OCR精度向上テスト開始")
        print("=" * 60)
        
        # テスト画像の検索
        test_images = self._find_test_images()
        
        if not test_images:
            print("⚠️  テスト画像が見つかりません")
            self._create_test_report()
            return
        
        print(f"📂 {len(test_images)}個のテスト画像を発見")
        
        # 各画像でテスト実行
        for i, image_path in enumerate(test_images, 1):
            print(f"\n🔍 テスト {i}/{len(test_images)}: {image_path.name}")
            result = self._test_single_image(image_path)
            self.test_results.append(result)
            
        # 結果分析とレポート作成
        self._analyze_results()
        self._create_test_report()
        
    def _find_test_images(self) -> List[Path]:
        """テスト画像の検索"""
        test_directories = [
            project_root / "media" / "test_images",
            project_root / "cultivation" / "test_data",
            project_root / "static" / "test_images",
            project_root,  # プロジェクトルート
        ]
        
        image_extensions = ['.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.pdf']
        found_images = []
        
        for directory in test_directories:
            if directory.exists():
                for ext in image_extensions:
                    found_images.extend(directory.glob(f"*{ext}"))
                    found_images.extend(directory.glob(f"**/*{ext}"))
        
        # 重複除去
        unique_images = []
        seen_names = set()
        for img in found_images:
            if img.name not in seen_names:
                unique_images.append(img)
                seen_names.add(img.name)
        
        return unique_images[:10]  # 最大10枚まで
        
    def _test_single_image(self, image_path: Path) -> Dict[str, Any]:
        """単一画像のテスト"""
        start_time = time.time()
        
        try:
            # OCR実行
            ocr_result = self.ocr.process_file(str(image_path))
            processing_time = time.time() - start_time
            
            # 結果分析
            analysis = self._analyze_ocr_result(ocr_result)
            
            result = {
                'image_path': str(image_path),
                'image_name': image_path.name,
                'processing_time': round(processing_time, 2),
                'success': ocr_result.get('success', False),
                'total_texts': analysis['total_texts'],
                'high_confidence_texts': analysis['high_confidence_texts'],
                'cultivation_related': analysis['cultivation_related'],
                'avg_confidence': analysis['avg_confidence'],
                'detected_types': analysis['detected_types'],
                'performance_stats': ocr_result.get('debug_info', {}).get('performance_stats', {}),
                'error': ocr_result.get('error') if not ocr_result.get('success') else None
            }
            
            # 詳細結果の表示
            self._print_test_result(result, ocr_result)
            
            return result
            
        except Exception as e:
            processing_time = time.time() - start_time
            
            error_result = {
                'image_path': str(image_path),
                'image_name': image_path.name,
                'processing_time': round(processing_time, 2),
                'success': False,
                'error': str(e),
                'total_texts': 0,
                'high_confidence_texts': 0,
                'cultivation_related': 0,
                'avg_confidence': 0,
                'detected_types': {}
            }
            
            print(f"❌ エラー: {e}")
            return error_result
    
    def _analyze_ocr_result(self, ocr_result: Dict) -> Dict[str, Any]:
        """OCR結果の分析"""
        analysis = {
            'total_texts': 0,
            'high_confidence_texts': 0,
            'cultivation_related': 0,
            'avg_confidence': 0,
            'detected_types': {}
        }
        
        if not ocr_result.get('success') or not ocr_result.get('pages'):
            return analysis
        
        all_texts = []
        cultivation_keywords = [
            'トマト', 'きゅうり', 'なす', 'ピーマン', 'レタス', 'キャベツ',
            '区画', '棚', 'ハウス', '温室', '品種', '苗', 'A棟', 'B棟', 'C棟'
        ]
        
        for page in ocr_result['pages']:
            if 'shelf_info' in page:
                # 既存形式（棚情報）
                for shelf in page['shelf_info']:
                    text_info = {
                        'text': shelf.get('text', ''),
                        'confidence': shelf.get('confidence', 0),
                        'cultivation_type': shelf.get('cultivation_type', 'unknown')
                    }
                    all_texts.append(text_info)
            else:
                # 新形式（テキスト情報）
                # デバッグ情報から抽出を試行
                debug_info = ocr_result.get('debug_info', {})
                if 'processing_log' in debug_info:
                    # ログから認識されたテキスト数を推定
                    for log_entry in debug_info['processing_log']:
                        if 'final_results' in log_entry.get('data', {}):
                            analysis['total_texts'] = log_entry['data']['final_results']
                            analysis['avg_confidence'] = log_entry['data'].get('avg_confidence', 0)
                            break
        
        if all_texts:
            analysis['total_texts'] = len(all_texts)
            analysis['high_confidence_texts'] = len([t for t in all_texts if t['confidence'] >= 70])
            analysis['avg_confidence'] = sum(t['confidence'] for t in all_texts) / len(all_texts)
            
            # 栽培関連テキストのカウント
            for text_info in all_texts:
                text = text_info['text']
                if any(keyword in text for keyword in cultivation_keywords):
                    analysis['cultivation_related'] += 1
                
                # タイプ別カウント
                cult_type = text_info.get('cultivation_type', 'unknown')
                analysis['detected_types'][cult_type] = analysis['detected_types'].get(cult_type, 0) + 1
        
        return analysis
    
    def _print_test_result(self, result: Dict, ocr_result: Dict):
        """テスト結果の表示"""
        if result['success']:
            print(f"✅ 成功 - 処理時間: {result['processing_time']}秒")
            print(f"   📝 認識テキスト数: {result['total_texts']}")
            print(f"   🎯 高信頼度テキスト: {result['high_confidence_texts']}")
            print(f"   🌱 栽培関連テキスト: {result['cultivation_related']}")
            print(f"   📊 平均信頼度: {result['avg_confidence']:.1f}%")
            
            if result['detected_types']:
                print(f"   🏷️  検出タイプ: {dict(result['detected_types'])}")
            
            # パフォーマンス統計
            perf_stats = result.get('performance_stats', {})
            if perf_stats and 'processing_times' in perf_stats:
                times = perf_stats['processing_times']
                print(f"   ⚡ 前処理時間: {times.get('preprocessing', 0):.2f}秒")
                print(f"   🔍 OCR実行時間: {times.get('ocr', 0):.2f}秒")
                
        else:
            print(f"❌ 失敗 - エラー: {result.get('error', '不明')}")
    
    def _analyze_results(self):
        """結果の全体分析"""
        if not self.test_results:
            return
        
        print("\n📊 テスト結果総括")
        print("=" * 60)
        
        successful_tests = [r for r in self.test_results if r['success']]
        failed_tests = [r for r in self.test_results if not r['success']]
        
        print(f"✅ 成功: {len(successful_tests)}/{len(self.test_results)} ({len(successful_tests)/len(self.test_results)*100:.1f}%)")
        print(f"❌ 失敗: {len(failed_tests)}/{len(self.test_results)} ({len(failed_tests)/len(self.test_results)*100:.1f}%)")
        
        if successful_tests:
            avg_processing_time = sum(r['processing_time'] for r in successful_tests) / len(successful_tests)
            avg_text_count = sum(r['total_texts'] for r in successful_tests) / len(successful_tests)
            avg_confidence = sum(r['avg_confidence'] for r in successful_tests) / len(successful_tests)
            total_cultivation_related = sum(r['cultivation_related'] for r in successful_tests)
            
            print(f"\n📈 平均値:")
            print(f"   ⏱️  処理時間: {avg_processing_time:.2f}秒")
            print(f"   📝 認識テキスト数: {avg_text_count:.1f}")
            print(f"   🎯 平均信頼度: {avg_confidence:.1f}%")
            print(f"   🌱 栽培関連テキスト合計: {total_cultivation_related}")
            
            # 最高性能の画像
            best_result = max(successful_tests, key=lambda x: x['avg_confidence'])
            print(f"\n🏆 最高精度:")
            print(f"   📄 画像: {best_result['image_name']}")
            print(f"   🎯 信頼度: {best_result['avg_confidence']:.1f}%")
            print(f"   📝 認識数: {best_result['total_texts']}")
        
        if failed_tests:
            print(f"\n⚠️  失敗理由:")
            error_counts = {}
            for test in failed_tests:
                error = test.get('error', '不明')
                error_counts[error] = error_counts.get(error, 0) + 1
            
            for error, count in error_counts.items():
                print(f"   • {error}: {count}件")
    
    def _create_test_report(self):
        """テストレポートの作成"""
        report_path = project_root / "ocr_cultivation_test_report.html"
        
        html_content = self._generate_html_report()
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"\n📄 詳細レポートを作成しました: {report_path}")
        
        # JSON形式でも保存
        json_path = project_root / "ocr_cultivation_test_results.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump({
                'test_timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'total_tests': len(self.test_results),
                'results': self.test_results
            }, f, ensure_ascii=False, indent=2)
        
        print(f"📊 JSON結果データ: {json_path}")
    
    def _generate_html_report(self) -> str:
        """HTMLレポート生成"""
        timestamp = time.strftime('%Y年%m月%d日 %H:%M:%S')
        successful_tests = [r for r in self.test_results if r['success']]
        
        html = f"""
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>栽培区画OCR精度向上テスト結果</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 20px; line-height: 1.6; }}
        .header {{ background: linear-gradient(135deg, #4CAF50, #45a049); color: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; }}
        .summary {{ background: #f8f9fa; padding: 15px; border-radius: 8px; margin-bottom: 20px; }}
        .test-result {{ border: 1px solid #ddd; border-radius: 8px; margin-bottom: 15px; padding: 15px; }}
        .success {{ border-left: 5px solid #4CAF50; }}
        .failure {{ border-left: 5px solid #f44336; }}
        .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; }}
        .metric {{ background: #fff; padding: 10px; border-radius: 5px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .improvement {{ background: #e8f5e8; padding: 10px; border-radius: 5px; margin: 10px 0; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
        .confidence-high {{ color: #4CAF50; font-weight: bold; }}
        .confidence-medium {{ color: #ff9800; font-weight: bold; }}
        .confidence-low {{ color: #f44336; font-weight: bold; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🌱 栽培区画OCR精度向上テスト結果</h1>
        <p>実行日時: {timestamp}</p>
        <p>高度な前処理機能 + 栽培区画特化OCRの性能評価</p>
    </div>
    
    <div class="summary">
        <h2>📊 テスト概要</h2>
        <div class="metrics">
            <div class="metric">
                <h3>総テスト数</h3>
                <p style="font-size: 2em; margin: 0;">{len(self.test_results)}</p>
            </div>
            <div class="metric">
                <h3>成功率</h3>
                <p style="font-size: 2em; margin: 0; color: #4CAF50;">
                    {len(successful_tests)/len(self.test_results)*100 if self.test_results else 0:.1f}%
                </p>
            </div>
        """
        
        if successful_tests:
            avg_confidence = sum(r['avg_confidence'] for r in successful_tests) / len(successful_tests)
            total_cultivation = sum(r['cultivation_related'] for r in successful_tests)
            
            html += f"""
            <div class="metric">
                <h3>平均信頼度</h3>
                <p style="font-size: 2em; margin: 0;" class="{'confidence-high' if avg_confidence >= 80 else 'confidence-medium' if avg_confidence >= 60 else 'confidence-low'}">
                    {avg_confidence:.1f}%
                </p>
            </div>
            <div class="metric">
                <h3>栽培関連認識</h3>
                <p style="font-size: 2em; margin: 0; color: #4CAF50;">{total_cultivation}</p>
            </div>
        </div>
        
        <div class="improvement">
            <h3>🚀 精度向上のポイント</h3>
            <ul>
                <li><strong>歪み補正</strong>: スキャン時の台形歪みを自動補正</li>
                <li><strong>超解像処理</strong>: 低解像度画像を2倍に拡大してシャープ化</li>
                <li><strong>マルチモードOCR</strong>: 数字・日本語・英数字に特化した複数のOCRを並列実行</li>
                <li><strong>栽培語彙認識</strong>: 品種名・区画番号・管理コードを高精度で認識</li>
                <li><strong>アダプティブノイズ除去</strong>: 画像の特性に応じた最適なノイズ除去</li>
                <li><strong>多段階二値化</strong>: 複数の閾値で最適な二値化手法を自動選択</li>
            </ul>
        </div>
    </div>
    
    <h2>📋 詳細テスト結果</h2>
    """
        
        # 各テスト結果の詳細
        for i, result in enumerate(self.test_results, 1):
            css_class = "success" if result['success'] else "failure"
            status_icon = "✅" if result['success'] else "❌"
            
            html += f"""
    <div class="test-result {css_class}">
        <h3>{status_icon} テスト {i}: {result['image_name']}</h3>
        """
            
            if result['success']:
                confidence_class = ('confidence-high' if result['avg_confidence'] >= 80 
                                 else 'confidence-medium' if result['avg_confidence'] >= 60 
                                 else 'confidence-low')
                
                html += f"""
        <table>
            <tr><th>項目</th><th>値</th></tr>
            <tr><td>処理時間</td><td>{result['processing_time']}秒</td></tr>
            <tr><td>認識テキスト数</td><td>{result['total_texts']}</td></tr>
            <tr><td>高信頼度テキスト</td><td>{result['high_confidence_texts']}</td></tr>
            <tr><td>栽培関連テキスト</td><td style="color: #4CAF50; font-weight: bold;">{result['cultivation_related']}</td></tr>
            <tr><td>平均信頼度</td><td class="{confidence_class}">{result['avg_confidence']:.1f}%</td></tr>
        </table>
        """
                
                if result['detected_types']:
                    html += f"<p><strong>検出タイプ:</strong> {dict(result['detected_types'])}</p>"
            else:
                html += f"<p style='color: #f44336;'><strong>エラー:</strong> {result.get('error', '不明なエラー')}</p>"
            
            html += "</div>"
        
        html += """
</body>
</html>
"""
        return html

def main():
    """メイン関数"""
    print("栽培区画OCR精度向上テストを開始します...")
    
    tester = OCRCultivationTester()
    tester.run_comprehensive_test()
    
    print("\n🎉 テスト完了!")
    print("詳細な結果はHTMLレポートとJSONファイルをご確認ください。")

if __name__ == "__main__":
    main()