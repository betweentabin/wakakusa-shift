#!/bin/bash

# サーバー側でのユーザー作成スクリプト
# 実行方法: ssh -i ~/.ssh/id_rsa_BPO_taigakuwata taigakuwata@162.43.31.158 'bash -s' < server_setup_wakakusa-test.sh

set -e

echo "=== サーバー側: ユーザー 'wakakusa-test' を作成中 ==="

# ユーザーが既に存在するかチェック
if id "wakakusa-test" &>/dev/null; then
    echo "ユーザー 'wakakusa-test' は既に存在します"
else
    # 新しいユーザーを作成
    sudo useradd -m -s /bin/bash wakakusa-test
    echo "ユーザー 'wakakusa-test' を作成しました"
fi

# sudoers権限を追加
sudo usermod -aG sudo wakakusa-test

# SSH用のディレクトリを作成
sudo mkdir -p /home/wakakusa-test/.ssh
sudo chmod 700 /home/wakakusa-test/.ssh

# 既存の公開鍵を新しいユーザーにコピー
if [ -f /home/taigakuwata/.ssh/authorized_keys ]; then
    sudo cp /home/taigakuwata/.ssh/authorized_keys /home/wakakusa-test/.ssh/
    sudo chown -R wakakusa-test:wakakusa-test /home/wakakusa-test/.ssh
    sudo chmod 600 /home/wakakusa-test/.ssh/authorized_keys
    echo "公開鍵を wakakusa-test ユーザーにコピーしました"
else
    echo "警告: /home/taigakuwata/.ssh/authorized_keys が見つかりません"
fi

# ホームディレクトリの権限を設定
sudo chown -R wakakusa-test:wakakusa-test /home/wakakusa-test

echo "=== サーバー側セットアップ完了 ==="
