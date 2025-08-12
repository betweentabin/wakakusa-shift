#!/usr/bin/env python
"""
組織ごとの専用ログインアカウントを作成するマネジメントコマンド
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from shift_management.models import Organization, Staff
from django.utils import timezone

class Command(BaseCommand):
    help = '組織ごとの専用ログインアカウントを作成します'

    def add_arguments(self, parser):
        parser.add_argument(
            '--create-super-admin',
            action='store_true',
            help='組織管理専用のスーパーアドミンアカウントを作成'
        )

    def handle(self, *args, **options):
        if options['create_super_admin']:
            self.create_super_admin()
            return

        self.stdout.write(self.style.SUCCESS('=== 組織専用アカウント作成開始 ==='))
        
        organizations = Organization.objects.filter(is_active=True)
        if not organizations.exists():
            self.stdout.write(
                self.style.ERROR('有効な組織が見つかりません。先にサンプル組織を作成してください。')
            )
            return

        for organization in organizations:
            self.stdout.write(f'\n📋 組織: {organization.name} ({organization.code})')
            self.create_organization_accounts(organization)

        self.stdout.write(self.style.SUCCESS('\n=== アカウント作成完了 ==='))
        self.display_login_info()

    def create_super_admin(self):
        """組織管理専用のスーパーアドミンアカウントを作成"""
        self.stdout.write(self.style.SUCCESS('=== 組織管理専用スーパーアドミン作成 ==='))
        
        username = 'org_super_admin'
        password = 'OrgAdmin2024!'
        email = 'org-admin@wakakusa-shift.local'
        
        # 既存ユーザーをチェック
        if User.objects.filter(username=username).exists():
            self.stdout.write(
                self.style.WARNING(f'ユーザー「{username}」は既に存在します。')
            )
            return
        
        # スーパーユーザー作成
        user = User.objects.create_superuser(
            username=username,
            email=email,
            password=password
        )
        user.first_name = '組織管理'
        user.last_name = 'スーパーアドミン'
        user.save()
        
        self.stdout.write(self.style.SUCCESS(f'✓ 組織管理専用スーパーアドミンを作成しました'))
        self.stdout.write(f'  ユーザー名: {username}')
        self.stdout.write(f'  パスワード: {password}')
        self.stdout.write(f'  メール: {email}')
        self.stdout.write(self.style.WARNING('⚠️  このアカウントは組織管理専用です。パスワードを安全に管理してください。'))

    def create_organization_accounts(self, organization):
        """組織の専用アカウントを作成"""
        
        # 組織コードベースのプレフィックス
        if organization.code == 'wakakusa':
            prefix = 'wakakusa'
            password = 'wakakusa2024'
        elif organization.code == 'kaigo-abc':
            prefix = 'kaigo'
            password = 'kaigo2024'
        elif organization.code == 'medical-xyz':
            prefix = 'medical'
            password = 'medical2024'
        else:
            prefix = organization.code.replace('-', '_')
            password = f'{prefix}2024'

        # 管理者アカウント
        admin_user, created = self.create_user_and_staff(
            username=f'{prefix}_admin',
            password=password,
            email=f'admin@{organization.code}.example.com',
            organization=organization,
            role_type='manager',
            position='システム管理者',
            is_staff=True  # Django管理画面アクセス可能
        )
        if created:
            self.stdout.write(f'  ✓ 管理者: {admin_user.username}')

        # マネージャーアカウント
        manager_user, created = self.create_user_and_staff(
            username=f'{prefix}_manager',
            password=password,
            email=f'manager@{organization.code}.example.com',
            organization=organization,
            role_type='manager',
            position='現場責任者'
        )
        if created:
            self.stdout.write(f'  ✓ マネージャー: {manager_user.username}')

        # スタッフアカウント
        staff_user, created = self.create_user_and_staff(
            username=f'{prefix}_staff',
            password=password,
            email=f'staff@{organization.code}.example.com',
            organization=organization,
            role_type='staff',
            position='現場スタッフ'
        )
        if created:
            self.stdout.write(f'  ✓ スタッフ: {staff_user.username}')

    def create_user_and_staff(self, username, password, email, organization, role_type, position, is_staff=False):
        """ユーザーとスタッフを作成"""
        
        # ユーザー作成
        user, user_created = User.objects.get_or_create(
            username=username,
            defaults={
                'email': email,
                'is_staff': is_staff,
                'is_superuser': False,
                'first_name': position,
                'last_name': organization.name
            }
        )
        
        if user_created:
            user.set_password(password)
            user.save()

        # 既存のスタッフをチェック（メールアドレス重複回避）
        existing_staff = Staff.objects.filter(
            organization=organization,
            email=email
        ).first()
        
        if existing_staff and not existing_staff.user:
            # 既存スタッフにユーザーを関連付け
            existing_staff.user = user
            existing_staff.role_type = role_type
            existing_staff.position = position
            existing_staff.approval_status = 'approved'
            existing_staff.approved_at = timezone.now()
            existing_staff.save()
            staff = existing_staff
            staff_created = True
        elif not existing_staff:
            # 新規スタッフ作成（ユニークなメールアドレス）
            unique_email = f'{username}@{organization.code.replace("-", "")}.local'
            staff, staff_created = Staff.objects.get_or_create(
                user=user,
                organization=organization,
                defaults={
                    'name': f'{organization.name}_{position}',
                    'phone': '090-0000-0000',
                    'email': unique_email,
                    'position': position,
                    'role_type': role_type,
                    'is_active': True,
                    'approval_status': 'approved',
                    'approved_at': timezone.now(),
                }
            )
        else:
            # 既にユーザーが関連付けられている場合
            staff = existing_staff
            staff_created = False

        return user, user_created and staff_created 

    def display_login_info(self):
        """ログイン情報を表示"""
        self.stdout.write(
            self.style.SUCCESS(
                '\n🎉 組織専用アカウントの作成が完了しました！\n'
                '\n【ログイン情報】\n'
                '■ 医療法人わかくさ\n'
                '  管理者: wakakusa_admin / wakakusa2024\n'
                '  マネージャー: wakakusa_manager / wakakusa2024\n'
                '  スタッフ: wakakusa_staff / wakakusa2024\n'
                '\n'
                '■ 株式会社ABC介護\n'
                '  管理者: kaigo_admin / kaigo2024\n'
                '  マネージャー: kaigo_manager / kaigo2024\n'
                '  スタッフ: kaigo_staff / kaigo2024\n'
                '\n'
                '■ 医療法人XYZ病院\n'
                '  管理者: medical_admin / medical2024\n'
                '  マネージャー: medical_manager / medical2024\n'
                '  スタッフ: medical_staff / medical2024\n'
                '\n'
                '🔐 組織管理専用アカウント\n'
                '  スーパーアドミン: org_super_admin / OrgAdmin2024!\n'
                '\n'
                '各アカウントでログインして組織別のシフト管理をテストしてください。'
            )
        ) 