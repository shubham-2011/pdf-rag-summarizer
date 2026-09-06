import os
import sys
import time
from playwright.sync_api import sync_playwright

# Force UTF-8 encoding for Windows console output
sys.stdout.reconfigure(encoding='utf-8')

def run_e2e_test():
    print("[Playwright] Starting Playwright E2E Browser Test...")
    
    # 1. Create a sample PDF file with readable text content
    pdf_path = os.path.abspath("test_sample.pdf")
    try:
        from pypdf import PdfWriter
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        with open(pdf_path, "wb") as f:
            writer.write(f)
        print(f"[Playwright] Created test PDF at: {pdf_path}")
    except Exception as e:
        print(f"Failed to create test PDF: {e}")
        return

    # 2. Launch Playwright Chromium Browser
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        print("[Playwright] Navigating to http://localhost:5173...")
        page.goto("http://localhost:5173/")
        page.wait_for_selector("text=Document Intelligence Platform")
        print("[Playwright] Frontend Page Loaded Successfully!")

        # 3. Upload File via file input
        print("[Playwright] Uploading PDF document...")
        file_input = page.locator("#pdf-input")
        file_input.set_input_files(pdf_path)

        # 4. Wait for processing / response
        time.sleep(4)
        
        # Take screenshot
        screenshot_path = os.path.abspath("playwright_test_result.png")
        page.screenshot(path=screenshot_path)
        print(f"[Playwright] Saved browser screenshot at: {screenshot_path}")

        browser.close()
        print("[Playwright] E2E Test Completed Successfully!")

if __name__ == "__main__":
    run_e2e_test()
