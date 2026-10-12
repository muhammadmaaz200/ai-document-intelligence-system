
import io
import json
import re
from datetime import datetime

import fitz
import pandas as pd
import pytesseract
import streamlit as st
from PIL import Image


# --------------------------------------------------
# Page Configuration
# --------------------------------------------------

st.set_page_config(
    page_title="AI Document Intelligence",
    page_icon="📄",
    layout="wide"
)

st.title("📄 AI Document Intelligence System")
st.caption(
    "Upload an invoice, receipt, or document to extract "
    "text and key fields."
)

st.sidebar.info(
    "Portfolio demo: OCR, document classification, "
    "and structured data extraction."
)

st.sidebar.warning(
    "Do not upload confidential documents to a public demo."
)


# --------------------------------------------------
# Helper Function: Regex Matching
# --------------------------------------------------

def match(patterns, text):
    for pattern in patterns:
        result = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)

        if result:
            return result.group(1).strip(" :#\\\t")

    return ""


# --------------------------------------------------
# Extract Information from Document Text
# --------------------------------------------------

def extract_fields(text):

    # Invoice or receipt number
    number = match([
        r"(?:invoice|receipt)\s*(?:number|no\.?|#|id)"
        r"\s*[:#\-]?\s*([A-Z0-9][A-Z0-9/-]{1,})"
    ], text)

    # Date
    date = match([
        r"(?:invoice\s*)?date\s*[:\-]?\s*"
        r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",

        r"(?:invoice\s*)?date\s*[:\-]?\s*"
        r"(\d{4}[/-]\d{1,2}[/-]\d{1,2})",

        r"\b(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})\b"
    ], text)

    # Total amount
    total = match([
        r"(?:grand\s+total|total\s+due|amount\s+due|"
        r"total|balance\s+due)\s*[:\-]?\s*"
        r"(?:PKR|Rs\.?|USD|\$)?\s*"
        r"([0-9,]+(?:\.\d{2})?)",

        r"(?:PKR|Rs\.?)\s*([0-9,]+(?:\.\d{2})?)"
    ], text)

    # Vendor name or first meaningful line
    vendor = ""

    for line in text.splitlines():
        line = re.sub(r"\s+", " ", line).strip()

        if (
            len(line) > 2
            and re.search(r"[A-Za-z]", line)
            and not re.search(
                r"invoice|receipt|date|total|bill to|"
                r"ship to|phone|email",
                line,
                re.IGNORECASE
            )
        ):
            vendor = line[:100]
            break

    # Document classification
    lower_text = text.lower()

    if any(word in lower_text for word in [
        "invoice", "amount due", "bill to", "subtotal"
    ]):
        document_type = "Invoice"

    elif any(word in lower_text for word in [
        "receipt", "cashier", "change due", "payment received"
    ]):
        document_type = "Receipt"

    elif "purchase order" in lower_text:
        document_type = "Purchase Order"

    else:
        document_type = "General Document"

    return {
        "document_type": document_type,
        "vendor_or_first_line": vendor,
        "invoice_or_receipt_number": number,
        "date": date,
        "total_amount": total
    }


# --------------------------------------------------
# Read PDF and Apply OCR When Needed
# --------------------------------------------------

def read_pdf(data):

    document = fitz.open(stream=data, filetype="pdf")

    extracted_pages = []
    used_ocr = False

    try:
        for page in document:

            page_text = page.get_text("text").strip()

            # Use OCR for scanned pages or pages without text
            if len(page_text) < 20:

                pixmap = page.get_pixmap(
                    matrix=fitz.Matrix(2, 2),
                    alpha=False
                )

                image_bytes = pixmap.tobytes("png")

                page_image = Image.open(
                    io.BytesIO(image_bytes)
                ).convert("RGB")

                page_text = pytesseract.image_to_string(page_image)
                used_ocr = True

            extracted_pages.append(page_text)

    finally:
        document.close()

    return "\n\n".join(extracted_pages), used_ocr


# --------------------------------------------------
# Upload Document
# --------------------------------------------------

uploaded_file = st.file_uploader(
    "Choose a PDF, PNG, JPG, or JPEG",
    type=["pdf", "png", "jpg", "jpeg"]
)

