#!/bin/bash

echo "=== SSH接続環境セットアップスクリプト ==="
echo "サーバー: xserver-vps-BPO-taigakuwata"
echo "ホスト: 162.43.31.158"
echo "ユーザー: taigakuwata"
echo ""

# SSH設定ディレクトリの作成
echo "1. SSH設定ディレクトリを作成中..."
mkdir -p ~/.ssh
chmod 700 ~/.ssh

# 秘密鍵をSSHディレクトリにコピー
echo "2. 秘密鍵を配置中..."
cp ./id_rsa_BPO_taigakuwata ~/.ssh/
chmod 600 ~/.ssh/id_rsa_BPO_taigakuwata

# SSH設定ファイルを更新
echo "3. SSH設定ファイルを更新中..."
cat >> ~/.ssh/config << 'EOF'

# Wakakusa Shift - BPO Taiga Server
Host bpo-taiga
    HostName 162.43.31.158
    User taigakuwata
    Port 22
    IdentityFile ~/.ssh/id_rsa_BPO_taigakuwata
    IdentitiesOnly yes
    ServerAliveInterval 60
    ServerAliveCountMax 3

# Wakakusa Shift - 新環境用
Host wakakusa-01
    HostName 162.43.31.158
    User wakakusa-01
    Port 22
    IdentityFile ~/.ssh/id_rsa_BPO_taigakuwata
    IdentitiesOnly yes
    ServerAliveInterval 60
    ServerAliveCountMax 3
EOF

# SSH設定ファイルの権限を設定
chmod 600 ~/.ssh/config

echo "4. 設定完了！"
echo ""
echo "=== 接続テスト ==="
echo "以下のコマンドで接続をテストできます："
echo "ssh bpo-taiga"
echo ""
echo "または直接："
echo "ssh -i ~/.ssh/id_rsa_BPO_taigakuwata taigakuwata@162.43.31.158"
echo ""
echo "=== サーバー情報 ==="
echo "Host: xserver-vps-BPO-taigakuwata"
echo "IP: 162.43.31.158"
echo "User: taigakuwata"
echo "Port: 22"
echo "秘密鍵: ~/.ssh/id_rsa_BPO_taigakuwata"
echo ""
echo "新しいユーザー環境を作成する場合は、以下のスクリプトを実行してください："
echo "./ssh_setup_wakakusa01.sh" 