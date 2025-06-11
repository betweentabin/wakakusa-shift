#!/usr/bin/env python3
"""
システム監視スクリプト
定期実行でシステムの状態を監視し、問題があればアラートを送信
"""

import os
import sys
import requests
import psutil
import subprocess
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from pathlib import Path

# プロジェクトのパスを追加
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

# Django設定を読み込み
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings.production')

import django
django.setup()

from django.conf import settings
from django.core.cache import cache

class SystemMonitor:
    def __init__(self):
        self.alerts = []
        self.metrics = {}
        
    def check_disk_usage(self, threshold=90):
        """ディスク使用率をチェック"""
        try:
            disk_usage = psutil.disk_usage('/')
            usage_percent = (disk_usage.used / disk_usage.total) * 100
            
            self.metrics['disk_usage'] = usage_percent
            
            if usage_percent > threshold:
                self.alerts.append({
                    'type': 'disk',
                    'level': 'critical' if usage_percent > 95 else 'warning',
                    'message': f'ディスク使用率が {usage_percent:.1f}% です',
                    'value': usage_percent
                })
                
        except Exception as e:
            self.alerts.append({
                'type': 'disk',
                'level': 'error',
                'message': f'ディスク使用率の取得に失敗: {e}'
            })
    
    def check_memory_usage(self, threshold=85):
        """メモリ使用率をチェック"""
        try:
            memory = psutil.virtual_memory()
            usage_percent = memory.percent
            
            self.metrics['memory_usage'] = usage_percent
            
            if usage_percent > threshold:
                self.alerts.append({
                    'type': 'memory',
                    'level': 'critical' if usage_percent > 95 else 'warning',
                    'message': f'メモリ使用率が {usage_percent:.1f}% です',
                    'value': usage_percent
                })
                
        except Exception as e:
            self.alerts.append({
                'type': 'memory',
                'level': 'error',
                'message': f'メモリ使用率の取得に失敗: {e}'
            })
    
    def check_cpu_usage(self, threshold=80):
        """CPU使用率をチェック"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            
            self.metrics['cpu_usage'] = cpu_percent
            
            if cpu_percent > threshold:
                self.alerts.append({
                    'type': 'cpu',
                    'level': 'critical' if cpu_percent > 95 else 'warning',
                    'message': f'CPU使用率が {cpu_percent:.1f}% です',
                    'value': cpu_percent
                })
                
        except Exception as e:
            self.alerts.append({
                'type': 'cpu',
                'level': 'error',
                'message': f'CPU使用率の取得に失敗: {e}'
            })
    
    def check_application_health(self):
        """アプリケーションのヘルスチェック"""
        try:
            # ローカルのヘルスチェックエンドポイントにアクセス
            response = requests.get('http://localhost:8000/health/', timeout=10)
            
            if response.status_code == 200:
                health_data = response.json()
                self.metrics['app_health'] = health_data
                
                if health_data.get('status') != 'healthy':
                    self.alerts.append({
                        'type': 'application',
                        'level': 'critical',
                        'message': f'アプリケーションが不健全な状態: {health_data.get("status")}',
                        'details': health_data.get('checks', {})
                    })
            else:
                self.alerts.append({
                    'type': 'application',
                    'level': 'critical',
                    'message': f'ヘルスチェックが失敗: HTTP {response.status_code}'
                })
                
        except requests.exceptions.RequestException as e:
            self.alerts.append({
                'type': 'application',
                'level': 'critical',
                'message': f'アプリケーションにアクセスできません: {e}'
            })
    
    def check_database_connection(self):
        """データベース接続をチェック"""
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                
            self.metrics['database'] = 'connected'
            
        except Exception as e:
            self.alerts.append({
                'type': 'database',
                'level': 'critical',
                'message': f'データベース接続エラー: {e}'
            })
    
    def check_cache_connection(self):
        """キャッシュ接続をチェック"""
        try:
            cache.set('monitor_test', 'ok', 30)
            result = cache.get('monitor_test')
            
            if result == 'ok':
                self.metrics['cache'] = 'connected'
            else:
                self.alerts.append({
                    'type': 'cache',
                    'level': 'warning',
                    'message': 'キャッシュが正常に動作していません'
                })
                
        except Exception as e:
            self.alerts.append({
                'type': 'cache',
                'level': 'warning',
                'message': f'キャッシュ接続エラー: {e}'
            })
    
    def check_log_files(self):
        """ログファイルをチェック"""
        log_dir = BASE_DIR / 'logs'
        
        if not log_dir.exists():
            self.alerts.append({
                'type': 'logs',
                'level': 'warning',
                'message': 'ログディレクトリが存在しません'
            })
            return
        
        # エラーログの最新エントリをチェック
        error_log = log_dir / 'django_error.log'
        if error_log.exists():
            try:
                # 最後の10行を読み取り
                with open(error_log, 'r') as f:
                    lines = f.readlines()
                    recent_lines = lines[-10:] if len(lines) > 10 else lines
                
                # 最近のエラーをカウント
                recent_errors = [line for line in recent_lines if 'ERROR' in line]
                
                if len(recent_errors) > 5:
                    self.alerts.append({
                        'type': 'logs',
                        'level': 'warning',
                        'message': f'最近のエラーログが多すぎます: {len(recent_errors)}件'
                    })
                    
            except Exception as e:
                self.alerts.append({
                    'type': 'logs',
                    'level': 'error',
                    'message': f'ログファイルの読み取りエラー: {e}'
                })
    
    def send_alert_email(self, alerts):
        """アラートメールを送信"""
        if not alerts:
            return
        
        try:
            # メール設定
            smtp_server = getattr(settings, 'EMAIL_HOST', 'localhost')
            smtp_port = getattr(settings, 'EMAIL_PORT', 587)
            smtp_user = getattr(settings, 'EMAIL_HOST_USER', '')
            smtp_password = getattr(settings, 'EMAIL_HOST_PASSWORD', '')
            from_email = smtp_user or 'monitor@wakakusa-shift.com'
            to_emails = ['admin@wakakusa-shift.com']  # 管理者メールアドレス
            
            # メール本文を作成
            subject = f'🚨 わかくさシフト システムアラート ({len(alerts)}件)'
            
            body = f"""
