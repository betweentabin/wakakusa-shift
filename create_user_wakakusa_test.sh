#!/bin/bash

# ユーザー作成スクリプト
ENV_NAME="wakakusa-test"

echo "=== ユーザー '$ENV_NAME' を作成中 ==="

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
if [ -f /home/taigakuwata/.ssh/authorized_keys ]; then
    sudo cp /home/taigakuwata/.ssh/authorized_keys /home/$ENV_NAME/.ssh/
    sudo chown -R $ENV_NAME:$ENV_NAME /home/$ENV_NAME/.ssh
    sudo chmod 600 /home/$ENV_NAME/.ssh/authorized_keys
    echo "公開鍵を $ENV_NAME ユーザーにコピーしました"
else
    echo "警告: /home/taigakuwata/.ssh/authorized_keys が見つかりません"
fi

# ホームディレクトリの権限を設定
sudo chown -R $ENV_NAME:$ENV_NAME /home/$ENV_NAME

echo "=== ユーザー作成完了 ==="
echo "接続テスト用コマンド: ssh -i ~/.ssh/id_rsa_BPO_taigakuwata $ENV_NAME@162.43.31.158" 