import zlib

# --- Step 1: LLM output (uncompressed PDF content stream) ---
pdf_text = """
BT
/F1 16 Tf
72 770 Td
(Accessibility in PDFs) Tj
ET

BT
/F1 12 Tf
72 740 Td
(Accessibility in PDF documents ensures that all users, including those using screen readers, can access content.) Tj
ET

BT
/F1 16 Tf
72 700 Td
(Common Issues) Tj
ET

BT
/F1 12 Tf
72 670 Td
(Many PDFs lack semantic tags, proper reading order, or alt text for images.) Tj
ET
""".strip()

# --- Step 2: Compress the content stream ---
compressed_stream = zlib.compress(pdf_text.encode('utf-8'))

# --- Step 3: Create a minimal PDF structure with the compressed stream ---

output_pdf = f"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842]
   /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>
endobj
4 0 obj
<< /Length {len(compressed_stream)} /Filter /FlateDecode >>
stream
""".encode('utf-8') + compressed_stream + b"""
endstream
endobj
5 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
xref
0 6
0000000000 65535 f
0000000010 00000 n
0000000061 00000 n
0000000124 00000 n
0000000272 00000 n
""" + f"{272 + len(compressed_stream):010} 00000 n\n".encode('utf-8') + b"""trailer
<< /Size 6 /Root 1 0 R >>
startxref
""" + f"{272 + len(compressed_stream) + 55}".encode('utf-8') + b"""
%%EOF
"""

# --- Step 4: Write to file ---
with open("output.pdf", "wb") as f:
    f.write(output_pdf)

print("✅ PDF generated as output.pdf")
