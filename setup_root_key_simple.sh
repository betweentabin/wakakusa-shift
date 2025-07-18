#!/bin/bash

# rootユーザーに公開鍵を設定する簡単なスクリプト

echo "=== rootユーザーに公開鍵を設定します ==="

# 現在のユーザーの公開鍵を確認
echo "現在のユーザーの公開鍵:"
cat ~/.ssh/authorized_keys

echo ""
echo "この公開鍵をrootユーザーに設定します..."
echo "sudoパスワード（1234）を使用します..."

# rootユーザーの.sshディレクトリを作成
echo "1234" | sudo -S mkdir -p /root/.ssh
echo "1234" | sudo -S chmod 700 /root/.ssh

# 公開鍵をrootユーザーにコピー
echo "1234" | sudo -S cp ~/.ssh/authorized_keys /root/.ssh/authorized_keys
echo "1234" | sudo -S chmod 600 /root/.ssh/authorized_keys
echo "1234" | sudo -S chown root:root /root/.ssh/authorized_keys

echo ""
echo "✅ 公開鍵をrootユーザーに設定しました"

# 設定確認
echo ""
echo "=== 設定確認 ==="
echo "root .ssh ディレクトリ:"
echo "1234" | sudo -S ls -la /root/.ssh/

echo ""
echo "root authorized_keys:"
echo "1234" | sudo -S cat /root/.ssh/authorized_keys

echo ""
echo "🎉 設定完了！"
echo ""
echo "rootユーザーでの接続テスト:"
echo "ssh -i ~/.ssh/id_rsa_BPO_taigakuwata root@162.43.31.158" 