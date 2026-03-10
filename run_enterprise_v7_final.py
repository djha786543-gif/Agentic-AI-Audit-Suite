import asyncio
import os
import random
from datetime import datetime
from playwright.async_api import async_playwright, TimeoutError as PWTimeout

# --- CONFIGURATION ---
BASE_URL = "https://djha786543-gif.github.io/Agentic-AI-Audit-Suite/index.html"
BASE_PATH = os.path.expanduser("~/Documents")
TS = datetime.now().strftime("%Y%m%d_%H%M%S")

async def think(page, lo=1.2, hi=2.5):
    await asyncio.sleep(random.uniform(lo, hi))

async def highlight_element(page, locator):
    try:
        text = await locator.inner_text()
        color = "red" if "Critical" in text or "Exception" in text else "gold"
        await locator.evaluate(f"el => {{ el.style.outline = '4px solid {color}'; el.style.boxShadow = '0 0 12px {color}'; }}")
    except: pass

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=800)
        context = await browser.new_context(record_video_dir=BASE_PATH, viewport={"width": 1600, "height": 900})
        page = await context.new_page()
        try:
            print(f"[{TS}] --- STARTING INTEGRATED REAL-EMPLOYEE WALKTHROUGH ---")
            await page.goto(BASE_URL, wait_until="networkidle", timeout=30000)
            arch = page.get_by_text("Architecture Workflow Diagram").first
            await arch.scroll_into_view_if_needed()
            await highlight_element(page, arch)
            await think(page, 3, 4)
            modules = ["Dashboard", "SOD Auditor", "JE Forensics", "Config Drift", "Report"]
            for mod in modules:
                print(f"Auditing Module: {mod}")
                nav_link = page.get_by_text(mod, exact=True).first
                await nav_link.scroll_into_view_if_needed()
                await highlight_element(page, nav_link)
                await nav_link.click(force=True)
                await asyncio.sleep(2)
                rows = page.locator("table tbody tr")
                if await rows.count() > 0:
                    for i in range(min(2, await rows.count())):
                        await rows.nth(i).hover()
                        await asyncio.sleep(0.5)
                await page.mouse.wheel(0, 500)
                await think(page, 2, 3)
            exec_btn = page.get_by_text("Execute Audit").first
            await highlight_element(page, exec_btn)
            await exec_btn.click()
            await asyncio.sleep(6)
            await page.screenshot(path=os.path.join(BASE_PATH, f"V7_Final_Report_{TS}.png"))
        finally:
            video_obj = page.video
            await context.close()
            if video_obj:
                raw_path = await video_obj.path()
                final_video = os.path.join(BASE_PATH, f"ENTERPRISE_V7_FINAL_{TS}.webm")
                os.rename(raw_path, final_video)
                print(f"\n? MASTER VIDEO COMMITTED: {final_video}")
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
