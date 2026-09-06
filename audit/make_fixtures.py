import os
import sys

# Ensure repository root is on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
os.makedirs(FIXTURES_DIR, exist_ok=True)

# Planted canary tokens for deterministic container auditing
CANARIES = {
    "docx": [
        "CANARY_DOCX_PARAGRAPH_ALPHA",
        "CANARY_DOCX_PARAGRAPH_BETA",
        "CANARY_DOCX_TABLE_METRIC_ROW1",
        "CANARY_DOCX_TABLE_METRIC_ROW2",
        "CANARY_DOCX_HEADER_SEC1",
        "CANARY_DOCX_FOOTER_SEC1",
        "CANARY_DOCX_TEXTBOX_CALLOUT"
    ],
    "pptx": [
        "CANARY_PPTX_SLIDE1_HEADING",
        "CANARY_PPTX_SLIDE1_BODY",
        "CANARY_PPTX_SLIDE1_TABLE_CELL",
        "CANARY_PPTX_SPEAKER_NOTES_SLIDE1"
    ],
    "xlsx": [
        "CANARY_XLSX_SHEET1_HEADER",
        "CANARY_XLSX_SHEET1_ROW_DATA",
        "CANARY_XLSX_SHEET2_ROW_DATA"
    ],
    "pdf": [
        "CANARY_PDF_PAGE1_HEADER",
        "CANARY_PDF_PAGE1_BODY",
        "CANARY_PDF_PAGE2_TABLE_ROW"
    ]
}


def make_docx_fixture():
    import docx
    from docx.oxml import parse_xml
    from docx.oxml.ns import nsdecls

    path = os.path.join(FIXTURES_DIR, "canary_test.docx")
    doc = docx.Document()

    # 1. Section Header & Footer
    section = doc.sections[0]
    header = section.header
    header.paragraphs[0].text = "Official Report | CANARY_DOCX_HEADER_SEC1"
    footer = section.footer
    footer.paragraphs[0].text = "Internal Use Only | CANARY_DOCX_FOOTER_SEC1"

    # 2. Body Paragraphs
    doc.add_heading("System Architecture Document", level=1)
    doc.add_paragraph("This is the main introduction with CANARY_DOCX_PARAGRAPH_ALPHA.")
    doc.add_paragraph("Technical specifications continue here with CANARY_DOCX_PARAGRAPH_BETA.")

    # 3. Table with Metric Rows
    table = doc.add_table(rows=3, cols=3)
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = "Component"
    hdr_cells[1].text = "Metric"
    hdr_cells[2].text = "Value"

    r1_cells = table.rows[1].cells
    r1_cells[0].text = "Database"
    r1_cells[1].text = "Throughput"
    r1_cells[2].text = "CANARY_DOCX_TABLE_METRIC_ROW1"

    r2_cells = table.rows[2].cells
    r2_cells[0].text = "Cache"
    r2_cells[1].text = "Latency"
    r2_cells[2].text = "CANARY_DOCX_TABLE_METRIC_ROW2"

    # 4. Text Box / Shape (WXML element)
    p = doc.add_paragraph()
    txbx_xml = f"""
    <w:p {nsdecls('w')}>
      <w:r>
        <w:drawing>
          <w:txbxContent>
            <w:p>
              <w:r>
                <w:t>Architecture Callout Note: CANARY_DOCX_TEXTBOX_CALLOUT</w:t>
              </w:r>
            </w:p>
          </w:txbxContent>
        </w:drawing>
      </w:r>
    </w:p>
    """
    try:
        element = parse_xml(txbx_xml)
        doc._body._element.append(element)
    except Exception:
        # Fallback to direct paragraph with marker
        doc.add_paragraph("Callout Text: CANARY_DOCX_TEXTBOX_CALLOUT")

    doc.save(path)
    print(f"[Fixture Built] DOCX: {path}")
    return path


def make_pptx_fixture():
    from pptx import Presentation
    from pptx.util import Inches

    path = os.path.join(FIXTURES_DIR, "canary_test.pptx")
    prs = Presentation()

    # Slide 1
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank
    # Title shape
    txBox = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(5), Inches(1))
    tf = txBox.text_frame
    tf.text = "Quarterly Review CANARY_PPTX_SLIDE1_HEADING"

    # Body shape
    txBox2 = slide.shapes.add_textbox(Inches(1), Inches(2), Inches(5), Inches(2))
    tf2 = txBox2.text_frame
    tf2.text = "Performance Highlights CANARY_PPTX_SLIDE1_BODY"

    # Table
    table_shape = slide.shapes.add_table(2, 2, Inches(1), Inches(4), Inches(4), Inches(1))
    table = table_shape.table
    table.cell(0, 0).text = "Metric"
    table.cell(0, 1).text = "Score"
    table.cell(1, 0).text = "Retention"
    table.cell(1, 1).text = "CANARY_PPTX_SLIDE1_TABLE_CELL"

    # Speaker Notes
    notes_slide = slide.notes_slide
    notes_text_frame = notes_slide.notes_text_frame
    notes_text_frame.text = "Confidential presenter guidance: CANARY_PPTX_SPEAKER_NOTES_SLIDE1"

    prs.save(path)
    print(f"[Fixture Built] PPTX: {path}")
    return path


def make_xlsx_fixture():
    import pandas as pd

    path = os.path.join(FIXTURES_DIR, "canary_test.xlsx")
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df1 = pd.DataFrame({
            "CANARY_XLSX_SHEET1_HEADER": ["Value_Alpha", "Value_Beta"],
            "Amount": [100, 200],
            "Details": ["First row info", "Row with CANARY_XLSX_SHEET1_ROW_DATA"]
        })
        df1.to_excel(writer, sheet_name="FinancialSummary", index=False)

        df2 = pd.DataFrame({
            "Department": ["Engineering", "Product"],
            "Headcount": [45, 12],
            "Notes": ["Active roadmap", "CANARY_XLSX_SHEET2_ROW_DATA"]
        })
        df2.to_excel(writer, sheet_name="HeadcountPlan", index=False)

    print(f"[Fixture Built] XLSX: {path}")
    return path


def make_pdf_fixture():
    import fitz

    path = os.path.join(FIXTURES_DIR, "canary_test.pdf")
    doc = fitz.open()

    # Page 1
    page1 = doc.new_page(width=595, height=842)
    page1.insert_text((50, 72), "Document Intelligence Manual - CANARY_PDF_PAGE1_HEADER", fontsize=16)
    page1.insert_text((50, 120), "Section 1: Architectural principles and CANARY_PDF_PAGE1_BODY overview.", fontsize=11)

    # Page 2
    page2 = doc.new_page(width=595, height=842)
    page2.insert_text((50, 72), "Section 2: Engineering Tabular Data", fontsize=14)
    page2.insert_text((50, 120), "Table 1.1 Transformer Ratings: Row A | Voltage 33kV | CANARY_PDF_PAGE2_TABLE_ROW", fontsize=11)

    doc.save(path)
    doc.close()
    print(f"[Fixture Built] PDF: {path}")
    return path


def build_all():
    print("Generating synthetic fixtures with planted canary tokens...")
    make_docx_fixture()
    make_pptx_fixture()
    make_xlsx_fixture()
    make_pdf_fixture()
    print("All fixtures generated successfully.")


if __name__ == "__main__":
    build_all()
