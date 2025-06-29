import os
import fitz  # PyMuPDF
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

def collect_pdf_metrics(pdf_dir):
    records = []

    for filename in os.listdir(pdf_dir):
        if filename.lower().endswith('.pdf'):
            filepath = os.path.join(pdf_dir, filename)
            try:
                with fitz.open(filepath) as doc:
                    num_pages = len(doc)
                    text = ""
                    for page in doc:
                        text += page.get_text()
                    text_length = len(text)
                    file_size_bytes = os.path.getsize(filepath)
                    file_size_kb = file_size_bytes / 1024
                    file_size_mb = file_size_bytes / (1024 * 1024)

                    records.append({
                        'filename': filename,
                        'num_pages': num_pages,
                        'text_length': text_length,
                        'file_size_bytes': file_size_bytes,
                        'file_size_kb': file_size_kb,
                        'file_size_mb': file_size_mb
                    })
            except Exception as e:
                print(f"Error processing {filename}: {e}")

    return pd.DataFrame(records)

# === MAIN ===
pdf_directory = '../../finetuning'
df = collect_pdf_metrics(pdf_directory)

# Save results (optional)
df.to_csv('pdf_metrics.csv', index=False)

# === PLOTTING ===
# === Combined Plot ===
fig, axs = plt.subplots(2, 2, figsize=(14, 10))
fig.suptitle('PDF Metrics Overview', fontsize=16)

# 1. Histogram: Number of Pages
max_pages = df['num_pages'].max()
bins = np.arange(0, max_pages + 2) - 0.5
axs[0, 0].hist(df['num_pages'], bins=bins, edgecolor='black')
step = max(1, max_pages // 20)
axs[0, 0].set_xticks(np.arange(0, max_pages + 1, step))
axs[0, 0].set_title('Number of Pages')
axs[0, 0].set_xlabel('Pages')
axs[0, 0].set_ylabel('Documents')
axs[0, 0].grid(True, axis='y', linestyle='--')

# 2. Histogram: File Size (MB)
axs[0, 1].hist(df['file_size_mb'], bins=20, edgecolor='black')
axs[0, 1].set_title('File Size (MB)')
axs[0, 1].set_xlabel('File Size')
axs[0, 1].set_ylabel('Documents')
axs[0, 1].grid(True, axis='y', linestyle='--')

# 3. Scatter: Pages vs. Text Length
axs[1, 0].scatter(df['num_pages'], df['text_length'], alpha=0.7)
axs[1, 0].set_title('Text Length vs. Pages')
axs[1, 0].set_xlabel('Pages')
axs[1, 0].set_ylabel('Characters')
axs[1, 0].grid(True, linestyle='--')

# 4. Scatter: Pages vs. File Size
axs[1, 1].scatter(df['num_pages'], df['file_size_mb'], alpha=0.7)
axs[1, 1].set_title('File Size vs. Pages')
axs[1, 1].set_xlabel('Pages')
axs[1, 1].set_ylabel('Size (MB)')
axs[1, 1].grid(True, linestyle='--')

plt.tight_layout(rect=[0, 0, 1, 0.96])  # leave space for suptitle
plt.show()
