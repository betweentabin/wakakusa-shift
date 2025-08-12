#!/usr/bin/env python
"""
サンプル組織とデータを作成するマネジメントコマンド
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from shift_management.models import Organization, Staff, ShiftType
from django.utils import timezone

class Command(BaseCommand):
    help = 'サンプル組織とデータを作成します'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='既存のサンプルデータを削除してから作成',
        )

    def handle(self, *args, **options):
        if options['reset']:
            self.stdout.write('既存のサンプルデータを削除中...')
            # サンプル組織を削除（カスケードで関連データも削除される）
            Organization.objects.filter(
                code__in=['wakakusa', 'kaigo-abc', 'medical-xyz']
            ).delete()
            self.stdout.write(self.style.WARNING('既存のサンプルデータを削除しました'))

        # 組織1: 医療法人わかくさ
        self.stdout.write('組織1: 医療法人わかくさを作成中...')
        org1, created = Organization.objects.get_or_create(
            code='wakakusa',
            defaults={
                'name': '医療法人わかくさ',
                'description': '地域密着型の医療・介護サービスを提供する法人です。',
                'timezone': 'Asia/Tokyo',
                'currency': 'JPY',
                'contact_email': 'info@wakakusa-medical.jp',
                'contact_phone': '03-1234-5678',
                'address': '東京都新宿区西新宿1-1-1',
                'is_active': True,
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'✓ {org1.name} を作成しました'))
        else:
            self.stdout.write(f'✓ {org1.name} は既に存在します')

        # 組織2: 株式会社ABC介護
        self.stdout.write('組織2: 株式会社ABC介護を作成中...')
        org2, created = Organization.objects.get_or_create(
            code='kaigo-abc',
            defaults={
                'name': '株式会社ABC介護',
                'description': '在宅介護サービスを中心とした介護事業者です。',
                'timezone': 'Asia/Tokyo',
                'currency': 'JPY',
                'contact_email': 'contact@abc-kaigo.co.jp',
                'contact_phone': '06-9876-5432',
                'address': '大阪府大阪市中央区本町2-2-2',
                'is_active': True,
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'✓ {org2.name} を作成しました'))
        else:
            self.stdout.write(f'✓ {org2.name} は既に存在します')

        # 組織3: 医療法人XYZ病院
        self.stdout.write('組織3: 医療法人XYZ病院を作成中...')
        org3, created = Organization.objects.get_or_create(
            code='medical-xyz',
            defaults={
                'name': '医療法人XYZ病院',
                'description': '総合病院として幅広い医療サービスを提供しています。',
                'timezone': 'Asia/Tokyo',
                'currency': 'JPY',
                'contact_email': 'admin@xyz-hospital.or.jp',
                'contact_phone': '052-1111-2222',
                'address': '愛知県名古屋市中区栄3-3-3',
                'is_active': True,
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'✓ {org3.name} を作成しました'))
        else:
            self.stdout.write(f'✓ {org3.name} は既に存在します')

        # 各組織にサンプルスタッフを作成
        self.create_sample_staff(org1)
        self.create_sample_staff(org2)
        self.create_sample_staff(org3)

        # シフト種別を作成
        self.create_shift_types()

        self.stdout.write(
            self.style.SUCCESS(
                '\n🎉 サンプルデータの作成が完了しました！\n'
                '\n以下の組織が作成されました：\n'
                f'1. {org1.name} (コード: {org1.code})\n'
                f'2. {org2.name} (コード: {org2.code})\n'
                f'3. {org3.name} (コード: {org3.code})\n'
                '\n管理画面またはWebサイトで確認してください。'
            )
        )

    def create_sample_staff(self, organization):
        """組織にサンプルスタッフを作成"""
        self.stdout.write(f'{organization.name} にサンプルスタッフを作成中...')
        
        # 管理者
        manager, created = Staff.objects.get_or_create(
            organization=organization,
            name=f'{organization.code}_管理者',
            defaults={
                'phone': '090-1111-1111',
                'email': f'manager@{organization.code}.example.com',
                'position': '管理者',
                'role_type': 'manager',
                'is_active': True,
                'approval_status': 'approved',
                'approved_at': timezone.now(),
            }
        )
        if created:
            self.stdout.write(f'  ✓ 管理者: {manager.name}')

        # 職員
        staff_member, created = Staff.objects.get_or_create(
            organization=organization,
            name=f'{organization.code}_職員',
            defaults={
                'phone': '090-2222-2222',
                'email': f'staff@{organization.code}.example.com',
                'position': '正職員',
                'role_type': 'staff',
                'is_active': True,
                'approval_status': 'approved',
                'approved_at': timezone.now(),
            }
        )
        if created:
            self.stdout.write(f'  ✓ 職員: {staff_member.name}')

        # アルバイト
        part_timer, created = Staff.objects.get_or_create(
            organization=organization,
            name=f'{organization.code}_アルバイト',
            defaults={
                'phone': '090-3333-3333',
                'email': f'parttime@{organization.code}.example.com',
                'position': 'アルバイト',
                'role_type': 'part_time',
                'is_active': True,
                'approval_status': 'approved',
                'approved_at': timezone.now(),
            }
        )
        if created:
            self.stdout.write(f'  ✓ アルバイト: {part_timer.name}')

        # 利用者
        user_staff, created = Staff.objects.get_or_create(
            organization=organization,
            name=f'{organization.code}_利用者',
            defaults={
                'phone': '090-4444-4444',
                'email': f'user@{organization.code}.example.com',
                'position': '利用者',
                'role_type': 'user',
                'is_active': True,
                'approval_status': 'approved',
                'approved_at': timezone.now(),
            }
        )
        if created:
            self.stdout.write(f'  ✓ 利用者: {user_staff.name}')

    def create_shift_types(self):
        """基本的なシフト種別を作成"""
        self.stdout.write('基本的なシフト種別を作成中...')
        
        shift_types = [
            {
                'name': '早番',
                'color': '#28a745',
                'start_time': '07:00',
                'end_time': '15:00',
                'description': '早朝から午後までの勤務'
            },
            {
                'name': '日勤',
                'color': '#007bff',
                'start_time': '09:00',
                'end_time': '17:00',
                'description': '通常の日勤時間'
            },
            {
                'name': '遅番',
                'color': '#fd7e14',
                'start_time': '13:00',
                'end_time': '21:00',
                'description': '午後から夜までの勤務'
            },
            {
                'name': '夜勤',
                'color': '#6f42c1',
                'start_time': '21:00',
                'end_time': '07:00',
                'description': '夜間勤務'
            },
            {
                'name': '半日',
                'color': '#20c997',
                'start_time': '09:00',
                'end_time': '13:00',
                'description': '半日勤務'
            },
        ]
        
        for shift_data in shift_types:
            shift_type, created = ShiftType.objects.get_or_create(
                name=shift_data['name'],
                defaults=shift_data
            )
            if created:
                self.stdout.write(f'  ✓ シフト種別: {shift_type.name}')
            else:
                self.stdout.write(f'  ✓ シフト種別: {shift_type.name} (既存)') 