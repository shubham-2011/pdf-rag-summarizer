import time
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    page.goto("http://localhost:5173")
    page.wait_for_selector("text=Connected", timeout=15000)
    print("Connected.")

    file_input = page.locator("#pdf-input")
    file_input.set_input_files("audit/sample.docx")
    print("File uploaded, waiting for Indexed...")
    page.wait_for_selector("text=Indexed", timeout=30000)
    print("Indexed confirmed.")

    # Check tabs
    tabs = page.locator("button.tab-btn")
    print("Tab count:", tabs.count())
    for i in range(tabs.count()):
        print(f"Tab {i}: {tabs.nth(i).inner_text()}")

    # Click Conversational RAG Q&A
    chat_tab = page.locator("button.tab-btn:has-text('Conversational RAG Q&A')")
    print("Chat tab visible:", chat_tab.is_visible())
    chat_tab.click()
    time.sleep(1)

    # Check composer
    textarea = page.locator(".composer-textarea")
    print("Textarea visible:", textarea.is_visible(), "disabled:", textarea.is_disabled())

    # Type question
    textarea.fill("how many pages are in this document")
    time.sleep(0.5)

    send_btn = page.locator("button.send-btn")
    print("Send btn visible:", send_btn.is_visible(), "disabled:", send_btn.is_disabled())

    send_btn.click()
    print("Clicked send!")

    # Wait 5 seconds
    time.sleep(5)
    print("Assistant bubbles:", page.locator(".message-bubble.assistant").count())
    if page.locator(".message-bubble.assistant").count() > 0:
        print("Content:", page.locator(".message-bubble.assistant").first.inner_text())

    page.screenshot(path="scratch/diag_chat.png")
    browser.close()
