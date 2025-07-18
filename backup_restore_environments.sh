#!/bin/bash

# 環境バックアップ・リストアスクリプト
# 環境のデータベース、設定ファイル、アプリケーションファイルをバックアップ・リストア

set -e

SERVER_IP="162.43.31.158"
SSH_KEY="~/.ssh/id_rsa_BPO_taigakuwata"
BACKUP_DIR="./backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

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

# 関数: 既存の環境一覧を取得
get_existing_environments() {
    if [ -f ~/.ssh/config ]; then
        grep "^Host " ~/.ssh/config | grep -v "bpo-taiga" | awk '{print $2}' | grep -E "^wakakusa-" 2>/dev/null || true
    fi
}

# 関数: バックアップディレクトリの作成
create_backup_directory() {
    local env_name=$1
    local backup_path="$BACKUP_DIR/${env_name}_${TIMESTAMP}"
    
    mkdir -p "$backup_path"
    echo "$backup_path"
}

# 関数: 環境のバックアップ
backup_environment() {
    local env_name=$1
    
    if [ -z "$env_name" ]; then
        print_colored $RED "環境名が指定されていません"
        return 1
    fi
    
    # 環境の存在確認
    local environments=$(get_existing_environments)
    if ! echo "$environments" | grep -q "^$env_name$"; then
        print_colored $RED "環境 '$env_name' が見つかりません"
        return 1
    fi
    
    # SSH接続テスト
    if ! ssh -i ~/.ssh/id_rsa_BPO_taigakuwata -o ConnectTimeout=10 -o BatchMode=yes $env_name@$SERVER_IP 'exit' 2>/dev/null; then
        print_colored $RED "環境 '$env_name' への接続に失敗しました"
        return 1
    fi
    
    local backup_path=$(create_backup_directory "$env_name")
    
    print_colored $BLUE "=== 環境 '$env_name' のバックアップを開始します ==="
    print_colored $BLUE "バックアップ先: $backup_path"
    
    # 1. システム情報の保存
    print_colored $YELLOW "1. システム情報を保存中..."
    ssh -i ~/.ssh/id_rsa_BPO_taigakuwata $env_name@$SERVER_IP << 'EOF' > "$backup_path/system_info.txt"
        echo "=== システム情報 ==="
        echo "バックアップ日時: $(date)"
        echo "ホスト名: $(hostname)"
        echo "OS: $(lsb_release -d 2>/dev/null | cut -f2 || echo "Unknown")"
        echo "カーネル: $(uname -r)"
        echo "ユーザー: $(whoami)"
        echo ""
        
        echo "=== インストール済みパッケージ ==="
        dpkg -l | grep -E "(python|nginx|git)" || true
        echo ""
        
        echo "=== サービス状態 ==="
        sudo systemctl status wakakusa-shift_${USER}.service --no-pager || true
        echo ""
        sudo systemctl status nginx --no-pager || true
        echo ""
        
        echo "=== 環境変数 ==="
        env | grep -E "(PATH|PYTHON|DJANGO)" || true
        echo ""
        
        echo "=== ネットワーク設定 ==="
        netstat -tlnp | grep -E ":(80|443|8000)" || true
EOF
    
    # 2. アプリケーションファイルのバックアップ
    print_colored $YELLOW "2. アプリケーションファイルをバックアップ中..."
    mkdir -p "$backup_path/app_files"
    rsync -avz --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
        -e "ssh -i ~/.ssh/id_rsa_BPO_taigakuwata" \
        $env_name@$SERVER_IP:/home/$env_name/apps/wakakusa-shift/ \
        "$backup_path/app_files/" || true
    
    # 3. データベースのバックアップ
    print_colored $YELLOW "3. データベースをバックアップ中..."
    ssh -i ~/.ssh/id_rsa_BPO_taigakuwata $env_name@$SERVER_IP << 'EOF'
        cd /home/$USER/apps/wakakusa-shift
        if [ -f "db.sqlite3" ]; then
            cp db.sqlite3 db_backup_$(date +%Y%m%d_%H%M%S).sqlite3
            echo "SQLiteデータベースをバックアップしました"
        fi
        
        # Djangoのデータをjsonでエクスポート
        if [ -f "manage.py" ]; then
            source /home/$USER/venv/bin/activate
            python manage.py dumpdata --natural-foreign --natural-primary > data_backup_$(date +%Y%m%d_%H%M%S).json
            echo "Djangoデータをjsonでエクスポートしました"
        fi
EOF
    
    # バックアップしたデータベースファイルをダウンロード
    scp -i ~/.ssh/id_rsa_BPO_taigakuwata \
        $env_name@$SERVER_IP:/home/$env_name/apps/wakakusa-shift/db_backup_*.sqlite3 \
        "$backup_path/" 2>/dev/null || true
    
    scp -i ~/.ssh/id_rsa_BPO_taigakuwata \
        $env_name@$SERVER_IP:/home/$env_name/apps/wakakusa-shift/data_backup_*.json \
        "$backup_path/" 2>/dev/null || true
    
    # 4. 設定ファイルのバックアップ
    print_colored $YELLOW "4. 設定ファイルをバックアップ中..."
    mkdir -p "$backup_path/config"
    
    # .env ファイル
    scp -i ~/.ssh/id_rsa_BPO_taigakuwata \
        $env_name@$SERVER_IP:/home/$env_name/apps/wakakusa-shift/.env \
        "$backup_path/config/" 2>/dev/null || true
    
    # systemd サービスファイル
    ssh -i ~/.ssh/id_rsa_BPO_taigakuwata $env_name@$SERVER_IP \
        "sudo cp /etc/systemd/system/wakakusa-shift_${env_name}.service /tmp/" 2>/dev/null || true
    scp -i ~/.ssh/id_rsa_BPO_taigakuwata \
        $env_name@$SERVER_IP:/tmp/wakakusa-shift_${env_name}.service \
        "$backup_path/config/" 2>/dev/null || true
    
    # nginx 設定ファイル
    ssh -i ~/.ssh/id_rsa_BPO_taigakuwata $env_name@$SERVER_IP \
        "sudo cp /etc/nginx/sites-available/${env_name} /tmp/" 2>/dev/null || true
    scp -i ~/.ssh/id_rsa_BPO_taigakuwata \
        $env_name@$SERVER_IP:/tmp/${env_name} \
        "$backup_path/config/nginx_${env_name}.conf" 2>/dev/null || true
    
    # 5. ログファイルのバックアップ
    print_colored $YELLOW "5. ログファイルをバックアップ中..."
    mkdir -p "$backup_path/logs"
    
    ssh -i ~/.ssh/id_rsa_BPO_taigakuwata $env_name@$SERVER_IP \
        "sudo journalctl -u wakakusa-shift_${env_name}.service --no-pager > /tmp/service_logs.txt" 2>/dev/null || true
    scp -i ~/.ssh/id_rsa_BPO_taigakuwata \
        $env_name@$SERVER_IP:/tmp/service_logs.txt \
        "$backup_path/logs/" 2>/dev/null || true
    
    # 6. バックアップ情報ファイルの作成
    print_colored $YELLOW "6. バックアップ情報ファイルを作成中..."
    cat > "$backup_path/backup_info.txt" << EOF
=== バックアップ情報 ===
環境名: $env_name
バックアップ日時: $(date)
バックアップ作成者: $(whoami)
サーバーIP: $SERVER_IP
バックアップパス: $backup_path

=== バックアップ内容 ===
- system_info.txt: システム情報
- app_files/: アプリケーションファイル
- db_backup_*.sqlite3: SQLiteデータベース
- data_backup_*.json: Djangoデータ（JSON形式）
- config/: 設定ファイル
  - .env: 環境変数
  - wakakusa-shift_${env_name}.service: systemdサービス設定
  - nginx_${env_name}.conf: Nginx設定
- logs/: ログファイル
  - service_logs.txt: サービスログ

=== リストア方法 ===
./backup_restore_environments.sh restore $env_name $backup_path
EOF
    
    # 7. バックアップの圧縮
    print_colored $YELLOW "7. バックアップを圧縮中..."
    cd "$BACKUP_DIR"
    tar -czf "${env_name}_${TIMESTAMP}.tar.gz" "${env_name}_${TIMESTAMP}/"
    
    print_colored $GREEN "✅ バックアップが完了しました"
    print_colored $BLUE "バックアップファイル: $BACKUP_DIR/${env_name}_${TIMESTAMP}.tar.gz"
    print_colored $BLUE "バックアップディレクトリ: $backup_path"
}

