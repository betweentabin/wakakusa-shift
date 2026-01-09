#!/bin/bash

# 環境管理スクリプト
# 複数の環境を簡単に管理するためのメニューシステム

set -e

SERVER_IP="162.43.31.158"
SSH_KEY="~/.ssh/id_rsa_BPO_taigakuwata"

# 色の定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 関数: 色付きメッセージの表示
print_colored() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# 関数: 既存の環境一覧を取得
get_existing_environments() {
    if [ -f ~/.ssh/config ]; then
        grep "^Host " ~/.ssh/config | grep -v "bpo-taiga" | awk '{print $2}' | grep -E "^wakakusa-" 2>/dev/null || true
    fi
}

# 関数: 環境の状態を確認
check_environment_status() {
    local env_name=$1
    print_colored $BLUE "環境 '$env_name' の状態を確認中..."
    
    # SSH接続テスト
    if ssh -i ~/.ssh/id_rsa_BPO_taigakuwata -o ConnectTimeout=5 -o BatchMode=yes $env_name@$SERVER_IP 'exit' 2>/dev/null; then
        print_colored $GREEN "✅ SSH接続: OK"
        
        # サービス状態確認
        local service_status=$(ssh -i ~/.ssh/id_rsa_BPO_taigakuwata $env_name@$SERVER_IP "sudo systemctl is-active wakakusa-shift_${env_name}.service 2>/dev/null || echo 'not-found'")
        if [ "$service_status" = "active" ]; then
            print_colored $GREEN "✅ サービス: 稼働中"
        elif [ "$service_status" = "inactive" ]; then
            print_colored $YELLOW "⚠️  サービス: 停止中"
        else
            print_colored $RED "❌ サービス: 未設定"
        fi
        
        # ディスク使用量確認
        local disk_usage=$(ssh -i ~/.ssh/id_rsa_BPO_taigakuwata $env_name@$SERVER_IP "df -h /home/$env_name | tail -1 | awk '{print \$5}'")
        print_colored $BLUE "💾 ディスク使用量: $disk_usage"
        
    else
        print_colored $RED "❌ SSH接続: 失敗"
    fi
    echo ""
}

# 関数: 環境一覧の表示
list_environments() {
    print_colored $BLUE "=== 既存の環境一覧 ==="
    local environments=$(get_existing_environments)
    
    if [ -z "$environments" ]; then
        print_colored $YELLOW "設定された環境がありません"
        return
    fi
    
    for env in $environments; do
        check_environment_status $env
    done
}

# 関数: 新しい環境の作成
create_environment() {
    print_colored $BLUE "=== 新しい環境の作成 ==="
    
    read -p "環境名を入力してください (例: wakakusa-03): " env_name
    
    if [ -z "$env_name" ]; then
        print_colored $RED "環境名が入力されていません"
        return
    fi
    
    # 既存環境との重複チェック
    local existing_envs=$(get_existing_environments)
    if echo "$existing_envs" | grep -q "^$env_name$"; then
        print_colored $RED "環境 '$env_name' は既に存在します"
        return
    fi
    
    print_colored $GREEN "環境 '$env_name' を作成します..."
    ./setup_new_environment.sh "$env_name"
    
    read -p "続けてアプリケーションをデプロイしますか？ (y/n): " deploy_choice
    if [ "$deploy_choice" = "y" ] || [ "$deploy_choice" = "Y" ]; then
        ./deploy_to_environment.sh "$env_name"
    fi
}

# 関数: 環境の削除
delete_environment() {
    print_colored $BLUE "=== 環境の削除 ==="
    
    local environments=$(get_existing_environments)
    if [ -z "$environments" ]; then
        print_colored $YELLOW "削除可能な環境がありません"
        return
    fi
    
    print_colored $BLUE "削除可能な環境:"
    echo "$environments" | nl
    
    read -p "削除する環境名を入力してください: " env_name
    
    if [ -z "$env_name" ]; then
        print_colored $RED "環境名が入力されていません"
        return
    fi
    
    if ! echo "$environments" | grep -q "^$env_name$"; then
        print_colored $RED "環境 '$env_name' が見つかりません"
        return
    fi
    
    print_colored $YELLOW "警告: 環境 '$env_name' を削除します。この操作は取り消せません。"
    read -p "本当に削除しますか？ (yes/no): " confirm
    
    if [ "$confirm" != "yes" ]; then
        print_colored $BLUE "削除をキャンセルしました"
        return
    fi
    
    print_colored $RED "環境 '$env_name' を削除中..."
    
    # サーバー側でユーザーとサービスを削除
    ssh -i ~/.ssh/id_rsa_BPO_taigakuwata taigakuwata@$SERVER_IP << EOF
        # サービスを停止・削除
        sudo systemctl stop wakakusa-shift_${env_name}.service 2>/dev/null || true
        sudo systemctl disable wakakusa-shift_${env_name}.service 2>/dev/null || true
        sudo rm -f /etc/systemd/system/wakakusa-shift_${env_name}.service
        sudo systemctl daemon-reload
        
        # Nginx設定を削除
        sudo rm -f /etc/nginx/sites-enabled/${env_name}
        sudo rm -f /etc/nginx/sites-available/${env_name}
        sudo systemctl reload nginx
        
        # ユーザーを削除
        sudo userdel -r ${env_name} 2>/dev/null || true
        
        echo "サーバー側の削除完了"
EOF
    
    # ローカルのSSH設定から削除
    if [ -f ~/.ssh/config ]; then
        # 一時ファイルを作成して、該当環境の設定を除外
        grep -v -A 5 "^Host $env_name$" ~/.ssh/config > ~/.ssh/config.tmp || true
        mv ~/.ssh/config.tmp ~/.ssh/config
    fi
    
    # 生成されたファイルを削除
    rm -f "server_setup_${env_name}.sh"
    rm -f "app_setup_${env_name}.sh"
    
    print_colored $GREEN "環境 '$env_name' の削除が完了しました"
}

