#!/bin/bash

# 環境へのアプリケーションデプロイスクリプト
# 使用方法: ./deploy_to_environment.sh <環境名>

set -e

# 引数チェック
if [ $# -ne 1 ]; then
    echo "使用方法: $0 <環境名>"
    echo "例: $0 wakakusa-02"
    exit 1
fi

ENV_NAME=$1
SERVER_IP="162.43.31.158"
APP_NAME="wakakusa-shift"
REPO_URL="https://github.com/YOUR_USERNAME/wakakusa-shift-2.git"  # 実際のリポジトリURLに変更してください

echo "=== 環境 '$ENV_NAME' にアプリケーションをデプロイします ==="

# 1. 環境への接続テスト
echo "1. 環境への接続テスト中..."
if ! ssh -i ~/.ssh/id_rsa_BPO_taigakuwata -o ConnectTimeout=10 $ENV_NAME@$SERVER_IP 'echo "接続確認"' > /dev/null 2>&1; then
    echo "❌ 環境 '$ENV_NAME' への接続に失敗しました"
    echo "まず './setup_new_environment.sh $ENV_NAME' を実行してください"
    exit 1
fi

# 2. 環境セットアップスクリプトを生成
echo "2. 環境セットアップスクリプトを生成中..."
cat > "app_setup_${ENV_NAME}.sh" << 'EOF'
#!/bin/bash

set -e

ENV_NAME=$1
APP_NAME="wakakusa-shift"

echo "=== アプリケーション環境セットアップ開始 ==="

# システムパッケージを更新
echo "システムパッケージを更新中..."
sudo apt update && sudo apt upgrade -y

# 必要なパッケージをインストール
echo "必要なパッケージをインストール中..."
sudo apt install -y python3 python3-pip python3-venv git nginx sqlite3 curl

# Python仮想環境を作成
echo "Python仮想環境を作成中..."
cd /home/$ENV_NAME
python3 -m venv venv
source venv/bin/activate

# アプリケーションディレクトリを作成
mkdir -p /home/$ENV_NAME/apps
cd /home/$ENV_NAME/apps

# Gitリポジトリをクローン（既存の場合は更新）
if [ -d "$APP_NAME" ]; then
    echo "既存のリポジトリを更新中..."
    cd $APP_NAME
    git pull origin main
else
    echo "リポジトリをクローン中..."
    # 注意: 実際のリポジトリURLに変更が必要
    echo "手動でリポジトリをクローンしてください:"
    echo "git clone <YOUR_REPO_URL> $APP_NAME"
    mkdir -p $APP_NAME
    cd $APP_NAME
fi

# 仮想環境を有効化
source /home/$ENV_NAME/venv/bin/activate

# 依存関係をインストール（requirements.txtが存在する場合）
if [ -f "requirements.txt" ]; then
    echo "依存関係をインストール中..."
    pip install -r requirements.txt
fi

# データベースの初期化
if [ -f "manage.py" ]; then
    echo "データベースを初期化中..."
    python manage.py migrate
fi

# 静的ファイルの収集
if [ -f "manage.py" ]; then
    echo "静的ファイルを収集中..."
    python manage.py collectstatic --noinput
fi

# Nginxの設定
echo "Nginx設定を準備中..."
sudo mkdir -p /etc/nginx/sites-available
sudo mkdir -p /etc/nginx/sites-enabled

# 簡単なNginx設定ファイルを作成
cat > /tmp/nginx_${ENV_NAME}.conf << NGINX_EOF
server {
    listen 80;
    server_name ${ENV_NAME}.example.com;  # 実際のドメインに変更

    location /static/ {
        alias /home/${ENV_NAME}/apps/${APP_NAME}/static/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
NGINX_EOF

sudo mv /tmp/nginx_${ENV_NAME}.conf /etc/nginx/sites-available/${ENV_NAME}
sudo ln -sf /etc/nginx/sites-available/${ENV_NAME} /etc/nginx/sites-enabled/

# Nginxの設定をテスト
sudo nginx -t

# systemdサービスファイルを作成
echo "systemdサービスファイルを作成中..."
cat > /tmp/${APP_NAME}_${ENV_NAME}.service << SERVICE_EOF
[Unit]
Description=Wakakusa Shift Application for ${ENV_NAME}
After=network.target

[Service]
Type=simple
User=${ENV_NAME}
Group=${ENV_NAME}
WorkingDirectory=/home/${ENV_NAME}/apps/${APP_NAME}
Environment=PATH=/home/${ENV_NAME}/venv/bin
ExecStart=/home/${ENV_NAME}/venv/bin/python manage.py runserver 0.0.0.0:8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SERVICE_EOF

sudo mv /tmp/${APP_NAME}_${ENV_NAME}.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable ${APP_NAME}_${ENV_NAME}.service

echo "=== アプリケーション環境セットアップ完了 ==="
echo "次のコマンドでサービスを開始できます:"
echo "sudo systemctl start ${APP_NAME}_${ENV_NAME}.service"
echo "sudo systemctl restart nginx"
EOF

# 3. サーバー側でアプリケーションセットアップを実行
echo "3. サーバー側でアプリケーションセットアップを実行中..."
scp -i ~/.ssh/id_rsa_BPO_taigakuwata "app_setup_${ENV_NAME}.sh" $ENV_NAME@$SERVER_IP:/home/$ENV_NAME/
ssh -i ~/.ssh/id_rsa_BPO_taigakuwata $ENV_NAME@$SERVER_IP "chmod +x /home/$ENV_NAME/app_setup_${ENV_NAME}.sh && /home/$ENV_NAME/app_setup_${ENV_NAME}.sh $ENV_NAME"

# 4. アプリケーションファイルをアップロード
echo "4. アプリケーションファイルをアップロード中..."
echo "現在のディレクトリからアプリケーションファイルをアップロードします..."

# 除外するファイル・ディレクトリのリストを作成
cat > /tmp/rsync_exclude << 'EXCLUDE_EOF'
.git/
__pycache__/
*.pyc
*.pyo
.env
db.sqlite3
venv/
node_modules/
.DS_Store
*.log
EXCLUDE_EOF

# rsyncでファイルをアップロード
rsync -avz --exclude-from=/tmp/rsync_exclude \
    -e "ssh -i ~/.ssh/id_rsa_BPO_taigakuwata" \
    ./ $ENV_NAME@$SERVER_IP:/home/$ENV_NAME/apps/wakakusa-shift/

# 5. 権限を設定
echo "5. ファイル権限を設定中..."
ssh -i ~/.ssh/id_rsa_BPO_taigakuwata $ENV_NAME@$SERVER_IP "chown -R $ENV_NAME:$ENV_NAME /home/$ENV_NAME/apps/"

# 6. 環境変数ファイルを設定
echo "6. 環境変数ファイルを設定中..."
if [ -f "env.example" ]; then
    scp -i ~/.ssh/id_rsa_BPO_taigakuwata env.example $ENV_NAME@$SERVER_IP:/home/$ENV_NAME/apps/wakakusa-shift/.env
    echo "env.exampleを.envとしてアップロードしました。必要に応じて編集してください。"
fi

# 7. サービスを開始
echo "7. サービスを開始中..."
ssh -i ~/.ssh/id_rsa_BPO_taigakuwata $ENV_NAME@$SERVER_IP << 'START_SERVICES'
cd /home/$ENV_NAME/apps/wakakusa-shift
source /home/$ENV_NAME/venv/bin/activate

# データベースマイグレーション
if [ -f "manage.py" ]; then
    python manage.py migrate
    python manage.py collectstatic --noinput
fi

# サービスを開始
sudo systemctl start wakakusa-shift_$ENV_NAME.service
sudo systemctl restart nginx

# サービスの状態を確認
sudo systemctl status wakakusa-shift_$ENV_NAME.service --no-pager
START_SERVICES

# 8. デプロイ完了メッセージ
echo ""
echo "=== デプロイ完了 ==="
echo "環境名: $ENV_NAME"
echo "サーバーIP: $SERVER_IP"
echo "アプリケーション: $APP_NAME"
echo ""
echo "接続情報:"
echo "- SSH: ssh $ENV_NAME"
echo "- Web: http://$SERVER_IP (または設定したドメイン)"
echo ""
echo "管理コマンド:"
echo "- サービス状態確認: ssh $ENV_NAME 'sudo systemctl status wakakusa-shift_${ENV_NAME}.service'"
echo "- サービス再起動: ssh $ENV_NAME 'sudo systemctl restart wakakusa-shift_${ENV_NAME}.service'"
echo "- ログ確認: ssh $ENV_NAME 'sudo journalctl -u wakakusa-shift_${ENV_NAME}.service -f'"
echo ""
echo "生成されたファイル:"
echo "- app_setup_${ENV_NAME}.sh (アプリケーションセットアップスクリプト)"
echo ""

# 一時ファイルを削除
rm -f /tmp/rsync_exclude 