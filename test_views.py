#!/usr/bin/env python
import os
import sys
import django

# Django設定
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings.development')
django.setup()

from django.test import Client
from django.contrib.auth.models import User

def test_new_features():
    """新機能のテスト"""
    c = Client()
    
    try:
        # 管理者でログイン
        user = User.objects.get(username='admin')
        c.force_login(user)
        
        # 各ページをテスト
        pages = [
            ('/leave-requests/', 'Leave requests'),
            ('/shift-proposals/', 'Shift proposals'),
            ('/notifications/', 'Notifications'),
        ]
        
        for url, name in pages:
            try:
                response = c.get(url)
                print(f'{name} ({url}): Status {response.status_code}')
                
                if response.status_code == 500:
                    print(f'  Server error occurred')
                elif response.status_code != 200:
                    print(f'  Unexpected status code')
                    
            except Exception as e:
                print(f'{name} ({url}): Error - {e}')
                
    except Exception as e:
        print(f'Test setup error: {e}')

if __name__ == '__main__':
    test_new_features()