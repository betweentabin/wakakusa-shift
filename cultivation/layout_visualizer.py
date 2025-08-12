"""
栽培レイアウト図表示用ビジュアライザー
OCR結果を元に栽培レイアウト図をSVG形式で生成
"""
import math
import json
from typing import Dict, List, Tuple, Optional
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe


class LayoutVisualizer:
    """栽培レイアウト図のSVG生成クラス"""
    
    def __init__(self, layout_data: Dict, ocr_results: Dict, canvas_size: Tuple[int, int] = (800, 600)):
        self.layout_data = layout_data
        self.ocr_results = ocr_results
        self.canvas_width, self.canvas_height = canvas_size
        
        # カラーパレット
        self.colors = {
            'section_fill': '#e3f2fd',
            'section_stroke': '#1976d2',
            'section_hover': '#bbdefb',
            'text_color': '#333333',
            'background': '#f9f9f9',
            'grid_line': '#e0e0e0',
            'highlight': '#ff9800',
            'success': '#4caf50',
            'warning': '#ffc107',
            'error': '#f44336'
        }
        
        # SVG要素のスタイル
        self.styles = {
            'section_rect': {
                'fill': self.colors['section_fill'],
                'stroke': self.colors['section_stroke'],
                'stroke-width': '2',
                'rx': '4',
                'ry': '4',
                'cursor': 'pointer'
            },
            'section_text': {
                'font-family': 'Arial, sans-serif',
                'font-size': '14px',
                'font-weight': 'bold',
                'fill': self.colors['text_color'],
                'text-anchor': 'middle',
                'dominant-baseline': 'middle'
            },
            'grid_line': {
                'stroke': self.colors['grid_line'],
                'stroke-width': '1',
                'stroke-dasharray': '2,2'
            }
        }
        
        # レイアウト解析
        self.analyze_layout()
    
    def analyze_layout(self):
        """レイアウトデータを解析し、描画に必要な情報を計算"""
        if not self.ocr_results.get('success') or not self.ocr_results.get('pages'):
            self.grid_info = {'rows': 0, 'cols': 0, 'sections': []}
            return
        
        # 棚情報の抽出
        shelf_info = []
        for page in self.ocr_results['pages']:
            if 'shelf_info' in page:
                shelf_info.extend(page['shelf_info'])
        
        if not shelf_info:
            self.grid_info = {'rows': 0, 'cols': 0, 'sections': []}
            return
        
        # グリッド範囲の計算
        grid_positions = [(item['position']['grid_x'], item['position']['grid_y']) 
                         for item in shelf_info if 'position' in item]
        
        if not grid_positions:
            self.grid_info = {'rows': 0, 'cols': 0, 'sections': []}
            return
        
        min_x = min(pos[0] for pos in grid_positions)
        max_x = max(pos[0] for pos in grid_positions)
        min_y = min(pos[1] for pos in grid_positions)
        max_y = max(pos[1] for pos in grid_positions)
        
        self.grid_info = {
            'rows': max_y - min_y + 1,
            'cols': max_x - min_x + 1,
            'min_x': min_x,
            'max_x': max_x,
            'min_y': min_y,
            'max_y': max_y,
            'sections': shelf_info
        }
        
        # セクションサイズの計算
        self.calculate_section_dimensions()
    
    def calculate_section_dimensions(self):
        """セクションの描画サイズを計算"""
        if self.grid_info['rows'] == 0 or self.grid_info['cols'] == 0:
            self.section_width = 0
            self.section_height = 0
            return
        
        # マージンとパディングの設定
        margin = 40
        padding = 10
        
        # 利用可能なスペース
        available_width = self.canvas_width - (2 * margin)
        available_height = self.canvas_height - (2 * margin)
        
        # セクションサイズの計算
        section_width = (available_width - (self.grid_info['cols'] - 1) * padding) / self.grid_info['cols']
        section_height = (available_height - (self.grid_info['rows'] - 1) * padding) / self.grid_info['rows']
        
        # 正方形に近い形状にする
        min_size = min(section_width, section_height)
        self.section_width = max(min_size, 60)  # 最小サイズ
        self.section_height = max(min_size, 60)
        
        # 実際のレイアウトサイズ
        total_width = self.grid_info['cols'] * self.section_width + (self.grid_info['cols'] - 1) * padding
        total_height = self.grid_info['rows'] * self.section_height + (self.grid_info['rows'] - 1) * padding
        
        # 中央揃えのためのオフセット
        self.offset_x = (self.canvas_width - total_width) / 2
        self.offset_y = (self.canvas_height - total_height) / 2
    
    def grid_to_svg_position(self, grid_x: int, grid_y: int) -> Tuple[float, float]:
        """グリッド座標をSVG座標に変換"""
        if self.grid_info['rows'] == 0 or self.grid_info['cols'] == 0:
            return (0, 0)
        
        # グリッド座標を正規化（0ベース）
        normalized_x = grid_x - self.grid_info['min_x']
        normalized_y = grid_y - self.grid_info['min_y']
        
        # SVG座標に変換
        x = self.offset_x + normalized_x * (self.section_width + 10)
        y = self.offset_y + normalized_y * (self.section_height + 10)
        
        return (x, y)
    
    def get_confidence_color(self, confidence: float) -> str:
        """信頼度に応じた色を返す"""
        if confidence >= 80:
            return self.colors['success']
        elif confidence >= 60:
            return self.colors['warning']
        else:
            return self.colors['error']
    
    def create_section_element(self, section: Dict) -> str:
        """個別区画のSVG要素を生成"""
        if 'position' not in section:
            return ""
        
        grid_x = section['position']['grid_x']
        grid_y = section['position']['grid_y']
        x, y = self.grid_to_svg_position(grid_x, grid_y)
        
        shelf_number = section.get('shelf_number', 'N/A')
        confidence = section.get('confidence', 0)
        
        # 信頼度に応じた色
        stroke_color = self.get_confidence_color(confidence)
        
        # 矩形要素
        rect_attrs = {
            'x': f"{x:.1f}",
            'y': f"{y:.1f}",
            'width': f"{self.section_width:.1f}",
            'height': f"{self.section_height:.1f}",
            'fill': self.colors['section_fill'],
            'stroke': stroke_color,
            'stroke-width': '2',
            'rx': '4',
            'ry': '4',
            'cursor': 'pointer',
            'data-shelf': shelf_number,
            'data-confidence': str(confidence),
            'data-grid-x': str(grid_x),
            'data-grid-y': str(grid_y),
            'class': 'section-rect'
        }
        
        rect_element = f'<rect {" ".join(f"{k}=\"{v}\"" for k, v in rect_attrs.items())} />'
        
        # テキスト要素
        text_x = x + self.section_width / 2
        text_y = y + self.section_height / 2
        
        text_attrs = {
            'x': f"{text_x:.1f}",
            'y': f"{text_y:.1f}",
            'font-family': 'Arial, sans-serif',
            'font-size': '12px',
            'font-weight': 'bold',
            'fill': self.colors['text_color'],
            'text-anchor': 'middle',
            'dominant-baseline': 'middle',
            'class': 'section-text'
        }
        
        text_element = f'<text {" ".join(f"{k}=\"{v}\"" for k, v in text_attrs.items())}>{shelf_number}</text>'
        
        # 信頼度インジケーター
        confidence_y = y + self.section_height - 5
        confidence_width = (self.section_width - 10) * (confidence / 100)
        
        confidence_bg = f'<rect x="{x + 5}" y="{confidence_y}" width="{self.section_width - 10}" height="3" fill="#e0e0e0" rx="1" />'
        confidence_bar = f'<rect x="{x + 5}" y="{confidence_y}" width="{confidence_width}" height="3" fill="{stroke_color}" rx="1" />'
        
        return f'{rect_element}\n{text_element}\n{confidence_bg}\n{confidence_bar}'
    
    def create_grid_lines(self) -> str:
        """グリッド線を生成"""
        if self.grid_info['rows'] == 0 or self.grid_info['cols'] == 0:
            return ""
        
        lines = []
        
        # 垂直線
        for i in range(self.grid_info['cols'] + 1):
            x = self.offset_x + i * (self.section_width + 10) - 5
            y1 = self.offset_y - 5
            y2 = self.offset_y + self.grid_info['rows'] * (self.section_height + 10) - 5
            lines.append(f'<line x1="{x}" y1="{y1}" x2="{x}" y2="{y2}" stroke="#e0e0e0" stroke-width="1" stroke-dasharray="2,2" />')
        
        # 水平線
        for i in range(self.grid_info['rows'] + 1):
            y = self.offset_y + i * (self.section_height + 10) - 5
            x1 = self.offset_x - 5
            x2 = self.offset_x + self.grid_info['cols'] * (self.section_width + 10) - 5
            lines.append(f'<line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" stroke="#e0e0e0" stroke-width="1" stroke-dasharray="2,2" />')
        
        return '\n'.join(lines)
    
    def create_legend(self) -> str:
        """凡例を生成"""
        legend_items = [
            {'color': self.colors['success'], 'label': '信頼度: 80%以上'},
            {'color': self.colors['warning'], 'label': '信頼度: 60-79%'},
            {'color': self.colors['error'], 'label': '信頼度: 60%未満'}
        ]
        
        legend_x = 20
        legend_y = self.canvas_height - 80
        
        legend_elements = []
        legend_elements.append(f'<text x="{legend_x}" y="{legend_y - 20}" font-family="Arial" font-size="14" font-weight="bold" fill="#333">凡例</text>')
        
        for i, item in enumerate(legend_items):
            y_pos = legend_y + i * 20
            legend_elements.append(f'<rect x="{legend_x}" y="{y_pos - 6}" width="12" height="12" fill="{item["color"]}" rx="2" />')
            legend_elements.append(f'<text x="{legend_x + 20}" y="{y_pos + 3}" font-family="Arial" font-size="12" fill="#333">{item["label"]}</text>')
        
        return '\n'.join(legend_elements)
    
    def create_title_and_info(self) -> str:
        """タイトルと情報を生成"""
        title_elements = []
        
        # タイトル
        title_elements.append(f'<text x="{self.canvas_width / 2}" y="25" font-family="Arial" font-size="18" font-weight="bold" text-anchor="middle" fill="#333">栽培レイアウト図</text>')
        
        # 統計情報
        total_sections = len(self.grid_info['sections'])
        avg_confidence = sum(section.get('confidence', 0) for section in self.grid_info['sections']) / max(total_sections, 1)
        
        info_text = f"検出区画数: {total_sections} | 平均信頼度: {avg_confidence:.1f}% | グリッドサイズ: {self.grid_info['rows']}×{self.grid_info['cols']}"
        title_elements.append(f'<text x="{self.canvas_width / 2}" y="45" font-family="Arial" font-size="12" text-anchor="middle" fill="#666">{info_text}</text>')
        
        return '\n'.join(title_elements)
    
    def generate_svg(self) -> str:
        """SVG形式の栽培レイアウト図を生成"""
        if not self.grid_info['sections']:
            return self.generate_empty_svg()
        
        # SVG要素の生成
        svg_elements = []
        
        # グリッド線
        svg_elements.append(self.create_grid_lines())
        
        # セクション要素
        for section in self.grid_info['sections']:
            section_svg = self.create_section_element(section)
            if section_svg:
                svg_elements.append(section_svg)
        
        # 凡例
        svg_elements.append(self.create_legend())
        
        # タイトルと情報
        svg_elements.append(self.create_title_and_info())
        
        # SVG全体の構成
        svg_content = f'''
        <svg width="{self.canvas_width}" height="{self.canvas_height}" viewBox="0 0 {self.canvas_width} {self.canvas_height}" xmlns="http://www.w3.org/2000/svg">
            <defs>
                <style>
                    .section-rect:hover {{
                        fill: {self.colors['section_hover']};
                        stroke-width: 3;
                    }}
                    .section-rect.highlighted {{
                        fill: {self.colors['highlight']};
                        stroke: {self.colors['highlight']};
                        stroke-width: 3;
                    }}
                </style>
            </defs>
            <rect width="100%" height="100%" fill="{self.colors['background']}" />
            {chr(10).join(svg_elements)}
        </svg>
        '''
        
        return svg_content.strip()
    
    def generate_empty_svg(self) -> str:
        """空のレイアウト図を生成"""
        return f'''
        <svg width="{self.canvas_width}" height="{self.canvas_height}" viewBox="0 0 {self.canvas_width} {self.canvas_height}" xmlns="http://www.w3.org/2000/svg">
            <rect width="100%" height="100%" fill="{self.colors['background']}" />
            <text x="{self.canvas_width / 2}" y="{self.canvas_height / 2}" 
                  font-family="Arial" font-size="18" text-anchor="middle" 
                  fill="#666">レイアウト情報がありません</text>
            <text x="{self.canvas_width / 2}" y="{self.canvas_height / 2 + 30}" 
                  font-family="Arial" font-size="14" text-anchor="middle" 
                  fill="#999">OCR処理を実行してください</text>
        </svg>
        '''
    
    def get_layout_statistics(self) -> Dict:
        """レイアウトの統計情報を取得"""
        sections = self.grid_info['sections']
        
        if not sections:
            return {
                'total_sections': 0,
                'avg_confidence': 0,
                'confidence_distribution': {'high': 0, 'medium': 0, 'low': 0},
                'grid_size': {'rows': 0, 'cols': 0}
            }
        
        confidences = [section.get('confidence', 0) for section in sections]
        avg_confidence = sum(confidences) / len(confidences)
        
        # 信頼度分布
        high_confidence = sum(1 for c in confidences if c >= 80)
        medium_confidence = sum(1 for c in confidences if 60 <= c < 80)
        low_confidence = sum(1 for c in confidences if c < 60)
        
        return {
            'total_sections': len(sections),
            'avg_confidence': avg_confidence,
            'confidence_distribution': {
                'high': high_confidence,
                'medium': medium_confidence,
                'low': low_confidence
            },
            'grid_size': {
                'rows': self.grid_info['rows'],
                'cols': self.grid_info['cols']
            }
        }
    
    def export_layout_data(self) -> Dict:
        """レイアウトデータをエクスポート"""
        return {
            'layout_info': self.grid_info,
            'statistics': self.get_layout_statistics(),
            'sections': [
                {
                    'shelf_number': section.get('shelf_number'),
                    'confidence': section.get('confidence'),
                    'grid_position': section.get('position', {}),
                    'bbox': section.get('text_bbox', {}),
                    'shape': section.get('shape', {})
                }
                for section in self.grid_info['sections']
            ]
        }