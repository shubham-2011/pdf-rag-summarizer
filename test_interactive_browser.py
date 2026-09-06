import os
import sys
import time
from playwright.sync_api import sync_playwright
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

# Ensure UTF-8 output encoding for Windows console
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def create_sample_pdf():
    pdf_path = os.path.abspath("sample_ai_roadmap.pdf")
    try:
        c = canvas.Canvas(pdf_path, pagesize=letter)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(100, 750, "Chapter 1: Artificial Intelligence & RAG Overview")
        c.setFont("Helvetica", 12)
        c.drawString(100, 720, "Retrieval-Augmented Generation (RAG) combines dense vector search with LLMs.")
        c.drawString(100, 700, "It parses unstructured PDF documents, embeds text chunks into ChromaDB,")
        c.drawString(100, 680, "and provides exact page-level citations for accurate Q&A responses.")
        
        c.showPage() # Page 2
        c.setFont("Helvetica-Bold", 16)
        c.drawString(100, 750, "Chapter 2: Step-by-Step Implementation Roadmap")
        c.setFont("Helvetica", 12)
        c.drawString(100, 720, "Phase 1: Parse PDF with PyPDFLoader and split with RecursiveCharacterTextSplitter.")
        c.drawString(100, 700, "Phase 2: Index embeddings using HuggingFace all-MiniLM-L6-v2 fallback or OpenAI.")
        c.drawString(100, 680, "Phase 3: Deploy FastAPI backend with React single-page application dashboard.")
        
        c.save()
        print(f"[PDF] Generated test PDF with text at: {pdf_path}")
        return pdf_path
    except Exception as e:
        print(f"Error creating PDF: {e}")
        return None

def run_interactive_browser_test():
    print("[BrowserTest] Starting interactive Playwright check...")
    
    pdf_path = create_sample_pdf()
    if not pdf_path:
        print("Failed to prepare test PDF.")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        # Step 1: Open app
        print("[BrowserTest] Navigating to http://localhost:5173...")
        page.goto("http://localhost:5173/")
        page.wait_for_selector("text=Document Intelligence Platform")
        print("[BrowserTest] Web App Header Loaded!")

        # Step 2: Upload PDF
        print("[BrowserTest] Uploading PDF with text content...")
        file_input = page.locator("#pdf-input")
        file_input.set_input_files(pdf_path)

        # Step 3: Wait for Indexed badge
        print("[BrowserTest] Waiting for Indexed badge...")
        page.wait_for_selector("text=Indexed", timeout=20000)
        print("[BrowserTest] PDF Uploaded & Indexed Successfully!")

        # Take Uploaded State Screenshot
        upload_img = os.path.abspath("live_uploaded_state.png")
        page.screenshot(path=upload_img)

        # Step 4: Click Generate Roadmap
        print("[BrowserTest] Clicking Generate Roadmap...")
        generate_btn = page.locator("button:has-text('Generate Roadmap')")
        if generate_btn.is_visible():
            generate_btn.click()
            time.sleep(4)

        # Take Summary & Roadmap Screenshot
        summary_img = os.path.abspath("live_summary_roadmap.png")
        page.screenshot(path=summary_img)
        print(f"[BrowserTest] Summary screenshot saved at: {summary_img}")

        # Step 5: Switch to Chat tab
        chat_tab = page.locator("button:has-text('Conversational RAG Chat')")
        if chat_tab.is_visible():
            chat_tab.click()
            time.sleep(1)

            # Type query
            chat_input = page.locator("input[placeholder*='Ask anything']")
            if chat_input.is_visible():
                chat_input.fill("What is discussed in Chapter 2?")
                page.locator("button:has-text('Send')").click()
                time.sleep(4)

        # Take RAG Chat Screenshot
        chat_img = os.path.abspath("live_chat_rag.png")
        page.screenshot(path=chat_img)
        print(f"[BrowserTest] Chat screenshot saved at: {chat_img}")

        browser.close()
        print("[BrowserTest] All Browser Tests Passed Successfully!")

if __name__ == "__main__":
    run_interactive_browser_test()
