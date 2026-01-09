#!/bin/bash

# 新しい環境セットアップスクリプト
# 使用方法: ./setup_new_environment.sh <環境名>

set -e  # エラーが発生したら終了

# 引数チェック
if [ $# -ne 1 ]; then
    echo "使用方法: $0 <環境名>"
    echo "例: $0 wakakusa-02"
    exit 1
fi

ENV_NAME=$1
SSH_KEY_PATH="./id_rsa_BPO_taigakuwata"
SERVER_IP="162.43.31.158"
BASE_USER="taigakuwata"

echo "=== 新しい環境 '$ENV_NAME' のセットアップを開始します ==="

# 1. SSH鍵の権限を設定
echo "1. SSH鍵の権限を設定中..."
chmod 600 $SSH_KEY_PATH

# 2. SSH設定ファイルに新しい環境を追加
echo "2. SSH設定を更新中..."
SSH_CONFIG_ENTRY="
# 環境: $ENV_NAME
Host $ENV_NAME
    HostName $SERVER_IP
    User $ENV_NAME
    Port 22
    IdentityFile ~/.ssh/id_rsa_BPO_taigakuwata
    IdentitiesOnly yes
"

# ~/.ssh/configに追加（重複チェック付き）
if ! grep -q "Host $ENV_NAME" ~/.ssh/config 2>/dev/null; then
    echo "$SSH_CONFIG_ENTRY" >> ~/.ssh/config
    echo "SSH設定に $ENV_NAME を追加しました"
else
    echo "SSH設定に $ENV_NAME は既に存在します"
fi

# 3. 秘密鍵を~/.sshにコピー
echo "3. 秘密鍵をSSHディレクトリにコピー中..."
cp $SSH_KEY_PATH ~/.ssh/
chmod 600 ~/.ssh/id_rsa_BPO_taigakuwata

# 4. サーバー側でユーザーを作成するスクリプトを生成
echo "4. サーバー側セットアップスクリプトを生成中..."
cat > "server_setup_${ENV_NAME}.sh" << EOF
#!/bin/bash

# サーバー側でのユーザー作成スクリプト
# 実行方法: ssh -i ~/.ssh/id_rsa_BPO_taigakuwata $BASE_USER@$SERVER_IP 'bash -s' < server_setup_${ENV_NAME}.sh

set -e

echo "=== サーバー側: ユーザー '$ENV_NAME' を作成中 ==="

# ユーザーが既に存在するかチェック
if id "$ENV_NAME" &>/dev/null; then
    echo "ユーザー '$ENV_NAME' は既に存在します"
else
    # 新しいユーザーを作成
    sudo useradd -m -s /bin/bash $ENV_NAME
    echo "ユーザー '$ENV_NAME' を作成しました"
fi

# sudoers権限を追加
sudo usermod -aG sudo $ENV_NAME

# SSH用のディレクトリを作成
sudo mkdir -p /home/$ENV_NAME/.ssh
sudo chmod 700 /home/$ENV_NAME/.ssh

# 既存の公開鍵を新しいユーザーにコピー
if [ -f /home/$BASE_USER/.ssh/authorized_keys ]; then
    sudo cp /home/$BASE_USER/.ssh/authorized_keys /home/$ENV_NAME/.ssh/
    sudo chown -R $ENV_NAME:$ENV_NAME /home/$ENV_NAME/.ssh
    sudo chmod 600 /home/$ENV_NAME/.ssh/authorized_keys
    echo "公開鍵を $ENV_NAME ユーザーにコピーしました"
else
    echo "警告: /home/$BASE_USER/.ssh/authorized_keys が見つかりません"
fi

# ホームディレクトリの権限を設定
sudo chown -R $ENV_NAME:$ENV_NAME /home/$ENV_NAME

echo "=== サーバー側セットアップ完了 ==="
EOF

chmod +x "server_setup_${ENV_NAME}.sh"

# 5. サーバー側でユーザーを作成
echo "5. サーバー側でユーザーを作成中..."
echo "サーバーに接続してユーザーを作成します..."
echo "sudoパスワードの入力が必要な場合があります..."

# スクリプトをサーバーにアップロードしてから実行
scp -i ~/.ssh/id_rsa_BPO_taigakuwata "server_setup_${ENV_NAME}.sh" $BASE_USER@$SERVER_IP:/tmp/
ssh -i ~/.ssh/id_rsa_BPO_taigakuwata -t $BASE_USER@$SERVER_IP "chmod +x /tmp/server_setup_${ENV_NAME}.sh && /tmp/server_setup_${ENV_NAME}.sh $ENV_NAME"

# 6. 接続テスト
echo "6. 新しい環境への接続テスト中..."
if ssh -i ~/.ssh/id_rsa_BPO_taigakuwata -o ConnectTimeout=10 $ENV_NAME@$SERVER_IP 'echo "接続成功: $(whoami)@$(hostname)"'; then
    echo "✅ 接続テスト成功!"
else
    echo "❌ 接続テストに失敗しました"
    exit 1
fi

# 7. 環境情報を表示
echo ""
echo "=== 環境セットアップ完了 ==="
echo "環境名: $ENV_NAME"
echo "サーバーIP: $SERVER_IP"
echo "ユーザー名: $ENV_NAME"
echo "SSH接続コマンド: ssh $ENV_NAME"
echo "または: ssh -i ~/.ssh/id_rsa_BPO_taigakuwata $ENV_NAME@$SERVER_IP"
echo ""
echo "生成されたファイル:"
echo "- server_setup_${ENV_NAME}.sh (サーバー側セットアップスクリプト)"
echo ""
echo "次のステップ:"
echo "1. ssh $ENV_NAME でサーバーに接続"
echo "2. 必要なソフトウェアをインストール"
echo "3. アプリケーションをデプロイ"
echo "" 