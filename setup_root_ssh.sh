#!/bin/bash

# rootユーザーSSH設定スクリプト

echo "=== rootユーザーSSH設定を開始します ==="

# rootユーザーの.sshディレクトリを作成
sudo mkdir -p /root/.ssh
sudo chmod 700 /root/.ssh

# 現在のユーザーの公開鍵をrootユーザーにコピー
sudo cp ~/.ssh/authorized_keys /root/.ssh/authorized_keys
sudo chmod 600 /root/.ssh/authorized_keys
sudo chown root:root /root/.ssh/authorized_keys

echo "公開鍵をrootユーザーにコピーしました"

# SSH設定ファイルを確認・修正
echo "SSH設定を確認中..."

# sshd_configのバックアップを作成
sudo cp /etc/ssh/sshd_config /etc/ssh/sshd_config.backup

# rootログインを許可する設定を追加/修正
sudo sed -i 's/#PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config
sudo sed -i 's/PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config

# 公開鍵認証を有効にする
sudo sed -i 's/#PubkeyAuthentication.*/PubkeyAuthentication yes/' /etc/ssh/sshd_config
sudo sed -i 's/PubkeyAuthentication.*/PubkeyAuthentication yes/' /etc/ssh/sshd_config

# パスワード認証を無効にする（セキュリティのため）
sudo sed -i 's/#PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo sed -i 's/PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config

echo "SSH設定を更新しました"

# SSH設定の構文チェック
if sudo sshd -t; then
    echo "SSH設定の構文チェック: OK"
    
    # SSHサービスを再起動
    sudo systemctl restart ssh
    echo "SSHサービスを再起動しました"
    
    # 設定確認
    echo ""
    echo "=== 設定確認 ==="
    echo "PermitRootLogin: $(sudo grep '^PermitRootLogin' /etc/ssh/sshd_config || echo 'デフォルト設定')"
    echo "PubkeyAuthentication: $(sudo grep '^PubkeyAuthentication' /etc/ssh/sshd_config || echo 'デフォルト設定')"
    echo "PasswordAuthentication: $(sudo grep '^PasswordAuthentication' /etc/ssh/sshd_config || echo 'デフォルト設定')"
    
    echo ""
    echo "=== rootユーザーSSH設定完了 ==="
    echo "接続テスト用コマンド:"
    echo "ssh -i ~/.ssh/id_rsa_BPO_taigakuwata root@162.43.31.158"
    
else
    echo "❌ SSH設定にエラーがあります。設定を復元します..."
    sudo cp /etc/ssh/sshd_config.backup /etc/ssh/sshd_config
    exit 1
fi 