わかくさシフト管理システムで以下のアラートが発生しました。

発生時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

【アラート一覧】
"""
            
            for i, alert in enumerate(alerts, 1):
                level_emoji = {
                    'critical': '🔴',
                    'warning': '🟡',
                    'error': '❌'
                }.get(alert['level'], '⚠️')
                
                body += f"""
{i}. {level_emoji} {alert['type'].upper()}
   レベル: {alert['level']}
   メッセージ: {alert['message']}
"""
                
                if 'details' in alert:
                    body += f"   詳細: {alert['details']}\n"
            
            body += f"""

【システム状況】
- CPU使用率: {self.metrics.get('cpu_usage', 'N/A')}%
- メモリ使用率: {self.metrics.get('memory_usage', 'N/A')}%
- ディスク使用率: {self.metrics.get('disk_usage', 'N/A')}%
- データベース: {self.metrics.get('database', 'N/A')}
- キャッシュ: {self.metrics.get('cache', 'N/A')}

このメールは自動送信されています。
システム管理者は速やかに対応してください。

---
わかくさシフト監視システム
"""
            
            # メール送信
            msg = MIMEMultipart()
            msg['From'] = from_email
            msg['To'] = ', '.join(to_emails)
            msg['Subject'] = subject
            
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                if smtp_user and smtp_password:
                    server.starttls()
                    server.login(smtp_user, smtp_password)
                
                server.send_message(msg)
            
            print(f"✅ アラートメールを送信しました: {len(alerts)}件")
            
        except Exception as e:
            print(f"❌ アラートメール送信エラー: {e}")
    
    def run_monitoring(self):
        """監視を実行"""
        print(f"🔍 システム監視を開始... ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
        
        # 各種チェックを実行
        self.check_disk_usage()
        self.check_memory_usage()
        self.check_cpu_usage()
        self.check_application_health()
        self.check_database_connection()
        self.check_cache_connection()
        self.check_log_files()
        
        # 結果を表示
        if self.alerts:
            print(f"⚠️ {len(self.alerts)}件のアラートが発生しました:")
            for alert in self.alerts:
                level_emoji = {
                    'critical': '🔴',
                    'warning': '🟡',
                    'error': '❌'
                }.get(alert['level'], '⚠️')
                print(f"  {level_emoji} [{alert['type']}] {alert['message']}")
            
            # アラートメールを送信
            self.send_alert_email(self.alerts)
        else:
            print("✅ すべてのチェックが正常です")
        
        # メトリクスを表示
        print("\n📊 システムメトリクス:")
        for key, value in self.metrics.items():
            print(f"  {key}: {value}")

def main():
    monitor = SystemMonitor()
    monitor.run_monitoring()

if __name__ == '__main__':
    main() 