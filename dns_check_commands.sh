#!/bin/bash
# DNS設定確認用コマンド集

echo "=== DNS設定確認コマンド ==="
echo

echo "1. メインドメインの確認:"
echo "nslookup xrosspoint-bpo.com"
echo "dig xrosspoint-bpo.com"
echo

echo "2. サブドメインの確認:"
echo "nslookup shift.xrosspoint-bpo.com"
echo "nslookup admin.xrosspoint-bpo.com"
echo

echo "3. DNS伝播確認（複数のDNSサーバーで確認）:"
echo "dig @8.8.8.8 xrosspoint-bpo.com"
echo "dig @1.1.1.1 xrosspoint-bpo.com"
echo "dig @208.67.222.222 xrosspoint-bpo.com"
echo

echo "4. TTL確認:"
echo "dig xrosspoint-bpo.com | grep -E 'IN.*A'"
echo

echo "5. 全世界での伝播確認（オンラインツール）:"
echo "https://www.whatsmydns.net/#A/xrosspoint-bpo.com"
echo "https://dnschecker.org/"
echo

echo "6. 接続テスト（DNS設定後）:"
echo "curl -I http://xrosspoint-bpo.com:8000/"
echo "curl -I https://xrosspoint-bpo.com:8443/"
echo

echo "=== 実行例 ==="
echo "# DNS設定前（現在）"
nslookup xrosspoint-bpo.com 2>/dev/null || echo "DNS未設定（正常）"
echo

echo "# サーバーへの直接接続確認"
echo "curl -s -o /dev/null -w 'Status: %{http_code}, Time: %{time_total}s' http://162.43.31.158:8000/"
curl -s -o /dev/null -w 'Status: %{http_code}, Time: %{time_total}s' http://162.43.31.158:8000/ 