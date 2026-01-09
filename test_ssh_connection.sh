#!/bin/bash

echo "=== SSH接続テストスクリプト ==="
echo ""

# 接続情報を表示
echo "接続先サーバー情報："
echo "  Host: xserver-vps-BPO-taigakuwata"
echo "  IP: 162.43.31.158"
echo "  User: taigakuwata"
echo "  Port: 22"
echo ""

# 秘密鍵の存在確認
if [ -f ~/.ssh/id_rsa_BPO_taigakuwata ]; then
    echo "✓ 秘密鍵が見つかりました: ~/.ssh/id_rsa_BPO_taigakuwata"
else
    echo "✗ 秘密鍵が見つかりません。setup_ssh_environment.shを実行してください。"
    exit 1
fi

# SSH設定の確認
if [ -f ~/.ssh/config ]; then
    echo "✓ SSH設定ファイルが見つかりました: ~/.ssh/config"
else
    echo "✗ SSH設定ファイルが見つかりません。setup_ssh_environment.shを実行してください。"
    exit 1
fi

echo ""
echo "=== 接続テスト開始 ==="

# SSH接続テスト（Host設定を使用）
echo "1. Host設定を使用した接続テスト..."
ssh -o ConnectTimeout=10 -o BatchMode=yes bpo-taiga 'echo "SSH接続成功！"; whoami; pwd; date'

if [ $? -eq 0 ]; then
    echo "✓ Host設定での接続が成功しました！"
else
    echo "✗ Host設定での接続に失敗しました。直接接続を試します..."
    
    # 直接接続テスト
    echo "2. 直接接続テスト..."
    ssh -o ConnectTimeout=10 -o BatchMode=yes -i ~/.ssh/id_rsa_BPO_taigakuwata taigakuwata@162.43.31.158 'echo "SSH接続成功！"; whoami; pwd; date'
    
    if [ $? -eq 0 ]; then
        echo "✓ 直接接続が成功しました！"
    else
        echo "✗ 接続に失敗しました。以下を確認してください："
        echo "  - サーバーが起動しているか"
        echo "  - ネットワーク接続が正常か"
        echo "  - 秘密鍵の権限が正しいか (600)"
        echo "  - 公開鍵がサーバーに登録されているか"
    fi
fi

echo ""
echo "=== 手動接続コマンド ==="
echo "以下のコマンドで手動接続できます："
echo "ssh bpo-taiga"
echo ""
echo "または："
echo "ssh -i ~/.ssh/id_rsa_BPO_taigakuwata taigakuwata@162.43.31.158" 