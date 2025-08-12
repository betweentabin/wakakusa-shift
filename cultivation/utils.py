import cv2
import pytesseract
import pandas as pd
import pdfplumber
from PIL import Image
import re
import os
from .models import CultivationSection, Crop

def process_import_file(layout, file_path):
    """
    インポートファイルを処理してレイアウトを自動作成
    """
    file_extension = os.path.splitext(file_path)[1].lower()
    
    try:
        if file_extension in ['.jpg', '.jpeg', '.png', '.bmp']:
            return process_image_file(layout, file_path)
        elif file_extension == '.pdf':
            return process_pdf_file(layout, file_path)
        elif file_extension in ['.xlsx', '.xls']:
            return process_excel_file(layout, file_path)
        else:
            return False, f"サポートされていないファイル形式: {file_extension}"
    except Exception as e:
        return False, f"ファイル処理中にエラーが発生しました: {str(e)}"

def process_image_file(layout, file_path):
    """
    画像ファイルからOCRでテキストを抽出し、レイアウトを作成
    """
    try:
        # 画像を読み込み
        image = cv2.imread(file_path)
        if image is None:
            return False, "画像ファイルの読み込みに失敗しました"
        
        # グレースケールに変換
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # OCRでテキストを抽出
        text = pytesseract.image_to_string(gray, lang='jpn')
        
        # テキストから区画情報を抽出
        sections_created = extract_sections_from_text(layout, text)
        
        return True, f"{sections_created}個の区画を作成しました"
    except Exception as e:
        return False, f"画像処理エラー: {str(e)}"

def process_pdf_file(layout, file_path):
    """
    PDFファイルからテキストを抽出し、レイアウトを作成
    """
    try:
        sections_created = 0
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    sections_created += extract_sections_from_text(layout, text)
        
        return True, f"{sections_created}個の区画を作成しました"
    except Exception as e:
        return False, f"PDF処理エラー: {str(e)}"

def process_excel_file(layout, file_path):
    """
    Excelファイルからデータを読み込み、レイアウトを作成
    """
    try:
        # Excelファイルを読み込み
        df = pd.read_excel(file_path)
        
        sections_created = 0
        
        # データフレームから区画情報を抽出
        for index, row in df.iterrows():
            # 列名に基づいて情報を抽出
            section_name = None
            row_num = None
            column_num = None
            crop_name = None
            
            # 柔軟な列名マッチング
            for col in df.columns:
                col_lower = str(col).lower()
                if '区画' in col_lower or 'section' in col_lower or '名前' in col_lower:
                    section_name = str(row[col]) if pd.notna(row[col]) else None
                elif '行' in col_lower or 'row' in col_lower:
                    row_num = int(row[col]) if pd.notna(row[col]) else None
                elif '列' in col_lower or 'column' in col_lower or 'col' in col_lower:
                    column_num = int(row[col]) if pd.notna(row[col]) else None
                elif '作物' in col_lower or 'crop' in col_lower or '植物' in col_lower:
                    crop_name = str(row[col]) if pd.notna(row[col]) else None
            
            # 必要な情報が揃っている場合のみ区画を作成
            if section_name and row_num and column_num:
                section, created = CultivationSection.objects.get_or_create(
                    layout=layout,
                    row=row_num,
                    column=column_num,
                    defaults={'name': section_name}
                )
                if created:
                    sections_created += 1
                
                # 作物情報があれば栽培計画も作成
                if crop_name:
                    crop, _ = Crop.objects.get_or_create(
                        name=crop_name,
                        defaults={'color': '#ffc107'}  # デフォルト色
                    )
                    from .models import CultivationPlan
                    CultivationPlan.objects.get_or_create(
                        section=section,
                        defaults={'crop': crop}
                    )
        
        return True, f"{sections_created}個の区画を作成しました"
    except Exception as e:
        return False, f"Excel処理エラー: {str(e)}"

def extract_sections_from_text(layout, text):
    """
    テキストから区画情報を抽出
    """
    sections_created = 0
    
    # 区画パターンを検索（例：A列1段目、B-2、C3など）
    patterns = [
        r'([A-Z])列(\d+)段目',  # A列1段目
        r'([A-Z])-(\d+)',       # A-1
        r'([A-Z])(\d+)',        # A1
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            column_letter = match[0]
            row_num = int(match[1])
            column_num = ord(column_letter) - ord('A') + 1
            
            section_name = f"{column_letter}列{row_num}段目"
            
            section, created = CultivationSection.objects.get_or_create(
                layout=layout,
                row=row_num,
                column=column_num,
                defaults={'name': section_name}
            )
            if created:
                sections_created += 1
    
    return sections_created 