# 関数: 環境の再デプロイ
redeploy_environment() {
    print_colored $BLUE "=== 環境の再デプロイ ==="
    
    local environments=$(get_existing_environments)
    if [ -z "$environments" ]; then
        print_colored $YELLOW "再デプロイ可能な環境がありません"
        return
    fi
    
    print_colored $BLUE "再デプロイ可能な環境:"
    echo "$environments" | nl
    
    read -p "再デプロイする環境名を入力してください: " env_name
    
    if [ -z "$env_name" ]; then
        print_colored $RED "環境名が入力されていません"
        return
    fi
    
    if ! echo "$environments" | grep -q "^$env_name$"; then
        print_colored $RED "環境 '$env_name' が見つかりません"
        return
    fi
    
    print_colored $GREEN "環境 '$env_name' を再デプロイします..."
    ./deploy_to_environment.sh "$env_name"
}

# 関数: 環境への接続
connect_to_environment() {
    print_colored $BLUE "=== 環境への接続 ==="
    
    local environments=$(get_existing_environments)
    if [ -z "$environments" ]; then
        print_colored $YELLOW "接続可能な環境がありません"
        return
    fi
    
    print_colored $BLUE "接続可能な環境:"
    echo "$environments" | nl
    
    read -p "接続する環境名を入力してください: " env_name
    
    if [ -z "$env_name" ]; then
        print_colored $RED "環境名が入力されていません"
        return
    fi
    
    if ! echo "$environments" | grep -q "^$env_name$"; then
        print_colored $RED "環境 '$env_name' が見つかりません"
        return
    fi
    
    print_colored $GREEN "環境 '$env_name' に接続します..."
    ssh -i ~/.ssh/id_rsa_BPO_taigakuwata $env_name@$SERVER_IP
}

# 関数: ログの表示
show_logs() {
    print_colored $BLUE "=== ログの表示 ==="
    
    local environments=$(get_existing_environments)
    if [ -z "$environments" ]; then
        print_colored $YELLOW "ログを表示できる環境がありません"
        return
    fi
    
    print_colored $BLUE "ログを表示できる環境:"
    echo "$environments" | nl
    
    read -p "ログを表示する環境名を入力してください: " env_name
    
    if [ -z "$env_name" ]; then
        print_colored $RED "環境名が入力されていません"
        return
    fi
    
    if ! echo "$environments" | grep -q "^$env_name$"; then
        print_colored $RED "環境 '$env_name' が見つかりません"
        return
    fi
    
    print_colored $GREEN "環境 '$env_name' のログを表示します..."
    ssh -i ~/.ssh/id_rsa_BPO_taigakuwata $env_name@$SERVER_IP "sudo journalctl -u wakakusa-shift_${env_name}.service -f"
}

# メイン関数
main() {
    clear
    print_colored $BLUE "╭─────────────────────────────────────────────────────────╮"
    print_colored $BLUE "│                 環境管理システム                        │"
    print_colored $BLUE "│                Wakakusa Shift                           │"
    print_colored $BLUE "╰─────────────────────────────────────────────────────────╯"
    echo ""
    
    while true; do
        print_colored $YELLOW "メニューを選択してください:"
        echo "1. 環境一覧表示"
        echo "2. 新しい環境を作成"
        echo "3. 環境を削除"
        echo "4. 環境を再デプロイ"
        echo "5. 環境に接続"
        echo "6. ログを表示"
        echo "7. 終了"
        echo ""
        
        read -p "選択 (1-7): " choice
        echo ""
        
        case $choice in
            1)
                list_environments
                ;;
            2)
                create_environment
                ;;
            3)
                delete_environment
                ;;
            4)
                redeploy_environment
                ;;
            5)
                connect_to_environment
                ;;
            6)
                show_logs
                ;;
            7)
                print_colored $GREEN "環境管理システムを終了します"
                exit 0
                ;;
            *)
                print_colored $RED "無効な選択です。1-7の数字を入力してください。"
                ;;
        esac
        
        echo ""
        read -p "Enterキーを押して続行..."
        clear
    done
}

# スクリプトの実行
main 