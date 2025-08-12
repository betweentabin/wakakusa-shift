import asyncio
from playwright.async_api import async_playwright
import os

async def check_mobile_layout():
    async with async_playwright() as p:
        # iPhone 12のビューポート設定
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={'width': 390, 'height': 844},
            device_scale_factor=3,
            is_mobile=True,
            has_touch=True,
            user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Mobile/15E148 Safari/604.1'
        )
        
        page = await context.new_page()
        
        try:
            # ページにアクセス
            await page.goto('http://127.0.0.1:8000/cultivation/', wait_until='networkidle')
            
            # スクリーンショット保存用ディレクトリ作成
            os.makedirs('mobile_screenshots', exist_ok=True)
            
            # フルページスクリーンショット
            await page.screenshot(path='mobile_screenshots/cultivation_mobile_full.png', full_page=True)
            
            # ビューポート内のスクリーンショット
            await page.screenshot(path='mobile_screenshots/cultivation_mobile_viewport.png')
            
            # スクロール位置を変えてスクリーンショット
            await page.evaluate('window.scrollTo(0, document.body.scrollHeight / 2)')
            await page.screenshot(path='mobile_screenshots/cultivation_mobile_middle.png')
            
            await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            await page.screenshot(path='mobile_screenshots/cultivation_mobile_bottom.png')
            
            print("モバイルサイズでのスクリーンショットを保存しました:")
            print("- mobile_screenshots/cultivation_mobile_full.png (フルページ)")
            print("- mobile_screenshots/cultivation_mobile_viewport.png (ビューポート)")
            print("- mobile_screenshots/cultivation_mobile_middle.png (中間部分)")
            print("- mobile_screenshots/cultivation_mobile_bottom.png (下部)")
            
            # 30秒待機（手動で確認するため）
            print("\nブラウザを開いたまま30秒待機します。手動で確認してください。")
            await asyncio.sleep(30)
            
        except Exception as e:
            print(f"エラーが発生しました: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(check_mobile_layout())