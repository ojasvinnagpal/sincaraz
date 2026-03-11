"""Debug script — tests multiple anti-detection approaches."""
import asyncio
from playwright.async_api import async_playwright

async def test_approach(browser, label, context_args, extra_js=None):
    context = await browser.new_context(**context_args)
    page = await context.new_page()
    
    if extra_js:
        await page.add_init_script(extra_js)

    # Visit homepage first for cookies
    await page.goto("https://www.atptour.com/en/players/jannik-sinner/s0ag/overview",
                    wait_until="domcontentloaded", timeout=20000)
    await page.wait_for_timeout(2000)

    # Now hit the API
    url = "https://www.atptour.com/en/-/www/players/hero/s0ag?v=1"
    response = await page.goto(url, wait_until="domcontentloaded", timeout=15000)
    text = await page.evaluate("() => document.body.innerText")
    
    print(f"\n[{label}]")
    print(f"  Status: {response.status}")
    print(f"  Body: {repr(text[:200])}")
    
    await context.close()
    return response.status == 200

async def main():
    async with async_playwright() as p:
        
        # Approach 1: Non-headless (real visible browser)
        print("=== Approach 1: Non-headless browser ===")
        browser = await p.chromium.launch(headless=False)
        success = await test_approach(browser, "non-headless", {
            "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        })
        await browser.close()
        if success:
            print("  ✅ NON-HEADLESS WORKS")
            return

        # Approach 2: Headless with stealth JS patches
        print("\n=== Approach 2: Headless + stealth patches ===")
        browser = await p.chromium.launch(headless=True)
        stealth_js = """
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
        Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
        window.chrome = {runtime: {}};
        """
        success = await test_approach(browser, "headless+stealth", {
            "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "extra_http_headers": {"Accept-Language": "en-US,en;q=0.9"},
        }, extra_js=stealth_js)
        await browser.close()
        if success:
            print("  ✅ HEADLESS+STEALTH WORKS")
            return

        # Approach 3: Firefox instead of Chromium
        print("\n=== Approach 3: Firefox ===")
        browser = await p.firefox.launch(headless=True)
        success = await test_approach(browser, "firefox", {
            "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:123.0) Gecko/20100101 Firefox/123.0",
        })
        await browser.close()
        if success:
            print("  ✅ FIREFOX WORKS")
            return

        print("\n❌ All approaches blocked. ATP has strict bot detection.")

asyncio.run(main())
