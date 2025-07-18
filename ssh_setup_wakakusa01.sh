#!/bin/bash

# 新しいユーザー wakakusa-01 を作成
sudo useradd -m -s /bin/bash wakakusa-01

# パスワードを設定（対話式）
sudo passwd wakakusa-01

# sudoers権限を追加（必要に応じて）
sudo usermod -aG sudo wakakusa-01

# SSH用のディレクトリを作成
sudo mkdir -p /home/wakakusa-01/.ssh
sudo chmod 700 /home/wakakusa-01/.ssh

# 既存の公開鍵を新しいユーザーにコピー（同じ鍵を使用する場合）
sudo cp /home/taigakuwata/.ssh/authorized_keys /home/wakakusa-01/.ssh/
sudo chown -R wakakusa-01:wakakusa-01 /home/wakakusa-01/.ssh
sudo chmod 600 /home/wakakusa-01/.ssh/authorized_keys

echo "新しいユーザー wakakusa-01 が作成されました"
echo "SSH接続テスト: ssh -i id_rsa_BPO_taigakuwata wakakusa-01@162.43.31.158" 