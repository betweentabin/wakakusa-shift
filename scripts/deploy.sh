#!/bin/bash

# わかくさシフト本番環境デプロイスクリプト
# 使用方法: ./scripts/deploy.sh [production|staging]

set -e  # エラー時に停止

# 設定
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ENVIRONMENT=${1:-production}

# 色付きログ
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 環境チェック
check_environment() {
    log_info "環境チェックを開始..."
    
    # 必要なコマンドの存在確認
    commands=("python3" "pip" "git")
    for cmd in "${commands[@]}"; do
        if ! command -v $cmd &> /dev/null; then
            log_error "$cmd コマンドが見つかりません"
            exit 1
        fi
    done
    
    # 環境変数チェック
    if [ "$ENVIRONMENT" = "production" ]; then
        required_vars=("DJANGO_SECRET_KEY" "DB_NAME" "DB_USER" "DB_PASSWORD" "ALLOWED_HOSTS")
        for var in "${required_vars[@]}"; do
            if [ -z "${!var}" ]; then
                log_error "環境変数 $var が設定されていません"
                exit 1
            fi
        done
    fi
    
    log_success "環境チェック完了"
}

# バックアップ作成
create_backup() {
    log_info "バックアップを作成中..."
    
    # データベースバックアップ
    if [ -f "$PROJECT_DIR/scripts/backup_database.py" ]; then
        cd "$PROJECT_DIR"
        python3 scripts/backup_database.py
        log_success "データベースバックアップ完了"
    else
        log_warning "バックアップスクリプトが見つかりません"
    fi
    
    # 静的ファイルのバックアップ
    if [ -d "$PROJECT_DIR/staticfiles" ]; then
        backup_dir="$PROJECT_DIR/backups/static_$(date +%Y%m%d_%H%M%S)"
        mkdir -p "$backup_dir"
        cp -r "$PROJECT_DIR/staticfiles" "$backup_dir/"
        log_success "静的ファイルバックアップ完了: $backup_dir"
    fi
}

# 依存関係の更新
update_dependencies() {
    log_info "依存関係を更新中..."
    
    cd "$PROJECT_DIR"
    
    # 仮想環境の確認
    if [ ! -d "venv" ]; then
        log_info "仮想環境を作成中..."
        python3 -m venv venv
    fi
    
    # 仮想環境をアクティベート
    source venv/bin/activate
    
    # 依存関係のインストール
    if [ "$ENVIRONMENT" = "production" ]; then
        pip install -r requirements_production.txt
    else
        pip install -r requirements.txt
    fi
    
    log_success "依存関係更新完了"
}

# データベースマイグレーション
run_migrations() {
    log_info "データベースマイグレーションを実行中..."
    
    cd "$PROJECT_DIR"
    source venv/bin/activate
    
    if [ "$ENVIRONMENT" = "production" ]; then
        export DJANGO_SETTINGS_MODULE=core.settings.production
        python3 manage_prod.py migrate --noinput
    else
        export DJANGO_SETTINGS_MODULE=core.settings.development
        python3 manage.py migrate --noinput
    fi
    
    log_success "マイグレーション完了"
}

# 静的ファイル収集
collect_static() {
    log_info "静的ファイルを収集中..."
    
    cd "$PROJECT_DIR"
    source venv/bin/activate
    
    if [ "$ENVIRONMENT" = "production" ]; then
        export DJANGO_SETTINGS_MODULE=core.settings.production
        python3 manage_prod.py collectstatic --noinput --clear
    else
        export DJANGO_SETTINGS_MODULE=core.settings.development
        python3 manage.py collectstatic --noinput --clear
    fi
    
    log_success "静的ファイル収集完了"
}

# パフォーマンス最適化
optimize_performance() {
    log_info "パフォーマンス最適化を実行中..."
    
    cd "$PROJECT_DIR"
    source venv/bin/activate
    
    # データベースインデックス作成
    if [ "$ENVIRONMENT" = "production" ]; then
        export DJANGO_SETTINGS_MODULE=core.settings.production
        python3 -c "
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings.production')
django.setup()
from shift_management.utils.cache import DatabaseOptimization
DatabaseOptimization.create_indexes()
print('✅ インデックス作成完了')
"
    fi
    
    log_success "パフォーマンス最適化完了"
}

# ヘルスチェック
health_check() {
    log_info "ヘルスチェックを実行中..."
    
    # アプリケーションの起動確認
    cd "$PROJECT_DIR"
    source venv/bin/activate
    
    if [ "$ENVIRONMENT" = "production" ]; then
        export DJANGO_SETTINGS_MODULE=core.settings.production
        python3 manage_prod.py check --deploy
    else
        export DJANGO_SETTINGS_MODULE=core.settings.development
        python3 manage.py check
    fi
    
    log_success "ヘルスチェック完了"
}

# ログディレクトリ作成
create_log_directories() {
    log_info "ログディレクトリを作成中..."
    
    mkdir -p "$PROJECT_DIR/logs"
    mkdir -p "$PROJECT_DIR/backups"
    mkdir -p "$PROJECT_DIR/cache"
    
    # 権限設定
    chmod 755 "$PROJECT_DIR/logs"
    chmod 755 "$PROJECT_DIR/backups"
    chmod 755 "$PROJECT_DIR/cache"
    
    log_success "ログディレクトリ作成完了"
}

# メイン処理
main() {
    log_info "=== わかくさシフト デプロイメント開始 ($ENVIRONMENT) ==="
    
    # 処理順序
    check_environment
    create_log_directories
    create_backup
    update_dependencies
    run_migrations
    collect_static
    optimize_performance
    health_check
    
    log_success "=== デプロイメント完了 ==="
    
    # 次のステップの案内
    echo ""
    log_info "次のステップ:"
    if [ "$ENVIRONMENT" = "production" ]; then
        echo "1. Webサーバー（Apache/Nginx）の設定を確認"
        echo "2. SSL証明書の設定を確認"
        echo "3. 定期バックアップのcron設定"
        echo "4. 監視システムの設定"
    else
        echo "1. 開発サーバーを起動: python manage.py runserver"
        echo "2. ブラウザでアクセス: http://localhost:8000"
    fi
}

# スクリプト実行
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi 