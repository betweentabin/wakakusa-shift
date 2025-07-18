# 環境セットアップガイド

このガイドでは、秘密鍵 `id_rsa_BPO_taigakuwata` を使用して新しい環境を構築する方法を説明します。

## 前提条件

- 秘密鍵 `id_rsa_BPO_taigakuwata` がプロジェクトルートに存在すること
- 既存のベースユーザー `taigakuwata` でサーバーにアクセスできること
- サーバーIP: `162.43.31.158`

## 使用方法

### 1. 新しい環境の作成

```bash
# 実行権限を付与
chmod +x setup_new_environment.sh

# 新しい環境を作成（例: wakakusa-02）
./setup_new_environment.sh wakakusa-02
```

このスクリプトが実行する内容:
- SSH鍵の権限設定
- SSH設定ファイルの更新
- 秘密鍵の~/.sshディレクトリへのコピー
- サーバー側でのユーザー作成
- 接続テスト

### 2. アプリケーションのデプロイ

```bash
# 実行権限を付与
chmod +x deploy_to_environment.sh

# アプリケーションをデプロイ
./deploy_to_environment.sh wakakusa-02
```

このスクリプトが実行する内容:
- 環境への接続テスト
- システムパッケージの更新
- 必要なソフトウェアのインストール
- Python仮想環境の作成
- アプリケーションファイルのアップロード
- データベースの初期化
- Nginxの設定
- systemdサービスの設定
- サービスの開始

## 生成されるファイル

### 環境作成時
- `server_setup_<環境名>.sh`: サーバー側でのユーザー作成スクリプト

### デプロイ時
- `app_setup_<環境名>.sh`: アプリケーション環境セットアップスクリプト

## 接続方法

環境作成後、以下のコマンドで接続できます:

```bash
# SSH設定を使用した接続
ssh wakakusa-02

# 直接接続
ssh -i ~/.ssh/id_rsa_BPO_taigakuwata wakakusa-02@162.43.31.158
```

## 管理コマンド

### サービス管理
```bash
# サービス状態確認
ssh wakakusa-02 'sudo systemctl status wakakusa-shift_wakakusa-02.service'

# サービス再起動
ssh wakakusa-02 'sudo systemctl restart wakakusa-shift_wakakusa-02.service'

# ログ確認
ssh wakakusa-02 'sudo journalctl -u wakakusa-shift_wakakusa-02.service -f'
```

### アプリケーション管理
```bash
# アプリケーションディレクトリに移動
ssh wakakusa-02 'cd /home/wakakusa-02/apps/wakakusa-shift'

# 仮想環境を有効化
ssh wakakusa-02 'source /home/wakakusa-02/venv/bin/activate'

# Djangoコマンドの実行
ssh wakakusa-02 'cd /home/wakakusa-02/apps/wakakusa-shift && source /home/wakakusa-02/venv/bin/activate && python manage.py <コマンド>'
```

## トラブルシューティング

### 接続エラー
```bash
# SSH接続の詳細ログを確認
ssh -v wakakusa-02

# 秘密鍵の権限を確認
ls -la ~/.ssh/id_rsa_BPO_taigakuwata
# 結果: -rw------- (600権限である必要があります)
```

### サービスエラー
```bash
# サービスの詳細ログを確認
ssh wakakusa-02 'sudo journalctl -u wakakusa-shift_wakakusa-02.service --no-pager'

# Nginxの設定をテスト
ssh wakakusa-02 'sudo nginx -t'

# Nginxを再起動
ssh wakakusa-02 'sudo systemctl restart nginx'
```

### 権限エラー
```bash
# ファイル権限を修正
ssh wakakusa-02 'sudo chown -R wakakusa-02:wakakusa-02 /home/wakakusa-02/apps/'
```

## 注意事項

1. **セキュリティ**: 秘密鍵は適切に管理し、権限を600に設定してください
2. **ドメイン**: Nginx設定でドメイン名を実際のものに変更してください
3. **リポジトリ**: デプロイスクリプト内のリポジトリURLを実際のものに変更してください
4. **環境変数**: `.env`ファイルを適切に設定してください

