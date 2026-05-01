# PDF用フォント配置ディレクトリ

WeasyPrint/ReportLabで日本語文字を確実に描画するため、
日本語フォント（例: NotoSansJP-Regular.ttf）をここに配置してください。

推奨フォント:
- Noto Sans JP / Noto Sans CJK JP（Google/Noto, OFL ライセンス）
- IPAexゴシック（IPA フォントライセンス）

配置例:
- `static/fonts/NotoSansJP-Regular.ttf`

アプリ側の実装では、`static/fonts/NotoSansJP-Regular.ttf` を @font-face で読み込み、
WeasyPrint に base_url として STATIC_ROOT または `./static` を渡しています。
ファイルを配置後、`collectstatic` とアプリ再起動を行ってください。

注意: フォントファイルはライセンスを確認の上、ご自身の責任で配置してください。

