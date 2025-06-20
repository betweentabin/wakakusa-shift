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
        
        username = 'admin'
        email = input('管理者メールアドレス: ')
        password = input('管理者パスワード: ')
        
        if User.objects.filter(username=username).exists():
            self.stdout.write(
                self.style.WARNING(f'ユーザー "{username}" は既に存在します')
            )
            return

        user = User.objects.create_superuser(
            username=username,
            email=email,
            password=password
        )
        
        # 対応するStaffレコードを作成
        staff, created = Staff.objects.get_or_create(
            user=user,
            defaults={
                'name': '管理者',
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
        
        # シフト種別の作成
        shift_types = [
            {'name': '早番', 'color': '#28a745', 'start_time': '09:00', 'end_time': '17:00'},
            {'name': '遅番', 'color': '#dc3545', 'start_time': '13:00', 'end_time': '21:00'},
            {'name': '夜勤', 'color': '#6f42c1', 'start_time': '22:00', 'end_time': '06:00'},
            {'name': '休日出勤', 'color': '#fd7e14', 'start_time': '10:00', 'end_time': '18:00'},
        ]
        
        for shift_type_data in shift_types:
            shift_type, created = ShiftType.objects.get_or_create(
                name=shift_type_data['name'],
                defaults={
                    'color': shift_type_data['color'],
                    'start_time': shift_type_data['start_time'],
                    'end_time': shift_type_data['end_time'],
                }
            )
            if created:
                self.stdout.write(f'  ✅ シフト種別「{shift_type.name}」を作成')
        
        # 各権限レベルのサンプルスタッフを作成
        sample_staff = [
            {
                'name': '管理者 太郎',
                'role_type': 'manager',
                'email': 'manager@example.com',
                'position': '管理者',
                'username': 'manager',
                'password': 'password123'
            },
            {
                'name': '職員 花子',
                'role_type': 'staff',
                'email': 'staff@example.com',
                'position': '正職員',
                'username': 'staff',
                'password': 'password123'
            },
            {
                'name': 'アルバイト 次郎',
                'role_type': 'part_time',
                'email': 'parttime1@example.com',
                'position': 'アルバイト',
                'username': 'parttime1',
                'password': 'password123'
            },
            {
                'name': 'アルバイト 三郎',
                'role_type': 'part_time',
                'email': 'parttime2@example.com',
                'position': 'アルバイト',
                'username': 'parttime2',
                'password': 'password123'
            },
            {
                'name': '利用者 四郎',
                'role_type': 'user',
                'email': 'user@example.com',
                'position': '利用者',
                'username': 'user',
                'password': 'password123'
            },
        ]
        
        for staff_data in sample_staff:
            # ユーザーアカウントを作成
            user, user_created = User.objects.get_or_create(
                username=staff_data['username'],
                defaults={
                    'email': staff_data['email'],
                    'first_name': staff_data['name'].split()[0],
                    'last_name': staff_data['name'].split()[1] if len(staff_data['name'].split()) > 1 else '',
                }
            )
            if user_created:
                user.set_password(staff_data['password'])
                user.save()
            
            # スタッフレコードを作成
            staff, staff_created = Staff.objects.get_or_create(
                user=user,
                defaults={
                    'name': staff_data['name'],
                    'email': staff_data['email'],
                    'position': staff_data['position'],
                    'role_type': staff_data['role_type'],
                    'is_active': True,
                    'approval_status': 'approved',  # サンプルデータは承認済みで作成
                }
            )
            
            if staff_created:
                self.stdout.write(f'  ✅ スタッフ「{staff.name}」({staff.get_role_type_display()})を作成')
        
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