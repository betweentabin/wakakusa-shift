"""
Cultivation アプリケーションの定数定義
"""

class Colors:
    """カラーコード定数"""
    DEFAULT_GRAY = "#808080"
    DEFAULT_YELLOW = "#ffc107"
    DEFAULT_GREEN = "#28a745"
    DEFAULT_RED = "#dc3545"
    DEFAULT_BLUE = "#007bff"

class Limits:
    """制限値定数"""
    NAME_MAX_LENGTH = 100
    DESCRIPTION_MAX_LENGTH = 500
    MAX_CULTIVATION_DAYS = 365
    MIN_CULTIVATION_DAYS = 1
    GRID_SUGGESTION_COUNT = 5
    DEFAULT_SECTION_COUNT = 10

class ImageSizes:
    """画像サイズ定数"""
    THUMBNAIL = 50
    PREVIEW = 100
    MEDIUM = 300
    LARGE = 500

class DateFormats:
    """日付フォーマット定数"""
    DISPLAY_FORMAT = "%Y年%m月%d日"
    INPUT_FORMAT = "%Y-%m-%d"
    
class Messages:
    """メッセージ定数"""
    CREATE_SUCCESS = "{model}を作成しました。"
    UPDATE_SUCCESS = "{model}を更新しました。"
    DELETE_SUCCESS = "{model}を削除しました。"
    IMPORT_SUCCESS = "{count}件のデータをインポートしました。"
    EXPORT_SUCCESS = "データをエクスポートしました。"
    PERMISSION_DENIED = "この操作を実行する権限がありません。"
    
class CropStatus:
    """作物ステータス定数"""
    PLANNING = "planning"
    SEEDED = "seeded"
    GROWING = "growing"
    HARVEST_READY = "harvest_ready"
    HARVESTED = "harvested"
    
    CHOICES = [
        (PLANNING, "計画中"),
        (SEEDED, "播種済み"),
        (GROWING, "成長中"),
        (HARVEST_READY, "収穫可能"),
        (HARVESTED, "収穫済み"),
    ]