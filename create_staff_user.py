#!/usr/bin/env python
import os
import django

# Django設定を読み込み
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.contrib.auth.models import User

def create_staff_user():
    """一般スタッフユーザーを作成"""
    username = 'staff'
    email = 'staff@example.com'
    password = 'staff123'
    
    # 既存ユーザーをチェック
    if User.objects.filter(username=username).exists():
        print(f'ユーザー "{username}" は既に存在します。')
        return
    
    # 一般ユーザーを作成
    user = User.objects.create_user(
        username=username,
        email=email,
        password=password,
        is_staff=False,  # 管理画面アクセス不可
        is_superuser=False  # スーパーユーザー権限なし
    )
    
    print(f'一般スタッフユーザーを作成しました:')
    print(f'  ユーザー名: {username}')
    print(f'  パスワード: {password}')
    print(f'  メール: {email}')
    print(f'  権限: 一般ユーザー（シフト確認のみ）')

if __name__ == '__main__':
    create_staff_user() 