#!/bin/bash

# 環境監視スクリプト
# 全環境の健康状態を監視し、レポートを生成

set -e

SERVER_IP="162.43.31.158"
SSH_KEY="~/.ssh/id_rsa_BPO_taigakuwata"
REPORT_FILE="environment_health_report_$(date +%Y%m%d_%H%M%S).txt"

# 色の定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 関数: 色付きメッセージの表示
print_colored() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# 関数: レポートに書き込み
write_report() {
    local message=$1
    echo "$message" >> "$REPORT_FILE"
    echo "$message"
}

# 関数: 既存の環境一覧を取得
get_existing_environments() {
    if [ -f ~/.ssh/config ]; then
        grep "^Host " ~/.ssh/config | grep -v "bpo-taiga" | awk '{print $2}' | grep -E "^wakakusa-" 2>/dev/null || true
    fi
}

# 関数: 環境の詳細な健康状態チェック
check_environment_health() {
    local env_name=$1
    local status="OK"
    
    write_report "=================================================="
    write_report "環境: $env_name"
    write_report "チェック時刻: $(date)"
    write_report "=================================================="
    
    # SSH接続テスト
    if ssh -i ~/.ssh/id_rsa_BPO_taigakuwata -o ConnectTimeout=10 -o BatchMode=yes $env_name@$SERVER_IP 'exit' 2>/dev/null; then
        write_report "✅ SSH接続: OK"
        
        # システム情報取得
        local system_info=$(ssh -i ~/.ssh/id_rsa_BPO_taigakuwata $env_name@$SERVER_IP << 'EOF'
            echo "=== システム情報 ==="
            echo "OS: $(lsb_release -d 2>/dev/null | cut -f2 || echo "Unknown")"
            echo "カーネル: $(uname -r)"
            echo "アップタイム: $(uptime -p)"
            echo "ロードアベレージ: $(uptime | grep -o 'load average:.*')"
            echo ""
            
            echo "=== メモリ使用量 ==="
            free -h
            echo ""
            
            echo "=== ディスク使用量 ==="
            df -h /home/$USER
            echo ""
            
            echo "=== プロセス情報 ==="
            ps aux | grep -E "(python|gunicorn|nginx)" | grep -v grep | head -10
            echo ""
            
            echo "=== ネットワーク接続 ==="
            netstat -tlnp | grep -E ":(80|443|8000)" | head -5
            echo ""
            
            echo "=== サービス状態 ==="
            sudo systemctl status wakakusa-shift_${USER}.service --no-pager -l || echo "サービス未設定"
            echo ""
            
            echo "=== Nginx状態 ==="
            sudo systemctl status nginx --no-pager -l | head -10
            echo ""
            
            echo "=== 最近のログ (最新10行) ==="
            sudo journalctl -u wakakusa-shift_${USER}.service --no-pager -n 10 || echo "ログなし"
            echo ""
            
            echo "=== ディスク容量警告チェック ==="
            df /home/$USER | tail -1 | awk '{
                used = $5
                gsub("%", "", used)
                if (used > 80) {
                    print "⚠️  警告: ディスク使用量が " used "% です"
                } else {
                    print "✅ ディスク使用量: " used "%"
                }
            }'
            
            echo "=== メモリ使用量警告チェック ==="
            free | awk 'NR==2{
                used = $3/$2 * 100
                if (used > 80) {
                    printf "⚠️  警告: メモリ使用量が %.1f%% です\n", used
                } else {
                    printf "✅ メモリ使用量: %.1f%%\n", used
                }
            }'
            
            echo "=== アプリケーション接続テスト ==="
            if curl -s -o /dev/null -w "%{http_code}" http://localhost:8000 2>/dev/null | grep -q "200"; then
                echo "✅ アプリケーション: 正常応答"
            else
                echo "❌ アプリケーション: 応答なし"
            fi
EOF
)
        
        write_report "$system_info"
        
        # 警告チェック
        if echo "$system_info" | grep -q "⚠️"; then
            status="WARNING"
            print_colored $YELLOW "⚠️  環境 '$env_name' に警告があります"
        fi
        
        if echo "$system_info" | grep -q "❌"; then
            status="ERROR"
            print_colored $RED "❌ 環境 '$env_name' にエラーがあります"
        fi
        
    else
        write_report "❌ SSH接続: 失敗"
        status="ERROR"
        print_colored $RED "❌ 環境 '$env_name' への接続に失敗"
    fi
    
    write_report "最終ステータス: $status"
    write_report ""
    
    echo "$status"
}

