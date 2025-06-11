"""
本番環境セットアップ用管理コマンド
python manage_prod.py setup_production
"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.db import transaction
from django.core.cache import cache
from shift_management.models import Staff, ShiftType
from shift_management.utils.cache import DatabaseOptimization, warm_cache
import os

class Command(BaseCommand):
    help = '本番環境の初期セットアップを実行'

    def add_arguments(self, parser):
        parser.add_argument(
            '--create-superuser',
            action='store_true',
            help='スーパーユーザーを作成',
        )
        parser.add_argument(
            '--create-sample-data',
            action='store_true',
            help='サンプルデータを作成',
        )
        parser.add_argument(
            '--optimize-db',
            action='store_true',
            help='データベースを最適化',
        )
        parser.add_argument(
            '--warm-cache',
            action='store_true',
            help='キャッシュをウォームアップ',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('わかくさシフト本番環境セットアップを開始...')
        )

        try:
            with transaction.atomic():
                if options['create_superuser']:
                    self.create_superuser()

                if options['create_sample_data']:
                    self.create_sample_data()

                if options['optimize_db']:
                    self.optimize_database()

                if options['warm_cache']:
                    self.warm_cache()

            self.stdout.write(
                self.style.SUCCESS('✅ セットアップが完了しました！')
            )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ セットアップエラー: {e}')
            )
            raise CommandError(f'セットアップに失敗しました: {e}')

    def create_superuser(self):
        """スーパーユーザーを作成"""
        self.stdout.write('👤 スーパーユーザーを作成中...')
        
        username = input('ユーザー名: ')
        email = input('メールアドレス: ')
        
        if User.objects.filter(username=username).exists():
            self.stdout.write(
                self.style.WARNING(f'ユーザー "{username}" は既に存在します')
            )
            return

        user = User.objects.create_superuser(
            username=username,
            email=email,
            password=None  # パスワードは対話式で設定
        )
        
        # 対応するStaffレコードを作成
        staff, created = Staff.objects.get_or_create(
            user=user,
            defaults={
                'name': username,
                'email': email,
                'position': '管理者',
                'is_active': True
            }
        )
        
        self.stdout.write(
            self.style.SUCCESS(f'✅ スーパーユーザー "{username}" を作成しました')
        )

    def create_sample_data(self):
        """サンプルデータを作成"""
        self.stdout.write('📊 サンプルデータを作成中...')

        # シフト種別のサンプルデータ
        shift_types_data = [
            {'name': '早番', 'color': '#28a745', 'start_time': '08:00', 'end_time': '17:00'},
            {'name': '遅番', 'color': '#dc3545', 'start_time': '13:00', 'end_time': '22:00'},
            {'name': '夜勤', 'color': '#6f42c1', 'start_time': '22:00', 'end_time': '08:00'},
            {'name': '日勤', 'color': '#007bff', 'start_time': '09:00', 'end_time': '18:00'},
        ]

        for shift_data in shift_types_data:
            shift_type, created = ShiftType.objects.get_or_create(
                name=shift_data['name'],
                defaults=shift_data
            )
            if created:
                self.stdout.write(f'  ✅ シフト種別 "{shift_type.name}" を作成')

        # サンプルスタッフデータ
        sample_staff_data = [
            {'name': '田中太郎', 'position': '看護師', 'email': 'tanaka@example.com'},
            {'name': '佐藤花子', 'position': '看護師', 'email': 'sato@example.com'},
            {'name': '鈴木一郎', 'position': '介護士', 'email': 'suzuki@example.com'},
        ]

        for staff_data in sample_staff_data:
            staff, created = Staff.objects.get_or_create(
                name=staff_data['name'],
                defaults=staff_data
            )
            if created:
                self.stdout.write(f'  ✅ スタッフ "{staff.name}" を作成')

        self.stdout.write(
            self.style.SUCCESS('✅ サンプルデータの作成が完了しました')
        )

    def optimize_database(self):
        """データベースを最適化"""
        self.stdout.write('🔧 データベースを最適化中...')

        try:
            # インデックスを作成
            DatabaseOptimization.create_indexes()
            self.stdout.write('  ✅ インデックスを作成しました')

            # SQLiteの場合は追加の最適化
            DatabaseOptimization.optimize_shift_queries()
            self.stdout.write('  ✅ クエリ最適化を実行しました')

            self.stdout.write(
                self.style.SUCCESS('✅ データベース最適化が完了しました')
            )

        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f'⚠️ データベース最適化エラー: {e}')
            )

    def warm_cache(self):
        """キャッシュをウォームアップ"""
        self.stdout.write('🔥 キャッシュをウォームアップ中...')

        try:
            warm_cache()
            self.stdout.write(
                self.style.SUCCESS('✅ キャッシュウォームアップが完了しました')
            )

        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f'⚠️ キャッシュウォームアップエラー: {e}')
            ) 