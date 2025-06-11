"""
キャッシュ戦略とパフォーマンス最適化
"""

from django.core.cache import cache
from django.db.models import Prefetch
from functools import wraps
import hashlib
import json
from datetime import datetime, timedelta

def cache_key_generator(*args, **kwargs):
    """
    キャッシュキーを生成
    """
    key_data = {
        'args': args,
        'kwargs': kwargs,
        'timestamp': datetime.now().strftime('%Y%m%d')  # 日付でキーを変更
    }
    key_string = json.dumps(key_data, sort_keys=True, default=str)
    return hashlib.md5(key_string.encode()).hexdigest()

def cache_shift_data(timeout=300):
    """
    シフトデータをキャッシュするデコレータ
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # キャッシュキーを生成
            cache_key = f"shift_data_{cache_key_generator(*args, **kwargs)}"
            
            # キャッシュから取得を試行
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # キャッシュにない場合は実行
            result = func(*args, **kwargs)
            
            # 結果をキャッシュに保存
            cache.set(cache_key, result, timeout)
            
            return result
        return wrapper
    return decorator

def invalidate_shift_cache(staff_id=None, date_range=None):
    """
    シフトキャッシュを無効化
    """
    # 特定のパターンのキャッシュを削除
    if staff_id:
        cache.delete_many([
            f"staff_shifts_{staff_id}",
            f"monthly_shifts_{staff_id}",
        ])
    
    # 全体のシフトキャッシュを削除
    cache.delete_many([
        'all_shifts_current_month',
        'shift_calendar_data',
        'staff_list_active',
    ])

class OptimizedShiftQueries:
    """
    最適化されたシフトクエリ
    """
    
    @staticmethod
    @cache_shift_data(timeout=600)  # 10分間キャッシュ
    def get_monthly_shifts(year, month):
        """
        月次シフトデータを最適化して取得
        """
        from shift_management.models import Shift, Staff, ShiftType
        
        # 日付範囲を計算
        start_date = datetime(year, month, 1).date()
        if month == 12:
            end_date = datetime(year + 1, 1, 1).date() - timedelta(days=1)
        else:
            end_date = datetime(year, month + 1, 1).date() - timedelta(days=1)
        
        # 最適化されたクエリ（select_related, prefetch_relatedを使用）
        shifts = Shift.objects.filter(
            date__range=[start_date, end_date]
        ).select_related(
            'staff', 'shift_type'
        ).order_by('date', 'start_time')
        
        return list(shifts)
    
    @staticmethod
    @cache_shift_data(timeout=300)  # 5分間キャッシュ
    def get_active_staff():
        """
        アクティブなスタッフ一覧を取得
        """
        from shift_management.models import Staff
        
        return list(Staff.objects.filter(is_active=True).order_by('name'))
    
    @staticmethod
    @cache_shift_data(timeout=600)  # 10分間キャッシュ
    def get_shift_types():
        """
        シフト種別一覧を取得
        """
        from shift_management.models import ShiftType
        
        return list(ShiftType.objects.all().order_by('name'))
    
    @staticmethod
    def get_staff_shifts_optimized(staff_id, start_date, end_date):
        """
        特定スタッフのシフトを最適化して取得
        """
        from shift_management.models import Shift
        
        cache_key = f"staff_shifts_{staff_id}_{start_date}_{end_date}"
        cached_result = cache.get(cache_key)
        
        if cached_result is not None:
            return cached_result
        
        shifts = Shift.objects.filter(
            staff_id=staff_id,
            date__range=[start_date, end_date]
        ).select_related('shift_type').order_by('date', 'start_time')
        
        result = list(shifts)
        cache.set(cache_key, result, 300)  # 5分間キャッシュ
        
        return result

class DatabaseOptimization:
    """
    データベース最適化ユーティリティ
    """
    
    @staticmethod
    def optimize_shift_queries():
        """
        シフトクエリの最適化設定
        """
        from django.db import connection
        
        # SQLiteの場合の最適化
        if 'sqlite' in connection.settings_dict['ENGINE']:
            with connection.cursor() as cursor:
                # WALモードを有効化（読み書き性能向上）
                cursor.execute("PRAGMA journal_mode=WAL;")
                # 同期モードを最適化
                cursor.execute("PRAGMA synchronous=NORMAL;")
                # キャッシュサイズを増加
                cursor.execute("PRAGMA cache_size=10000;")
                # 一時ファイルをメモリに保存
                cursor.execute("PRAGMA temp_store=MEMORY;")
    
    @staticmethod
    def create_indexes():
        """
        パフォーマンス向上のためのインデックス作成
        """
        from django.db import connection
        
        with connection.cursor() as cursor:
            # よく使用される検索条件にインデックスを作成
            try:
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_shift_date_staff 
                    ON shift_management_shift(date, staff_id);
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_shift_date_range 
                    ON shift_management_shift(date);
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_staff_active 
                    ON shift_management_staff(is_active);
                """)
                
            except Exception as e:
                print(f"インデックス作成エラー: {e}")

def warm_cache():
    """
    キャッシュのウォームアップ
    アプリケーション起動時に実行
    """
    try:
        # 現在月のデータをプリロード
        now = datetime.now()
        OptimizedShiftQueries.get_monthly_shifts(now.year, now.month)
        OptimizedShiftQueries.get_active_staff()
        OptimizedShiftQueries.get_shift_types()
        
        print("✅ キャッシュウォームアップ完了")
        
    except Exception as e:
        print(f"⚠️ キャッシュウォームアップエラー: {e}")

def cache_stats():
    """
    キャッシュ統計情報を取得
    """
    try:
        # Redisの場合
        if hasattr(cache, '_cache') and hasattr(cache._cache, 'get_client'):
            client = cache._cache.get_client()
            info = client.info()
            return {
                'type': 'redis',
                'used_memory': info.get('used_memory_human', 'N/A'),
                'connected_clients': info.get('connected_clients', 'N/A'),
                'keyspace_hits': info.get('keyspace_hits', 'N/A'),
                'keyspace_misses': info.get('keyspace_misses', 'N/A'),
            }
        else:
            return {
                'type': 'file_based_or_locmem',
                'status': 'active'
            }
    except Exception as e:
        return {
            'type': 'unknown',
            'error': str(e)
        } 