# 関数: 全環境の監視
monitor_all_environments() {
    local environments=$(get_existing_environments)
    local total_envs=0
    local healthy_envs=0
    local warning_envs=0
    local error_envs=0
    
    # レポートヘッダー
    write_report "========================================"
    write_report "     環境健康状態監視レポート"
    write_report "========================================"
    write_report "生成日時: $(date)"
    write_report "サーバーIP: $SERVER_IP"
    write_report ""
    
    if [ -z "$environments" ]; then
        write_report "監視対象の環境がありません"
        print_colored $YELLOW "監視対象の環境がありません"
        return
    fi
    
    print_colored $BLUE "全環境の健康状態をチェック中..."
    
    for env in $environments; do
        total_envs=$((total_envs + 1))
        local status=$(check_environment_health "$env")
        
        case $status in
            "OK")
                healthy_envs=$((healthy_envs + 1))
                print_colored $GREEN "✅ $env: 正常"
                ;;
            "WARNING")
                warning_envs=$((warning_envs + 1))
                print_colored $YELLOW "⚠️  $env: 警告"
                ;;
            "ERROR")
                error_envs=$((error_envs + 1))
                print_colored $RED "❌ $env: エラー"
                ;;
        esac
    done
    
    # サマリー
    write_report "========================================"
    write_report "           監視結果サマリー"
    write_report "========================================"
    write_report "総環境数: $total_envs"
    write_report "正常: $healthy_envs"
    write_report "警告: $warning_envs"
    write_report "エラー: $error_envs"
    write_report ""
    
    if [ $error_envs -gt 0 ]; then
        write_report "🚨 緊急: $error_envs 個の環境でエラーが発生しています"
    elif [ $warning_envs -gt 0 ]; then
        write_report "⚠️  注意: $warning_envs 個の環境で警告が発生しています"
    else
        write_report "✅ 全ての環境が正常に動作しています"
    fi
    
    write_report "========================================"
    
    # 結果表示
    echo ""
    print_colored $BLUE "========================================"
    print_colored $BLUE "           監視結果サマリー"
    print_colored $BLUE "========================================"
    print_colored $BLUE "総環境数: $total_envs"
    print_colored $GREEN "正常: $healthy_envs"
    print_colored $YELLOW "警告: $warning_envs"
    print_colored $RED "エラー: $error_envs"
    echo ""
    
    if [ $error_envs -gt 0 ]; then
        print_colored $RED "🚨 緊急: $error_envs 個の環境でエラーが発生しています"
    elif [ $warning_envs -gt 0 ]; then
        print_colored $YELLOW "⚠️  注意: $warning_envs 個の環境で警告が発生しています"
    else
        print_colored $GREEN "✅ 全ての環境が正常に動作しています"
    fi
    
    print_colored $BLUE "========================================"
    print_colored $BLUE "詳細レポート: $REPORT_FILE"
}

# 関数: 継続監視モード
continuous_monitoring() {
    local interval=${1:-300}  # デフォルト5分間隔
    
    print_colored $BLUE "継続監視モードを開始します (間隔: ${interval}秒)"
    print_colored $YELLOW "停止するには Ctrl+C を押してください"
    
    while true; do
        print_colored $BLUE "$(date): 監視を実行中..."
        monitor_all_environments
        
        print_colored $BLUE "次の監視まで ${interval} 秒待機します..."
        sleep "$interval"
    done
}

# 関数: アラート送信 (将来の拡張用)
send_alert() {
    local message=$1
    local severity=$2
    
    # 将来的にSlack、メール、webhookなどに対応可能
    echo "アラート ($severity): $message"
    
    # 例: Slack webhook (要設定)
    # if [ -n "$SLACK_WEBHOOK_URL" ]; then
    #     curl -X POST -H 'Content-type: application/json' \
    #         --data "{\"text\":\"$message\"}" \
    #         "$SLACK_WEBHOOK_URL"
    # fi
}

# メイン関数
main() {
    case "${1:-once}" in
        "once")
            monitor_all_environments
            ;;
        "continuous")
            continuous_monitoring "${2:-300}"
            ;;
        "help")
            echo "使用方法:"
            echo "  $0 [once|continuous] [間隔秒数]"
            echo ""
            echo "  once       - 一度だけ監視を実行 (デフォルト)"
            echo "  continuous - 継続監視モード"
            echo "  間隔秒数   - 継続監視の間隔 (デフォルト: 300秒)"
            echo ""
            echo "例:"
            echo "  $0                    # 一度だけ実行"
            echo "  $0 once              # 一度だけ実行"
            echo "  $0 continuous        # 5分間隔で継続監視"
            echo "  $0 continuous 60     # 1分間隔で継続監視"
            ;;
        *)
            print_colored $RED "無効なオプションです。'$0 help' でヘルプを表示してください。"
            exit 1
            ;;
    esac
}

# スクリプトの実行
main "$@" 