## ファイル構成

```
/home/<環境名>/
├── venv/                    # Python仮想環境
├── apps/
│   └── wakakusa-shift/      # アプリケーションディレクトリ
└── app_setup_<環境名>.sh    # セットアップスクリプト
```

## 複数環境の管理

複数の環境を作成する場合:

```bash
# 環境1
./setup_new_environment.sh wakakusa-01
./deploy_to_environment.sh wakakusa-01

# 環境2
./setup_new_environment.sh wakakusa-02
./deploy_to_environment.sh wakakusa-02

# 環境3
./setup_new_environment.sh wakakusa-03
./deploy_to_environment.sh wakakusa-03
```

各環境は独立しており、それぞれ異なるポートとサービス名を使用します。

## 追加ツール

### 1. 環境管理システム (manage_environments.sh)

メニュー形式で環境を管理できる統合ツールです。

```bash
# 実行権限を付与
chmod +x manage_environments.sh

# 環境管理システムを開始
./manage_environments.sh
```

機能:
- 環境一覧表示（状態確認付き）
- 新しい環境の作成
- 環境の削除
- 環境の再デプロイ
- 環境への接続
- ログの表示

### 2. 環境監視システム (monitor_environments.sh)

全環境の健康状態を監視し、詳細なレポートを生成します。

```bash
# 実行権限を付与
chmod +x monitor_environments.sh

# 一度だけ監視を実行
./monitor_environments.sh once

# 継続監視モード (5分間隔)
./monitor_environments.sh continuous

# 継続監視モード (1分間隔)
./monitor_environments.sh continuous 60
```

監視項目:
- SSH接続状態
- システム情報（OS、メモリ、ディスク）
- サービス状態
- アプリケーション応答
- ログ分析
- 警告・エラー検出

### 3. バックアップ・リストアシステム (backup_restore_environments.sh)

環境の完全なバックアップとリストアを行います。

```bash
# 実行権限を付与
chmod +x backup_restore_environments.sh

# 環境をバックアップ
./backup_restore_environments.sh backup wakakusa-01

# 環境をリストア
./backup_restore_environments.sh restore wakakusa-01 ./backups/wakakusa-01_20240101_120000

# バックアップ一覧を表示
./backup_restore_environments.sh list
```

バックアップ内容:
- システム情報
- アプリケーションファイル
- データベース（SQLite + JSON）
- 設定ファイル（.env、systemd、nginx）
- ログファイル

## 完全なワークフロー

### 新しい環境の作成から運用まで

```bash
# 1. 新しい環境を作成
./setup_new_environment.sh wakakusa-02

# 2. アプリケーションをデプロイ
./deploy_to_environment.sh wakakusa-02

# 3. 環境の状態を確認
./monitor_environments.sh once

# 4. バックアップを作成
./backup_restore_environments.sh backup wakakusa-02

# 5. 継続監視を開始 (別ターミナルで)
./monitor_environments.sh continuous
```

### 統合管理

```bash
# 環境管理システムを使用して全てを管理
./manage_environments.sh
```

## 自動化とスケジューリング

### crontabでの定期実行

```bash
# crontabを編集
crontab -e

# 例: 毎日午前2時にバックアップ
0 2 * * * /path/to/wakakusa-shift-2/backup_restore_environments.sh backup wakakusa-01

# 例: 5分ごとに監視
*/5 * * * * /path/to/wakakusa-shift-2/monitor_environments.sh once >> /var/log/wakakusa-monitor.log 2>&1
```

### systemdサービスでの監視

```bash
# 監視サービスファイルを作成
sudo tee /etc/systemd/system/wakakusa-monitor.service << EOF
[Unit]
Description=Wakakusa Environment Monitor
After=network.target

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=/path/to/wakakusa-shift-2
ExecStart=/path/to/wakakusa-shift-2/monitor_environments.sh continuous 300
Restart=always
RestartSec=60

[Install]
WantedBy=multi-user.target
EOF

# サービスを有効化・開始
sudo systemctl daemon-reload
sudo systemctl enable wakakusa-monitor.service
sudo systemctl start wakakusa-monitor.service
``` 