"""
OCR機能ユーティリティモジュール
図面解析・OCR機能を提供するクラス群
"""
import cv2
import numpy as np
import pytesseract
from PIL import Image
import pdf2image
import re
import os
import hashlib
import time
import logging
import json
from typing import List, Dict, Tuple, Optional
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone


class DocumentOCR:
    """図面・文書のOCR処理クラス"""
    
    def __init__(self, debug_mode=False):
        # OCR設定の取得
        self.ocr_settings = getattr(settings, 'OCR_SETTINGS', {})
        
        # デバッグモード設定
        self.debug_mode = debug_mode or self.ocr_settings.get('DEBUG_MODE', False)
        self.processing_log = []
        
        # ログ設定
        self.logger = logging.getLogger('ocr_processing')
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO if self.debug_mode else logging.WARNING)
        
        # Tesseractの設定
        tesseract_cmd = self.ocr_settings.get('TESSERACT_CMD', '/opt/homebrew/bin/tesseract')
        if os.path.exists(tesseract_cmd):
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
        
        # OCR言語設定
        languages = self.ocr_settings.get('OCR_LANGUAGES', 'jpn+eng')
        self.tesseract_config = f'--oem 3 --psm 6 -l {languages}'
        
        # キャッシュ設定
        self.cache_enabled = self.ocr_settings.get('CACHE_ENABLED', True)
        self.cache_duration = self.ocr_settings.get('CACHE_DURATION', 3600)
        
        # 画像前処理設定
        self.preprocessing_config = self.ocr_settings.get('IMAGE_PREPROCESSING', {})
        
        # パフォーマンス追跡
        self.performance_stats = {
            'start_time': None,
            'processing_times': {},
            'memory_usage': {},
        }
        
        # 動的パラメータ調整
        self.adaptive_settings = self.ocr_settings.get('ADAPTIVE_SETTINGS', {
            'enabled': True,
            'confidence_fallback_threshold': 50,
            'retry_with_different_psm': True,
            'psm_modes': [6, 8, 7, 3],  # 試行する PSM モード
            'max_retries': 3
        })
        
    def process_uploaded_file(self, file_path: str) -> Dict:
        """アップロードされたファイルを処理"""
        self.performance_stats['start_time'] = time.time()
        self.processing_log = []
        
        try:
            self._log_step("処理開始", {"file_path": file_path})
            
            # ファイル情報の記録
            file_size = os.path.getsize(file_path)
            file_extension = file_path.lower().split('.')[-1]
            self._log_step("ファイル情報取得", {
                "size": file_size,
                "extension": file_extension
            })
            
            # キャッシュチェック
            start_cache = time.time()
            if self.cache_enabled:
                cached_result = self._get_cached_result(file_path)
                if cached_result:
                    self._log_step("キャッシュヒット", {"cache_time": time.time() - start_cache})
                    cached_result['debug_info'] = self._generate_debug_info()
                    return cached_result
            self.performance_stats['processing_times']['cache_check'] = time.time() - start_cache
            
            # ファイル処理
            start_processing = time.time()
            if file_extension == 'pdf':
                result = self.process_pdf(file_path)
            elif file_extension in ['png', 'jpg', 'jpeg', 'tiff', 'bmp']:
                result = self.process_image(file_path)
            else:
                raise ValueError(f"未対応のファイル形式: {file_extension}")
            
            self.performance_stats['processing_times']['main_processing'] = time.time() - start_processing
            
            # デバッグ情報を結果に追加
            if self.debug_mode:
                result['debug_info'] = self._generate_debug_info()
            
            # 結果をキャッシュに保存
            start_cache_save = time.time()
            if self.cache_enabled and result.get('success'):
                self._cache_result(file_path, result)
            self.performance_stats['processing_times']['cache_save'] = time.time() - start_cache_save
            
            self._log_step("処理完了", {"total_time": time.time() - self.performance_stats['start_time']})
            
            return result
            
        except Exception as e:
            error_info = {
                'success': False,
                'error': str(e),
                'error_type': type(e).__name__
            }
            
            if self.debug_mode:
                error_info['debug_info'] = self._generate_debug_info()
                error_info['stack_trace'] = str(e)
            
            self._log_step("エラー発生", error_info)
            return error_info
    
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
        try:
            start_step = time.time()
            self._log_step("PIL画像処理開始", {"image_size": pil_image.size})
            
            # OpenCV形式に変換
            start_convert = time.time()
            cv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
            self.performance_stats['processing_times']['image_convert'] = time.time() - start_convert
            self._log_step("OpenCV変換完了", {"shape": cv_image.shape})
            
            # 前処理
            start_preprocess = time.time()
            processed_image = self.preprocess_image(cv_image)
            self.performance_stats['processing_times']['preprocessing'] = time.time() - start_preprocess
            
            # OCR実行
            start_ocr = time.time()
            ocr_result = self.extract_text(processed_image)
            self.performance_stats['processing_times']['ocr'] = time.time() - start_ocr
            self._log_step("OCR実行完了", {"text_count": len(ocr_result)})
            
            # 図形検出
            start_shapes = time.time()
            shapes = self.detect_shapes(processed_image)
            self.performance_stats['processing_times']['shape_detection'] = time.time() - start_shapes
            self._log_step("図形検出完了", {"shape_count": len(shapes)})
            
            # 棚情報の抽出
            start_shelf = time.time()
            shelf_info = self.extract_shelf_information(ocr_result, shapes)
            self.performance_stats['processing_times']['shelf_extraction'] = time.time() - start_shelf
            self._log_step("棚情報抽出完了", {"shelf_count": len(shelf_info)})
            
            self.performance_stats['processing_times']['total_pil_processing'] = time.time() - start_step
            
            return {
                'ocr_text': ocr_result,
                'shapes': shapes,
                'shelf_info': shelf_info,
                'image_size': pil_image.size
            }
        except Exception as e:
            self._log_step("PIL画像処理エラー", {"error": str(e)})
            return {
                'ocr_text': [],
                'shapes': [],
                'shelf_info': [],
                'image_size': (0, 0),
                'error': str(e)
            }
    
    def preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """高度な画像前処理（栽培区画認識用に最適化）"""
        try:
            self._log_step("高度前処理開始", {"input_shape": image.shape})
            
            # 自動回転補正
            start_rotation = time.time()
            corrected_image = self._auto_rotate_correction(image)
            self.performance_stats['processing_times']['rotation_correction'] = time.time() - start_rotation
            self._log_step("回転補正完了", {"corrected_shape": corrected_image.shape})
            
            # グレースケール変換
            start_gray = time.time()
            gray = cv2.cvtColor(corrected_image, cv2.COLOR_BGR2GRAY)
            self.performance_stats['processing_times']['grayscale'] = time.time() - start_gray
            
            # 歪み補正（台形補正）
            start_perspective = time.time()
            perspective_corrected = self._perspective_correction(gray)
            self.performance_stats['processing_times']['perspective_correction'] = time.time() - start_perspective
            self._log_step("歪み補正完了")
            
            # 解像度向上（超解像処理）
            start_super_res = time.time()
            enhanced_resolution = self._enhance_resolution(perspective_corrected)
            self.performance_stats['processing_times']['super_resolution'] = time.time() - start_super_res
            self._log_step("解像度向上完了")
            
            # アダプティブノイズ除去
            start_adaptive_denoise = time.time()
            adaptive_denoised = self._adaptive_denoise(enhanced_resolution)
            self.performance_stats['processing_times']['adaptive_denoising'] = time.time() - start_adaptive_denoise
            self._log_step("アダプティブノイズ除去完了")
            
            # テキスト領域強化
            start_text_enhance = time.time()
            text_enhanced = self._enhance_text_regions(adaptive_denoised)
            self.performance_stats['processing_times']['text_enhancement'] = time.time() - start_text_enhance
            self._log_step("テキスト領域強化完了")
            
            # 多段階二値化
            start_multi_binary = time.time()
            multi_binary = self._multi_stage_binarization(text_enhanced)
            self.performance_stats['processing_times']['multi_binarization'] = time.time() - start_multi_binary
            self._log_step("多段階二値化完了")
            
            # 文字形状補正
            start_char_correction = time.time()
            char_corrected = self._character_shape_correction(multi_binary)
            self.performance_stats['processing_times']['character_correction'] = time.time() - start_char_correction
            self._log_step("文字形状補正完了")
            
            return char_corrected
            
        except Exception as e:
            self._log_step("高度前処理エラー", {"error": str(e)})
            # エラーの場合は基本前処理にフォールバック
            return self._basic_preprocess(image)
    
    def _auto_rotate_correction(self, image: np.ndarray) -> np.ndarray:
        """自動回転補正"""
        try:
            # グレースケール変換（既にグレースケールの場合は何もしない）
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image.copy()
            
            # 輪郭検出で直線を見つける
            edges = cv2.Canny(gray, 50, 150, apertureSize=3)
            lines = cv2.HoughLines(edges, 1, np.pi/180, threshold=100)
            
            if lines is not None:
                angles = []
                for rho, theta in lines[:10]:  # 上位10本の直線のみ考慮
                    angle = theta * 180 / np.pi
                    # 水平線に近い角度を抽出
                    if angle < 45 or angle > 135:
                        if angle > 90:
                            angle = angle - 180
                        angles.append(angle)
                
                if angles:
                    # 中央値を使用して回転角度を決定
                    rotation_angle = np.median(angles)
                    
                    # 回転補正を実行（±10度以内の場合のみ）
                    if abs(rotation_angle) > 0.5 and abs(rotation_angle) < 10:
                        h, w = image.shape[:2]
                        center = (w // 2, h // 2)
                        rotation_matrix = cv2.getRotationMatrix2D(center, rotation_angle, 1.0)
                        corrected = cv2.warpAffine(image, rotation_matrix, (w, h), 
                                                 flags=cv2.INTER_CUBIC, 
                                                 borderMode=cv2.BORDER_REPLICATE)
                        self._log_step("回転補正適用", {"angle": rotation_angle})
                        return corrected
            
            self._log_step("回転補正不要", {"reason": "適切な直線が見つからない"})
            return image
            
        except Exception as e:
            self._log_step("回転補正エラー", {"error": str(e)})
            return image
    
    def extract_text(self, image: np.ndarray) -> List[Dict]:
        """栽培区画認識に特化したテキスト抽出"""
        try:
            self._log_step("栽培区画特化OCR開始", {"image_shape": image.shape})
            
            # マルチモードOCR実行
            all_results = []
            
            # 1. 標準モード（一般的なテキスト）
            standard_results = self._run_standard_ocr(image)
            all_results.extend(standard_results)
            self._log_step("標準OCR完了", {"results": len(standard_results)})
            
            # 2. 数字特化モード（区画番号など）
            numeric_results = self._run_numeric_specialized_ocr(image)
            all_results.extend(numeric_results)
            self._log_step("数字特化OCR完了", {"results": len(numeric_results)})
            
            # 3. 日本語特化モード（栽培区画名など）
            japanese_results = self._run_japanese_specialized_ocr(image)
            all_results.extend(japanese_results)
            self._log_step("日本語特化OCR完了", {"results": len(japanese_results)})
            
            # 4. 英数字特化モード（品種コードなど）
            alphanumeric_results = self._run_alphanumeric_specialized_ocr(image)
            all_results.extend(alphanumeric_results)
            self._log_step("英数字特化OCR完了", {"results": len(alphanumeric_results)})
            
            # 結果のマージと重複除去
            merged_results = self._merge_and_deduplicate_results(all_results)
            
            # 栽培区画コンテキストでの後処理
            processed_results = self._post_process_cultivation_context(merged_results)
            
            # 信頼度による最終フィルタリング
            final_results = self._apply_cultivation_confidence_filter(processed_results)
            
            self._log_step("栽培区画特化OCR完了", {
                "total_raw_results": len(all_results),
                "merged_results": len(merged_results),
                "final_results": len(final_results),
                "avg_confidence": sum(r['confidence'] for r in final_results) / len(final_results) if final_results else 0
            })
            
            return final_results
            
        except Exception as e:
            self._log_step("栽培区画特化OCRエラー", {"error": str(e)})
            # フォールバック：基本OCR
            return self._run_basic_fallback_ocr(image)
    
    def _run_ocr_with_config(self, image: np.ndarray, config: str) -> List[Dict]:
        """指定された設定でOCRを実行"""
        try:
            # OCR実行（詳細情報付き）
            data = pytesseract.image_to_data(image, config=config, output_type=pytesseract.Output.DICT)
            
            texts = []
            confidence_threshold = self.ocr_settings.get('DEFAULT_CONFIDENCE_THRESHOLD', 60)
            
            for i in range(len(data['text'])):
                if int(data['conf'][i]) > confidence_threshold:
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
            self._log_step("OCR設定エラー", {"config": config, "error": str(e)})
            return []
    
    def _run_standard_ocr(self, image: np.ndarray) -> List[Dict]:
        """標準OCR実行"""
        languages = self.ocr_settings.get('OCR_LANGUAGES', 'jpn+eng')
        config = f'--oem 3 --psm 6 -l {languages}'
        return self._run_ocr_with_config(image, config)
    
    def _run_numeric_specialized_ocr(self, image: np.ndarray) -> List[Dict]:
        """数字特化OCR（区画番号、棚番号用）"""
        try:
            # 数字のみに特化した設定
            numeric_configs = [
                '--oem 3 --psm 8 -c tessedit_char_whitelist=0123456789',  # 数字のみ、単語レベル
                '--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789',  # 数字のみ、単一行
                '--oem 3 --psm 13 -c tessedit_char_whitelist=0123456789', # 数字のみ、生文字列
            ]
            
            all_numeric_results = []
            for config in numeric_configs:
                results = self._run_ocr_with_config(image, config)
                # 数字パターンを追加分析
                for result in results:
                    if self._is_cultivation_number(result['text']):
                        result['specialized_type'] = 'numeric'
                        result['confidence'] += 10  # 数字特化ボーナス
                        all_numeric_results.append(result)
            
            return all_numeric_results
            
        except Exception as e:
            self._log_step("数字特化OCRエラー", {"error": str(e)})
            return []
    
    def _run_japanese_specialized_ocr(self, image: np.ndarray) -> List[Dict]:
        """日本語特化OCR（栽培区画名、品種名用）"""
        try:
            # 日本語に特化した設定
            japanese_configs = [
                '--oem 3 --psm 6 -l jpn',  # 日本語のみ、統一ブロック
                '--oem 3 --psm 7 -l jpn',  # 日本語のみ、単一行
                '--oem 3 --psm 8 -l jpn',  # 日本語のみ、単語レベル
            ]
            
            all_japanese_results = []
            for config in japanese_configs:
                results = self._run_ocr_with_config(image, config)
                # 日本語パターンを追加分析
                for result in results:
                    if self._contains_japanese(result['text']):
                        result['specialized_type'] = 'japanese'
                        # 栽培関連語彙チェック
                        if self._is_cultivation_vocabulary(result['text']):
                            result['confidence'] += 15  # 栽培語彙ボーナス
                        else:
                            result['confidence'] += 5   # 日本語ボーナス
                        all_japanese_results.append(result)
            
            return all_japanese_results
            
        except Exception as e:
            self._log_step("日本語特化OCRエラー", {"error": str(e)})
            return []
    
    def _run_alphanumeric_specialized_ocr(self, image: np.ndarray) -> List[Dict]:
        """英数字特化OCR（品種コード、管理番号用）"""
        try:
            # 英数字に特化した設定
            alphanumeric_configs = [
                '--oem 3 --psm 8 -l eng -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789',
                '--oem 3 --psm 7 -l eng -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_',
                '--oem 3 --psm 6 -l eng',  # 標準英語
            ]
            
            all_alphanumeric_results = []
            for config in alphanumeric_configs:
                results = self._run_ocr_with_config(image, config)
                # 英数字パターンを追加分析
                for result in results:
                    if self._is_alphanumeric_code(result['text']):
                        result['specialized_type'] = 'alphanumeric'
                        result['confidence'] += 8  # 英数字ボーナス
                        all_alphanumeric_results.append(result)
            
            return all_alphanumeric_results
            
        except Exception as e:
            self._log_step("英数字特化OCRエラー", {"error": str(e)})
            return []
    
    def _merge_and_deduplicate_results(self, all_results: List[Dict]) -> List[Dict]:
        """結果のマージと重複除去"""
        try:
            if not all_results:
                return []
            
            # 位置による重複除去（同じ場所の似たテキストをマージ）
            merged = []
            
            for result in all_results:
                is_duplicate = False
                
                for existing in merged:
                    # 位置の重複チェック
                    if self._is_overlapping_bbox(result['bbox'], existing['bbox']):
                        # テキストの類似度チェック
                        similarity = self._calculate_text_similarity(result['text'], existing['text'])
                        
                        if similarity > 0.8:  # 80%以上類似
                            # より信頼度の高い結果を採用
                            if result['confidence'] > existing['confidence']:
                                # 既存を更新
                                existing.update(result)
                            is_duplicate = True
                            break
                
                if not is_duplicate:
                    merged.append(result)
            
            self._log_step("重複除去完了", {
                "original_count": len(all_results),
                "merged_count": len(merged)
            })
            
            return merged
            
        except Exception as e:
            self._log_step("重複除去エラー", {"error": str(e)})
            return all_results
    
    def _post_process_cultivation_context(self, results: List[Dict]) -> List[Dict]:
        """栽培区画コンテキストでの後処理"""
        try:
            processed = []
            
            for result in results:
                # テキストの正規化
                normalized_text = self._normalize_cultivation_text(result['text'])
                result['normalized_text'] = normalized_text
                
                # 栽培区画タイプの推定
                cultivation_type = self._estimate_cultivation_type(normalized_text)
                result['cultivation_type'] = cultivation_type
                
                # コンテキストボーナス適用
                context_bonus = self._calculate_context_bonus(result)
                result['confidence'] = min(100, result['confidence'] + context_bonus)
                
                processed.append(result)
            
            return processed
            
        except Exception as e:
            self._log_step("栽培コンテキスト後処理エラー", {"error": str(e)})
            return results
    
    def _apply_cultivation_confidence_filter(self, results: List[Dict]) -> List[Dict]:
        """栽培区画特化の信頼度フィルタリング"""
        try:
            # 栽培区画コンテキストでの動的閾値
            base_threshold = self.ocr_settings.get('DEFAULT_CONFIDENCE_THRESHOLD', 60)
            
            filtered = []
            for result in results:
                # タイプ別閾値調整
                type_threshold = base_threshold
                cultivation_type = result.get('cultivation_type', 'unknown')
                
                if cultivation_type == 'section_number':
                    type_threshold = max(50, base_threshold - 10)  # 区画番号は少し緩く
                elif cultivation_type == 'variety_name':
                    type_threshold = max(55, base_threshold - 5)   # 品種名は少し緩く
                elif cultivation_type == 'measurement':
                    type_threshold = base_threshold + 5            # 測定値は少し厳しく
                
                if result['confidence'] >= type_threshold:
                    filtered.append(result)
            
            self._log_step("栽培特化フィルタリング完了", {
                "input_count": len(results),
                "filtered_count": len(filtered),
                "base_threshold": base_threshold
            })
            
            return filtered
            
        except Exception as e:
            self._log_step("栽培特化フィルタリングエラー", {"error": str(e)})
            return results
    
    def _run_basic_fallback_ocr(self, image: np.ndarray) -> List[Dict]:
        """基本フォールバックOCR"""
        try:
            languages = self.ocr_settings.get('OCR_LANGUAGES', 'jpn+eng')
            config = f'--oem 3 --psm 6 -l {languages}'
            return self._run_ocr_with_config(image, config)
        except Exception as e:
            self._log_step("フォールバックOCRエラー", {"error": str(e)})
            return []
    
    # ヘルパーメソッド群
    def _is_cultivation_number(self, text: str) -> bool:
        """栽培関連の数字かどうか判定"""
        # 区画番号、棚番号などのパターン
        import re
        patterns = [
            r'^\d{1,3}$',           # 1-3桁の数字
            r'^[A-Z]\d{1,2}$',      # A1, B12 など
            r'^\d+-\d+$',           # 1-1, 2-3 など
            r'^第?\d+区画?$',        # 第1区画 など
        ]
        
        for pattern in patterns:
            if re.match(pattern, text):
                return True
        return False
    
    def _contains_japanese(self, text: str) -> bool:
        """日本語文字が含まれているか判定"""
        import re
        # ひらがな、カタカナ、漢字のパターン
        japanese_pattern = r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]'
        return bool(re.search(japanese_pattern, text))
    
    def _is_cultivation_vocabulary(self, text: str) -> bool:
        """栽培関連語彙かどうか判定"""
        cultivation_keywords = [
            'トマト', 'きゅうり', 'なす', 'ピーマン', 'レタス', 'キャベツ',
            '区画', '棚', 'ハウス', '温室', '育苗', '播種', '定植', '収穫',
            '品種', '苗', '種子', '肥料', '農薬', 'pH', '温度', '湿度',
            'A棟', 'B棟', 'C棟', '1号', '2号', '3号', '東', '西', '南', '北'
        ]
        
        return any(keyword in text for keyword in cultivation_keywords)
    
    def _is_alphanumeric_code(self, text: str) -> bool:
        """英数字コードかどうか判定"""
        import re
        # 品種コード、管理番号などのパターン
        patterns = [
            r'^[A-Z]{1,3}\d{1,4}$',     # A123, BC45 など
            r'^[A-Z]+\-\d+$',           # ABC-123 など
            r'^\d{4,}$',                # 4桁以上の数字
            r'^[A-Z]{2,}$',             # 2文字以上の英字
        ]
        
        for pattern in patterns:
            if re.match(pattern, text.upper()):
                return True
        return False
    
    def _is_overlapping_bbox(self, bbox1: Dict, bbox2: Dict) -> bool:
        """バウンディングボックスの重複判定"""
        x1, y1, w1, h1 = bbox1['x'], bbox1['y'], bbox1['width'], bbox1['height']
        x2, y2, w2, h2 = bbox2['x'], bbox2['y'], bbox2['width'], bbox2['height']
        
        # 重複領域の計算
        overlap_x = max(0, min(x1 + w1, x2 + w2) - max(x1, x2))
        overlap_y = max(0, min(y1 + h1, y2 + h2) - max(y1, y2))
        overlap_area = overlap_x * overlap_y
        
        # 小さい方のボックスの面積に対する重複割合
        area1 = w1 * h1
        area2 = w2 * h2
        min_area = min(area1, area2)
        
        return overlap_area > min_area * 0.5  # 50%以上重複
    
    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """テキスト類似度計算"""
        try:
            from difflib import SequenceMatcher
            return SequenceMatcher(None, text1, text2).ratio()
        except:
            # フォールバック：単純な一致チェック
            return 1.0 if text1 == text2 else 0.0
    
    def _normalize_cultivation_text(self, text: str) -> str:
        """栽培区画テキストの正規化"""
        import re
        
        # 基本的なクリーニング
        normalized = text.strip()
        
        # 全角数字を半角に変換
        normalized = normalized.translate(str.maketrans('０１２３４５６７８９', '0123456789'))
        
        # 全角英字を半角に変換
        normalized = normalized.translate(str.maketrans(
            'ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ',
            'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
        ))
        
        # 不要な文字の除去
        normalized = re.sub(r'[^\w\-\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]', '', normalized)
        
        return normalized
    
    def _estimate_cultivation_type(self, text: str) -> str:
        """栽培区画タイプの推定"""
        import re
        
        # 区画番号パターン
        if re.match(r'^\d{1,3}$|^[A-Z]\d{1,2}$|^\d+-\d+$', text):
            return 'section_number'
        
        # 品種名パターン
        if self._is_cultivation_vocabulary(text) and len(text) > 2:
            return 'variety_name'
        
        # 測定値パターン
        if re.match(r'^\d+\.?\d*[℃%㎝m]?$', text):
            return 'measurement'
        
        # 管理コードパターン
        if re.match(r'^[A-Z]{1,3}\d{1,4}$|^[A-Z]+\-\d+$', text):
            return 'management_code'
        
        return 'unknown'
    
    def _calculate_context_bonus(self, result: Dict) -> int:
        """コンテキストボーナス計算"""
        bonus = 0
        
        # タイプ別ボーナス
        cultivation_type = result.get('cultivation_type', 'unknown')
        if cultivation_type == 'section_number':
            bonus += 10
        elif cultivation_type == 'variety_name':
            bonus += 8
        elif cultivation_type == 'management_code':
            bonus += 12
        
        # 特化タイプボーナス
        specialized_type = result.get('specialized_type')
        if specialized_type:
            bonus += 5
        
        # 位置ボーナス（上部や左側にある文字は重要度が高い）
        bbox = result.get('bbox', {})
        if bbox.get('y', 1000) < 100:  # 上部
            bonus += 3
        if bbox.get('x', 1000) < 100:  # 左側
            bonus += 2
        
        return min(bonus, 25)  # 最大25ポイント
    
    def detect_shapes(self, image: np.ndarray) -> List[Dict]:
        """図形検出（矩形・円など）"""
        shapes = []
        
        try:
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
                    'bbox': {'x': int(x), 'y': int(y), 'width': int(w), 'height': int(h)},
                    'area': float(area),
                    'vertices': len(approx)
                }
                
                # 形状判定
                if len(approx) == 4:
                    # 矩形の可能性
                    aspect_ratio = w / h if h > 0 else 1
                    if 0.8 <= aspect_ratio <= 1.2:
                        shape_info['type'] = 'square'
                    else:
                        shape_info['type'] = 'rectangle'
                elif len(approx) > 8:
                    shape_info['type'] = 'circle'
                
                shapes.append(shape_info)
            
            return shapes
        except Exception as e:
            print(f"図形検出エラー: {e}")
            return []
    
    def extract_shelf_information(self, ocr_texts: List[Dict], shapes: List[Dict]) -> List[Dict]:
        """棚情報の抽出・マッチング"""
        shelves = []
        
        try:
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
        except Exception as e:
            print(f"棚情報抽出エラー: {e}")
            return []
    
    def find_nearby_shape(self, text_bbox: Dict, shapes: List[Dict], max_distance: int = 100) -> Optional[Dict]:
        """テキストに最も近い図形を見つける"""
        try:
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
        except Exception as e:
            print(f"近傍図形検索エラー: {e}")
            return None
    
    def calculate_grid_position(self, bbox: Dict) -> Dict:
        """バウンディングボックスからグリッド位置を計算"""
        try:
            center_x = bbox['x'] + bbox['width'] // 2
            center_y = bbox['y'] + bbox['height'] // 2
            
            # グリッド座標に変換（仮の実装）
            # 実際の実装では、図面のスケールや基準点を考慮する必要がある
            grid_x = center_x // 100  # 100ピクセルごとに1グリッド
            grid_y = center_y // 100
            
            return {
                'grid_x': int(grid_x),
                'grid_y': int(grid_y),
                'pixel_x': int(center_x),
                'pixel_y': int(center_y)
            }
        except Exception as e:
            print(f"グリッド座標計算エラー: {e}")
            return {
                'grid_x': 0,
                'grid_y': 0,
                'pixel_x': 0,
                'pixel_y': 0
            }
    
    def _get_cached_result(self, file_path: str) -> Optional[Dict]:
        """キャッシュから結果を取得"""
        try:
            file_hash = self._calculate_file_hash(file_path)
            cache_key = f"ocr_result_{file_hash}"
            return cache.get(cache_key)
        except Exception:
            return None
    
    def _cache_result(self, file_path: str, result: Dict):
        """結果をキャッシュに保存"""
        try:
            file_hash = self._calculate_file_hash(file_path)
            cache_key = f"ocr_result_{file_hash}"
            cache.set(cache_key, result, self.cache_duration)
        except Exception:
            pass
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """ファイルハッシュを計算"""
        try:
            with open(file_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception:
            return ""
    
    def _log_step(self, step_name: str, data: Dict = None):
        """処理ステップをログに記録"""
        timestamp = timezone.now().isoformat()
        log_entry = {
            'timestamp': timestamp,
            'step': step_name,
            'data': data or {}
        }
        self.processing_log.append(log_entry)
        
        if self.debug_mode:
            self.logger.info(f"{step_name}: {data}")
    
    def _generate_debug_info(self) -> Dict:
        """デバッグ情報を生成"""
        return {
            'processing_log': self.processing_log,
            'performance_stats': self.performance_stats,
            'ocr_settings': self.ocr_settings,
            'preprocessing_config': self.preprocessing_config,
            'total_processing_time': time.time() - self.performance_stats['start_time'] if self.performance_stats['start_time'] else 0
        }
    
    def _basic_preprocess(self, image: np.ndarray) -> np.ndarray:
        """基本的な前処理（フォールバック用）"""
        try:
            # グレースケール変換
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image
            
            # 基本的なノイズ除去
            denoised = cv2.fastNlMeansDenoising(gray, h=10)
            
            # CLAHE適用
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(denoised)
            
            # 二値化
            _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            return binary
        except Exception as e:
            self._log_step("基本前処理エラー", {"error": str(e)})
            # 最後の手段：グレースケール変換のみ
            if len(image.shape) == 3:
                return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            return image
    
    def _perspective_correction(self, image: np.ndarray) -> np.ndarray:
        """歪み補正（台形補正）- 栽培区画図面の歪みを修正"""
        try:
            # エッジ検出
            edges = cv2.Canny(image, 50, 150, apertureSize=3)
            
            # 直線検出
            lines = cv2.HoughLines(edges, 1, np.pi/180, threshold=100)
            
            if lines is not None and len(lines) >= 4:
                # 主要な線を抽出して台形の頂点を推定
                angles = []
                for rho, theta in lines[:10]:  # 上位10本の線を分析
                    angles.append(theta)
                
                # 垂直・水平線の角度を特定
                vertical_angles = [a for a in angles if abs(a - np.pi/2) < 0.1]
                horizontal_angles = [a for a in angles if abs(a) < 0.1 or abs(a - np.pi) < 0.1]
                
                if len(vertical_angles) >= 2 and len(horizontal_angles) >= 2:
                    # 四角形の頂点を検出
                    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    
                    for contour in contours:
                        # 輪郭を多角形近似
                        epsilon = 0.02 * cv2.arcLength(contour, True)
                        approx = cv2.approxPolyDP(contour, epsilon, True)
                        
                        # 4つの頂点を持つ四角形を検出
                        if len(approx) == 4:
                            # 面積チェック（画像の10%以上）
                            area = cv2.contourArea(approx)
                            image_area = image.shape[0] * image.shape[1]
                            
                            if area > image_area * 0.1:
                                # 透視変換行列を計算
                                pts1 = np.float32([approx[i][0] for i in range(4)])
                                
                                # 出力画像のサイズを決定
                                width = max(
                                    np.linalg.norm(pts1[0] - pts1[1]),
                                    np.linalg.norm(pts1[2] - pts1[3])
                                )
                                height = max(
                                    np.linalg.norm(pts1[0] - pts1[3]),
                                    np.linalg.norm(pts1[1] - pts1[2])
                                )
                                
                                pts2 = np.float32([[0, 0], [width, 0], [width, height], [0, height]])
                                
                                # 透視変換実行
                                matrix = cv2.getPerspectiveTransform(pts1, pts2)
                                corrected = cv2.warpPerspective(image, matrix, (int(width), int(height)))
                                
                                self._log_step("透視変換実行", {
                                    "detected_area": area,
                                    "output_size": (int(width), int(height))
                                })
                                
                                return corrected
            
            self._log_step("透視変換スキップ", {"reason": "適切な四角形が検出されませんでした"})
            return image
            
        except Exception as e:
            self._log_step("透視変換エラー", {"error": str(e)})
            return image
    
    def _enhance_resolution(self, image: np.ndarray) -> np.ndarray:
        """解像度向上（超解像処理）- 文字認識精度向上のため"""
        try:
            # 現在の画像サイズ
            height, width = image.shape[:2]
            
            # 解像度が低い場合のみ処理
            if width < 1200 or height < 1200:
                # バイキュービック補間で2倍に拡大
                scale_factor = 2.0
                new_width = int(width * scale_factor)
                new_height = int(height * scale_factor)
                
                enhanced = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_CUBIC)
                
                # シャープニングフィルタ適用
                kernel = np.array([[-1,-1,-1],
                                 [-1, 9,-1],
                                 [-1,-1,-1]])
                sharpened = cv2.filter2D(enhanced, -1, kernel)
                
                # ガウシアンブラーで微調整
                blurred = cv2.GaussianBlur(sharpened, (1, 1), 0)
                
                self._log_step("解像度向上実行", {
                    "original_size": (width, height),
                    "enhanced_size": (new_width, new_height),
                    "scale_factor": scale_factor
                })
                
                return blurred
            
            self._log_step("解像度向上スキップ", {"reason": "十分な解像度です"})
            return image
            
        except Exception as e:
            self._log_step("解像度向上エラー", {"error": str(e)})
            return image
    
    def _adaptive_denoise(self, image: np.ndarray) -> np.ndarray:
        """アダプティブノイズ除去 - 画像の特性に応じたノイズ除去"""
        try:
            # ノイズレベルを推定
            laplacian_var = cv2.Laplacian(image, cv2.CV_64F).var()
            
            if laplacian_var < 100:  # 低コントラスト画像
                # 強いノイズ除去
                denoised = cv2.fastNlMeansDenoising(image, h=15, templateWindowSize=7, searchWindowSize=21)
                self._log_step("強いノイズ除去実行", {"laplacian_var": laplacian_var})
            elif laplacian_var > 1000:  # 高コントラスト画像
                # 軽いノイズ除去
                denoised = cv2.fastNlMeansDenoising(image, h=5, templateWindowSize=7, searchWindowSize=21)
                self._log_step("軽いノイズ除去実行", {"laplacian_var": laplacian_var})
            else:  # 標準的な画像
                # 標準ノイズ除去
                denoised = cv2.fastNlMeansDenoising(image, h=10, templateWindowSize=7, searchWindowSize=21)
                self._log_step("標準ノイズ除去実行", {"laplacian_var": laplacian_var})
            
            return denoised
            
        except Exception as e:
            self._log_step("アダプティブノイズ除去エラー", {"error": str(e)})
            return cv2.fastNlMeansDenoising(image, h=10)
    
    def _enhance_text_regions(self, image: np.ndarray) -> np.ndarray:
        """テキスト領域強化 - 文字部分を強調"""
        try:
            # テキスト領域検出用のモルフォロジー演算
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            
            # トップハット変換（小さな明るい領域を強調）
            tophat = cv2.morphologyEx(image, cv2.MORPH_TOPHAT, kernel)
            
            # ブラックハット変換（小さな暗い領域を強調）
            blackhat = cv2.morphologyEx(image, cv2.MORPH_BLACKHAT, kernel)
            
            # 元画像にトップハット結果を加算し、ブラックハット結果を減算
            enhanced = cv2.add(image, tophat)
            enhanced = cv2.subtract(enhanced, blackhat)
            
            # テキスト特有の幅を持つ矩形カーネルでクロージング
            text_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 1))
            enhanced = cv2.morphologyEx(enhanced, cv2.MORPH_CLOSE, text_kernel)
            
            self._log_step("テキスト領域強化実行")
            return enhanced
            
        except Exception as e:
            self._log_step("テキスト領域強化エラー", {"error": str(e)})
            return image
    
    def _multi_stage_binarization(self, image: np.ndarray) -> np.ndarray:
        """多段階二値化 - 複数の閾値で最適な二値化を選択"""
        try:
            candidates = []
            
            # 1. OTSU閾値
            _, otsu = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            candidates.append(("OTSU", otsu))
            
            # 2. アダプティブ閾値（平均）
            adaptive_mean = cv2.adaptiveThreshold(image, 255, cv2.ADAPTIVE_THRESH_MEAN_C, 
                                                cv2.THRESH_BINARY, 11, 2)
            candidates.append(("ADAPTIVE_MEAN", adaptive_mean))
            
            # 3. アダプティブ閾値（ガウシアン）
            adaptive_gaussian = cv2.adaptiveThreshold(image, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                                    cv2.THRESH_BINARY, 11, 2)
            candidates.append(("ADAPTIVE_GAUSSIAN", adaptive_gaussian))
            
            # 4. 手動閾値（複数の値で試行）
            for threshold in [120, 140, 160, 180]:
                _, manual = cv2.threshold(image, threshold, 255, cv2.THRESH_BINARY)
                candidates.append((f"MANUAL_{threshold}", manual))
            
            # 最適な二値化結果を選択（文字領域の密度で評価）
            best_method = None
            best_score = 0
            best_image = otsu  # デフォルトはOTSU
            
            for method_name, binary_img in candidates:
                # 文字らしい連結成分の数を評価
                num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(binary_img, connectivity=8)
                
                # 適切なサイズの連結成分をカウント
                valid_components = 0
                for i in range(1, num_labels):  # 0はバックグラウンド
                    area = stats[i, cv2.CC_STAT_AREA]
                    width = stats[i, cv2.CC_STAT_WIDTH]
                    height = stats[i, cv2.CC_STAT_HEIGHT]
                    
                    # 文字らしいサイズの連結成分
                    if 10 <= area <= 2000 and 5 <= width <= 100 and 5 <= height <= 100:
                        aspect_ratio = width / height if height > 0 else 0
                        if 0.1 <= aspect_ratio <= 5:  # 文字らしいアスペクト比
                            valid_components += 1
                
                score = valid_components
                if score > best_score:
                    best_score = score
                    best_method = method_name
                    best_image = binary_img
            
            self._log_step("多段階二値化完了", {
                "best_method": best_method,
                "best_score": best_score,
                "candidates_tested": len(candidates)
            })
            
            return best_image
            
        except Exception as e:
            self._log_step("多段階二値化エラー", {"error": str(e)})
            # フォールバック：OTSU二値化
            _, binary = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            return binary
    
    def _character_shape_correction(self, image: np.ndarray) -> np.ndarray:
        """文字形状補正 - 文字の形状を整える"""
        try:
            # 微細なノイズ除去
            kernel = np.ones((2, 2), np.uint8)
            
            # オープニング（ノイズ除去）
            opening = cv2.morphologyEx(image, cv2.MORPH_OPEN, kernel)
            
            # クロージング（文字の隙間を埋める）
            closing = cv2.morphologyEx(opening, cv2.MORPH_CLOSE, kernel)
            
            # 文字の太さを調整（膨張・収縮）
            # 細い文字の場合は膨張、太い文字の場合は収縮
            contours, _ = cv2.findContours(closing, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if contours:
                # 平均的な文字の太さを推定
                total_area = sum(cv2.contourArea(c) for c in contours)
                avg_area = total_area / len(contours) if contours else 0
                
                if avg_area < 50:  # 細い文字
                    # 軽く膨張
                    dilate_kernel = np.ones((2, 2), np.uint8)
                    corrected = cv2.dilate(closing, dilate_kernel, iterations=1)
                    self._log_step("文字膨張実行", {"avg_area": avg_area})
                elif avg_area > 500:  # 太い文字
                    # 軽く収縮
                    erode_kernel = np.ones((2, 2), np.uint8)
                    corrected = cv2.erode(closing, erode_kernel, iterations=1)
                    self._log_step("文字収縮実行", {"avg_area": avg_area})
                else:
                    corrected = closing
                    self._log_step("文字形状維持", {"avg_area": avg_area})
            else:
                corrected = closing
                self._log_step("文字形状補正スキップ", {"reason": "輪郭が検出されませんでした"})
            
            return corrected
            
        except Exception as e:
            self._log_step("文字形状補正エラー", {"error": str(e)})
            return image


class LayoutGenerator:
    """OCR結果からレイアウトを生成するクラス"""
    
    def __init__(self):
        self.ocr_settings = getattr(settings, 'OCR_SETTINGS', {})
    
    def generate_layout_from_ocr(self, ocr_result: Dict, layout_name: str, created_by=None) -> Dict:
        """OCR結果からCultivationLayoutとCultivationSectionを生成"""
        try:
            from .models import CultivationLayout, CultivationSection
            
            # レイアウト作成
            layout = CultivationLayout.objects.create(
                name=layout_name,
                created_by=created_by
            )
            
            created_sections = []
            section_count = 0
            
            # 各ページの棚情報を処理
            for page in ocr_result.get('pages', []):
                for shelf in page.get('shelf_info', []):
                    if shelf.get('position'):
                        try:
                            # 区画作成
                            section = CultivationSection.objects.create(
                                layout=layout,
                                name=shelf['shelf_number'],
                                row=max(1, shelf['position']['grid_y'] + 1),  # 1-based indexing
                                column=max(1, shelf['position']['grid_x'] + 1),
                                description=f"OCRで自動生成 (信頼度: {shelf['confidence']}%)",
                                created_by=created_by
                            )
                            created_sections.append(section)
                            section_count += 1
                        except Exception as e:
                            print(f"区画作成エラー: {e}")
                            continue
            
            return {
                'success': True,
                'layout': layout,
                'sections': created_sections,
                'sections_count': section_count
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }


class OCRValidator:
    """OCR結果の検証・品質チェッククラス"""
    
    def __init__(self):
        self.ocr_settings = getattr(settings, 'OCR_SETTINGS', {})
    
    def validate_ocr_result(self, ocr_result: Dict) -> Dict:
        """OCR結果の品質を検証"""
        validation_result = {
            'is_valid': True,
            'warnings': [],
            'suggestions': [],
            'quality_score': 0
        }
        
        try:
            total_shelves = 0
            low_confidence_count = 0
            confidence_threshold = self.ocr_settings.get('DEFAULT_CONFIDENCE_THRESHOLD', 60)
            
            for page in ocr_result.get('pages', []):
                for shelf in page.get('shelf_info', []):
                    total_shelves += 1
                    if shelf.get('confidence', 0) < confidence_threshold:
                        low_confidence_count += 1
            
            # 品質スコア計算
            if total_shelves > 0:
                quality_score = max(0, 100 - (low_confidence_count / total_shelves * 100))
                validation_result['quality_score'] = round(quality_score, 1)
            
            # 警告とサジェスション
            if total_shelves == 0:
                validation_result['warnings'].append("棚情報が検出されませんでした")
                validation_result['suggestions'].append("画像の解像度を上げるか、コントラストを調整してください")
            
            if low_confidence_count > total_shelves * 0.3:
                validation_result['warnings'].append(f"低信頼度の認識が多数あります ({low_confidence_count}/{total_shelves})")
                validation_result['suggestions'].append("OCR信頼度閾値を下げるか、画像品質を改善してください")
            
            if quality_score < 70:
                validation_result['is_valid'] = False
                validation_result['suggestions'].append("画像の前処理を調整するか、別の画像を使用してください")
            
        except Exception as e:
            validation_result['is_valid'] = False
            validation_result['warnings'].append(f"検証エラー: {str(e)}")
        
        return validation_result