# 関数: 環境のリストア
restore_environment() {
    local env_name=$1
    local backup_path=$2
    
    if [ -z "$env_name" ] || [ -z "$backup_path" ]; then
        print_colored $RED "環境名とバックアップパスを指定してください"
        print_colored $BLUE "使用方法: $0 restore <環境名> <バックアップパス>"
        return 1
    fi
    
    # バックアップの存在確認
    if [ ! -d "$backup_path" ]; then
        # 圧縮ファイルの場合は展開
        if [ -f "$backup_path.tar.gz" ]; then
            print_colored $BLUE "圧縮ファイルを展開中..."
            cd "$BACKUP_DIR"
            tar -xzf "$backup_path.tar.gz"
        else
            print_colored $RED "バックアップが見つかりません: $backup_path"
            return 1
        fi
    fi
    
    # 環境の存在確認
    local environments=$(get_existing_environments)
    if ! echo "$environments" | grep -q "^$env_name$"; then
        print_colored $YELLOW "環境 '$env_name' が存在しません。先に環境を作成してください。"
        read -p "環境を作成しますか？ (y/n): " create_env
        if [ "$create_env" = "y" ] || [ "$create_env" = "Y" ]; then
            ./setup_new_environment.sh "$env_name"
        else
            return 1
        fi
    fi
    
    print_colored $BLUE "=== 環境 '$env_name' のリストアを開始します ==="
    print_colored $BLUE "バックアップ元: $backup_path"
    
    # 1. サービスの停止
    print_colored $YELLOW "1. サービスを停止中..."
    ssh -i ~/.ssh/id_rsa_BPO_taigakuwata $env_name@$SERVER_IP \
        "sudo systemctl stop wakakusa-shift_${env_name}.service" 2>/dev/null || true
    
    # 2. アプリケーションファイルのリストア
    print_colored $YELLOW "2. アプリケーションファイルをリストア中..."
    if [ -d "$backup_path/app_files" ]; then
        rsync -avz --delete \
            -e "ssh -i ~/.ssh/id_rsa_BPO_taigakuwata" \
            "$backup_path/app_files/" \
            $env_name@$SERVER_IP:/home/$env_name/apps/wakakusa-shift/
    fi
    
    # 3. データベースのリストア
    print_colored $YELLOW "3. データベースをリストア中..."
    if [ -f "$backup_path"/db_backup_*.sqlite3 ]; then
        scp -i ~/.ssh/id_rsa_BPO_taigakuwata \
            "$backup_path"/db_backup_*.sqlite3 \
            $env_name@$SERVER_IP:/home/$env_name/apps/wakakusa-shift/db.sqlite3
    fi
    
    # 4. 設定ファイルのリストア
    print_colored $YELLOW "4. 設定ファイルをリストア中..."
    if [ -f "$backup_path/config/.env" ]; then
        scp -i ~/.ssh/id_rsa_BPO_taigakuwata \
            "$backup_path/config/.env" \
            $env_name@$SERVER_IP:/home/$env_name/apps/wakakusa-shift/
    fi
    
    # systemd サービスファイルのリストア
    if [ -f "$backup_path/config/wakakusa-shift_${env_name}.service" ]; then
        scp -i ~/.ssh/id_rsa_BPO_taigakuwata \
            "$backup_path/config/wakakusa-shift_${env_name}.service" \
            $env_name@$SERVER_IP:/tmp/
        ssh -i ~/.ssh/id_rsa_BPO_taigakuwata $env_name@$SERVER_IP \
            "sudo mv /tmp/wakakusa-shift_${env_name}.service /etc/systemd/system/ && sudo systemctl daemon-reload"
    fi
    
    # nginx 設定ファイルのリストア
    if [ -f "$backup_path/config/nginx_${env_name}.conf" ]; then
        scp -i ~/.ssh/id_rsa_BPO_taigakuwata \
            "$backup_path/config/nginx_${env_name}.conf" \
            $env_name@$SERVER_IP:/tmp/
        ssh -i ~/.ssh/id_rsa_BPO_taigakuwata $env_name@$SERVER_IP \
            "sudo mv /tmp/nginx_${env_name}.conf /etc/nginx/sites-available/${env_name} && sudo ln -sf /etc/nginx/sites-available/${env_name} /etc/nginx/sites-enabled/"
    fi
    
    # 5. 権限の修正
    print_colored $YELLOW "5. 権限を修正中..."
    ssh -i ~/.ssh/id_rsa_BPO_taigakuwata $env_name@$SERVER_IP \
        "chown -R ${env_name}:${env_name} /home/${env_name}/apps/"
    
    # 6. 依存関係の再インストール
    print_colored $YELLOW "6. 依存関係を再インストール中..."
    ssh -i ~/.ssh/id_rsa_BPO_taigakuwata $env_name@$SERVER_IP << 'EOF'
        cd /home/$USER/apps/wakakusa-shift
        source /home/$USER/venv/bin/activate
        if [ -f "requirements.txt" ]; then
            pip install -r requirements.txt
        fi
        
        # データベースマイグレーション
        if [ -f "manage.py" ]; then
            python manage.py migrate
            python manage.py collectstatic --noinput
        fi
EOF
    
    # 7. サービスの開始
    print_colored $YELLOW "7. サービスを開始中..."
    ssh -i ~/.ssh/id_rsa_BPO_taigakuwata $env_name@$SERVER_IP << EOF
        sudo systemctl enable wakakusa-shift_${env_name}.service
        sudo systemctl start wakakusa-shift_${env_name}.service
        sudo systemctl reload nginx
        
        # サービス状態の確認
        sudo systemctl status wakakusa-shift_${env_name}.service --no-pager
EOF
    
    print_colored $GREEN "✅ リストアが完了しました"
    print_colored $BLUE "環境 '$env_name' が正常に復元されました"
}

