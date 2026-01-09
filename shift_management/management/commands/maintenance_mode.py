"""
メンテナンスモード制御用管理コマンド
python manage_prod.py maintenance_mode --enable
python manage_prod.py maintenance_mode --disable
"""

from django.core.management.base import BaseCommand
from django.core.cache import cache
from datetime import datetime

class Command(BaseCommand):
    help = 'メンテナンスモードの有効/無効を切り替え'

    def add_arguments(self, parser):
        parser.add_argument(
            '--enable',
            action='store_true',
            help='メンテナンスモードを有効にする',
        )
        parser.add_argument(
            '--disable',
            action='store_true',
            help='メンテナンスモードを無効にする',
        )
        parser.add_argument(
            '--status',
            action='store_true',
            help='現在のメンテナンスモード状態を確認',
        )
        parser.add_argument(
            '--message',
            type=str,
            help='メンテナンス時に表示するメッセージ',
            default='システムメンテナンス中です'
        )

    def handle(self, *args, **options):
        if options['enable']:
            self.enable_maintenance_mode(options['message'])
        elif options['disable']:
            self.disable_maintenance_mode()
        elif options['status']:
            self.show_status()
        else:
            self.stdout.write(
                self.style.ERROR('--enable, --disable, --status のいずれかを指定してください')
            )

    def enable_maintenance_mode(self, message):
        """メンテナンスモードを有効にする"""
        cache.set('maintenance_mode', True, timeout=None)  # 無期限
        cache.set('maintenance_message', message, timeout=None)
        cache.set('maintenance_start_time', datetime.now().isoformat(), timeout=None)
        
        self.stdout.write(
            self.style.SUCCESS('🔧 メンテナンスモードを有効にしました')
        )
        self.stdout.write(f'メッセージ: {message}')
        self.stdout.write(f'開始時刻: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')

    def disable_maintenance_mode(self):
        """メンテナンスモードを無効にする"""
        start_time_str = cache.get('maintenance_start_time')
        
        cache.delete('maintenance_mode')
        cache.delete('maintenance_message')
        cache.delete('maintenance_start_time')
        
        self.stdout.write(
            self.style.SUCCESS('✅ メンテナンスモードを無効にしました')
        )
        
        if start_time_str:
            try:
                start_time = datetime.fromisoformat(start_time_str)
                duration = datetime.now() - start_time
                self.stdout.write(f'メンテナンス時間: {duration}')
            except:
                pass

    def show_status(self):
        """現在のメンテナンスモード状態を表示"""
        is_maintenance = cache.get('maintenance_mode', False)
        message = cache.get('maintenance_message', '')
        start_time_str = cache.get('maintenance_start_time', '')
        
        if is_maintenance:
            self.stdout.write(
                self.style.WARNING('🔧 メンテナンスモード: 有効')
            )
            if message:
                self.stdout.write(f'メッセージ: {message}')
            if start_time_str:
                try:
                    start_time = datetime.fromisoformat(start_time_str)
                    duration = datetime.now() - start_time
                    self.stdout.write(f'開始時刻: {start_time.strftime("%Y-%m-%d %H:%M:%S")}')
                    self.stdout.write(f'経過時間: {duration}')
                except:
                    pass
        else:
            self.stdout.write(
                self.style.SUCCESS('✅ メンテナンスモード: 無効')
            ) 