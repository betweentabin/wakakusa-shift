# SSH接続コマンド集

## 基本接続
```bash
# サーバーに接続
ssh bpo-server

# または
ssh wakakusa-shift
```

## プロジェクト管理
```bash
# プロジェクトディレクトリに移動して接続
ssh bpo-server -t "cd wakakusa-shift && bash"

# サーバーの状態確認
ssh bpo-server "systemctl status wakakusa-shift"

# ログ確認
ssh bpo-server "tail -f /var/log/wakakusa_shift/django.log"

# プロセス確認
ssh bpo-server "ps aux | grep gunicorn"
```

## ファイル転送
```bash
# ローカルからサーバーへファイル転送
scp ファイル名 bpo-server:~/wakakusa-shift/

# サーバーからローカルへファイル転送
scp bpo-server:~/wakakusa-shift/ファイル名 ./

# ディレクトリ全体を転送
scp -r ディレクトリ名 bpo-server:~/wakakusa-shift/
```

## デプロイ・更新
```bash
# Gitプル
ssh bpo-server "cd wakakusa-shift && git pull origin main"

# サービス再起動
ssh bpo-server "sudo systemctl restart wakakusa-shift"

# 静的ファイル収集
ssh bpo-server "cd wakakusa-shift && python manage.py collectstatic --noinput"
```

## データベース操作
```bash
# マイグレーション
ssh bpo-server "cd wakakusa-shift && python manage.py migrate"

# データベースバックアップ
ssh bpo-server "cd wakakusa-shift && python manage.py dumpdata > backup_$(date +%Y%m%d).json"

# スーパーユーザー作成
ssh bpo-server "cd wakakusa-shift && python manage.py createsuperuser"
```

## システム監視
```bash
# ディスク使用量
ssh bpo-server "df -h"

# メモリ使用量
ssh bpo-server "free -h"

# CPU使用率
ssh bpo-server "top -n 1"

# ネットワーク接続
ssh bpo-server "netstat -tlnp | grep :8000"
```

## 接続情報
- **ホスト**: 162.43.31.158
- **ユーザー**: taigakuwata
- **ポート**: 22
- **秘密鍵**: ~/.ssh/id_rsa_bpo 