if uploaded_file:

    raw_data = uploaded_file.getvalue()

    st.write(
        f"**File:** {uploaded_file.name} · "
        f"**Size:** {len(raw_data) / 1024:.1f} KB"
    )

    if len(raw_data) > 12 * 1024 * 1024:
        st.error("Please upload a file smaller than 12 MB.")
        st.stop()

    if st.button("Process document", type="primary"):

        try:
            with st.spinner("Processing document..."):

                # Extract text from PDF or image
                if uploaded_file.name.lower().endswith(".pdf"):

                    extracted_text, used_ocr = read_pdf(raw_data)

                else:

                    uploaded_image = Image.open(
                        io.BytesIO(raw_data)
                    ).convert("RGB")

                    extracted_text = pytesseract.image_to_string(
                        uploaded_image
                    )

                    used_ocr = True

                # Extract structured fields
                fields = extract_fields(extracted_text)

                record = {
                    "filename": uploaded_file.name,
                    "processed_at": datetime.now().strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                    **fields
                }

                # Save current result in session
                st.session_state["result"] = {
                    "text": extracted_text,
                    "fields": fields,
                    "record": record,
                    "ocr": used_ocr
                }

                # Update temporary session history
                old_history = st.session_state.get("history", [])

                st.session_state["history"] = (
                    [record]
                    + [
                        item for item in old_history
                        if item["filename"] != uploaded_file.name
                    ]
                )

        except Exception as error:

            st.error(
                "Could not process the file. "
                "Make sure it is a valid PDF/image and OCR is installed."
            )

            st.caption(f"Technical detail: {error}")


# --------------------------------------------------
# Display Extraction Results
# --------------------------------------------------

result = st.session_state.get("result")

if result:

    st.divider()
    st.subheader("Extraction Results")

    if result["ocr"]:
        st.success("OCR used to extract document text.")
    else:
        st.success("Digital PDF text extracted directly.")

    fields = result["fields"]

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Document Type",
        fields["document_type"]
    )

    col2.metric(
        "Date",
        fields["date"] or "Not detected"
    )

    col3.metric(
        "Total Amount",
        fields["total_amount"] or "Not detected"
    )

    st.markdown("### Extracted Fields")

    st.dataframe(
        pd.DataFrame([fields]),
        use_container_width=True,
        hide_index=True
    )

    # Extracted text
    with st.expander("View Extracted Text", expanded=True):

        st.text_area(
            "Document text",
            result["text"] or "No text detected.",
            height=240
        )

    # JSON download
    json_data = json.dumps(
        {
            "fields": fields,
            "text": result["text"]
        },
        indent=2,
        ensure_ascii=False
    ).encode("utf-8")

    st.download_button(
        "Download JSON",
        data=json_data,
        file_name="extracted_document.json",
        mime="application/json"
    )

    # CSV download
    csv_data = pd.DataFrame(
        [result["record"]]
    ).to_csv(index=False).encode("utf-8-sig")

    st.download_button(
        "Download CSV",
        data=csv_data,
        file_name="extracted_fields.csv",
        mime="text/csv"
    )

    # Excel download
    excel_buffer = io.BytesIO()

    with pd.ExcelWriter(
        excel_buffer,
        engine="openpyxl"
    ) as writer:

        pd.DataFrame(
            [result["record"]]
        ).to_excel(
            writer,
            index=False,
            sheet_name="Extracted Data"
        )

    st.download_button(
        "Download Excel",
        data=excel_buffer.getvalue(),
        file_name="extracted_fields.xlsx",
        mime=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        )
    )


# --------------------------------------------------
# Session History
# --------------------------------------------------

history = st.session_state.get("history", [])

if history:

    st.divider()
    st.subheader("Session History")

    st.caption(
        "Temporary history only. It is not saved permanently "
        "and may be lost when the session resets."
    )

    st.dataframe(
        pd.DataFrame(history),
        use_container_width=True,
        hide_index=True
    )

    if st.button("Clear history"):

        st.session_state["history"] = []
        st.session_state.pop("result", None)

        st.rerun()


# --------------------------------------------------
# Footer
# --------------------------------------------------

st.divider()

st.caption(
    "Prototype: OCR and extracted fields may be inaccurate. "
    "Always verify extracted information manually."
)
