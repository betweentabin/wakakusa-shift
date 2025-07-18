#!/bin/bash

# sudoパスワードなしでコマンドを実行できるようにする設定

echo "=== sudo NOPASSWD設定を追加します ==="
echo "一度だけsudoパスワードの入力が必要です"

# taigakuwataユーザーにNOPASSWDを設定
echo "taigakuwata ALL=(ALL) NOPASSWD:ALL" | sudo tee /etc/sudoers.d/taigakuwata

# ファイルの権限を設定
sudo chmod 440 /etc/sudoers.d/taigakuwata

# 設定を確認
sudo visudo -c

echo "=== 設定完了 ==="
echo "これで以降はsudoパスワードなしでコマンドを実行できます" 