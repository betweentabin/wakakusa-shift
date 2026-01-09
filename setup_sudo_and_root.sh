#!/bin/bash

# sudo NOPASSWD設定とrootアクセス設定を一度に行うスクリプト

echo "=== sudo NOPASSWD設定とrootアクセス設定を開始します ==="
echo "一度だけsudoパスワードの入力が必要です"

# 1. sudo NOPASSWD設定
echo "1. sudo NOPASSWD設定を追加中..."
echo "taigakuwata ALL=(ALL) NOPASSWD:ALL" | sudo tee /etc/sudoers.d/taigakuwata
sudo chmod 440 /etc/sudoers.d/taigakuwata

# 設定を確認
if sudo visudo -c; then
    echo "✅ sudoers設定が正常に追加されました"
else
    echo "❌ sudoers設定にエラーがあります"
    exit 1
fi

# 2. rootユーザーのSSH設定
echo "2. rootユーザーSSH設定を開始中..."

# rootユーザーの.sshディレクトリを作成
sudo mkdir -p /root/.ssh
sudo chmod 700 /root/.ssh

# 現在のユーザーの公開鍵をrootユーザーにコピー
sudo cp ~/.ssh/authorized_keys /root/.ssh/authorized_keys
sudo chmod 600 /root/.ssh/authorized_keys
sudo chown root:root /root/.ssh/authorized_keys

echo "✅ 公開鍵をrootユーザーにコピーしました"

# SSH設定ファイルを修正
echo "3. SSH設定を更新中..."

# sshd_configのバックアップを作成
sudo cp /etc/ssh/sshd_config /etc/ssh/sshd_config.backup

# rootログインを許可する設定を追加/修正
sudo sed -i 's/#PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config
sudo sed -i 's/PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config

# 公開鍵認証を有効にする
sudo sed -i 's/#PubkeyAuthentication.*/PubkeyAuthentication yes/' /etc/ssh/sshd_config
sudo sed -i 's/PubkeyAuthentication.*/PubkeyAuthentication yes/' /etc/ssh/sshd_config

# SSH設定の構文チェック
if sudo sshd -t; then
    echo "✅ SSH設定の構文チェック: OK"
    
    # SSHサービスを再起動
    sudo systemctl restart ssh
    echo "✅ SSHサービスを再起動しました"
    
    # 設定確認
    echo ""
    echo "=== 設定確認 ==="
    echo "PermitRootLogin: $(sudo grep '^PermitRootLogin' /etc/ssh/sshd_config || echo 'デフォルト設定')"
    echo "PubkeyAuthentication: $(sudo grep '^PubkeyAuthentication' /etc/ssh/sshd_config || echo 'デフォルト設定')"
    
    echo ""
    echo "🎉 設定完了！"
    echo ""
    echo "以降、以下のコマンドでパスワードなしsudoが使用できます:"
    echo "sudo whoami"
    echo ""
    echo "rootユーザーでの接続テスト:"
    echo "ssh -i ~/.ssh/id_rsa_BPO_taigakuwata root@162.43.31.158"
    
else
    echo "❌ SSH設定にエラーがあります。設定を復元します..."
    sudo cp /etc/ssh/sshd_config.backup /etc/ssh/sshd_config
    exit 1
fi

# 4. 最終テスト
echo ""
echo "4. 設定テスト中..."
echo "sudo テスト: $(sudo whoami)"
echo "root .ssh ディレクトリ: $(sudo ls -la /root/.ssh/)" 