# 関数: バックアップ一覧の表示
list_backups() {
    print_colored $BLUE "=== バックアップ一覧 ==="
    
    if [ ! -d "$BACKUP_DIR" ]; then
        print_colored $YELLOW "バックアップディレクトリが存在しません"
        return
    fi
    
    local backup_files=$(find "$BACKUP_DIR" -name "*.tar.gz" -o -type d -name "wakakusa-*" | sort)
    
    if [ -z "$backup_files" ]; then
        print_colored $YELLOW "バックアップファイルが見つかりません"
        return
    fi
    
    echo "$backup_files" | while read backup; do
        if [ -f "$backup" ]; then
            local size=$(du -h "$backup" | cut -f1)
            local date=$(stat -c %y "$backup" | cut -d' ' -f1)
            print_colored $GREEN "📁 $backup ($size, $date)"
        elif [ -d "$backup" ]; then
            local size=$(du -sh "$backup" | cut -f1)
            local date=$(stat -c %y "$backup" | cut -d' ' -f1)
            print_colored $BLUE "📂 $backup ($size, $date)"
        fi
    done
}

# メイン関数
main() {
    case "${1:-help}" in
        "backup")
            backup_environment "$2"
            ;;
        "restore")
            restore_environment "$2" "$3"
            ;;
        "list")
            list_backups
            ;;
        "help")
            echo "環境バックアップ・リストアスクリプト"
            echo ""
            echo "使用方法:"
            echo "  $0 backup <環境名>                    # 環境をバックアップ"
            echo "  $0 restore <環境名> <バックアップパス>  # 環境をリストア"
            echo "  $0 list                               # バックアップ一覧を表示"
            echo ""
            echo "例:"
            echo "  $0 backup wakakusa-01"
            echo "  $0 restore wakakusa-01 ./backups/wakakusa-01_20240101_120000"
            echo "  $0 list"
            ;;
        *)
            print_colored $RED "無効なオプションです。'$0 help' でヘルプを表示してください。"
            exit 1
            ;;
    esac
}

# バックアップディレクトリの作成
mkdir -p "$BACKUP_DIR"

# スクリプトの実行
main "$@" 