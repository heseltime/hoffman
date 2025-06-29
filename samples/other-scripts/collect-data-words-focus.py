import os
import fitz  # PyMuPDF
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

def collect_word_metrics(pdf_dir):
    records = []

    for filename in os.listdir(pdf_dir):
        if filename.lower().endswith('.pdf'):
            filepath = os.path.join(pdf_dir, filename)
            try:
                with fitz.open(filepath) as doc:
                    num_pages = len(doc)
                    word_count = 0
                    for page in doc:
                        words = page.get_text("words")
                        word_count += len(words)

                    file_size_bytes = os.path.getsize(filepath)
                    file_size_kb = file_size_bytes / 1024
                    file_size_mb = file_size_bytes / (1024 * 1024)

                    words_per_page = word_count / num_pages if num_pages else 0
                    words_per_mb = word_count / file_size_mb if file_size_mb else 0
                    bytes_per_word = file_size_bytes / word_count if word_count else 0
                    text_density_ratio = file_size_mb / (word_count / 1000) if word_count else 0

                    records.append({
                        'filename': filename,
                        'num_pages': num_pages,
                        'word_count': word_count,
                        'file_size_bytes': file_size_bytes,
                        'file_size_kb': file_size_kb,
                        'file_size_mb': file_size_mb,
                        'words_per_page': words_per_page,
                        'words_per_mb': words_per_mb,
                        'bytes_per_word': bytes_per_word,
                        'text_density_ratio': text_density_ratio
                    })
            except Exception as e:
                print(f"Error processing {filename}: {e}")

    return pd.DataFrame(records)

# === MAIN ===
pdf_directory = '../../finetuning'
df = collect_word_metrics(pdf_directory)
df.to_csv('pdf_word_metrics.csv', index=False)

# === PLOTTING ===
# === Combined Plot ===
fig, axs = plt.subplots(3, 2, figsize=(16, 12))
fig.suptitle('PDF Word Metrics Overview', fontsize=16)

# Histogram: Word count
axs[0, 0].hist(df['word_count'], bins=20, edgecolor='black')
axs[0, 0].set_title('Distribution of Word Counts')
axs[0, 0].set_xlabel('Total Words')
axs[0, 0].set_ylabel('Documents')
axs[0, 0].grid(True, axis='y', linestyle='--')

# Histogram: Words per page
axs[0, 1].hist(df['words_per_page'], bins=20, edgecolor='black')
axs[0, 1].set_title('Words per Page Distribution')
axs[0, 1].set_xlabel('Words per Page')
axs[0, 1].set_ylabel('Documents')
axs[0, 1].grid(True, axis='y', linestyle='--')

# Scatter: Word count vs. number of pages
axs[1, 0].scatter(df['num_pages'], df['word_count'], alpha=0.7)
axs[1, 0].set_title('Word Count vs. Pages')
axs[1, 0].set_xlabel('Pages')
axs[1, 0].set_ylabel('Word Count')
axs[1, 0].grid(True, linestyle='--')

# Scatter: Word count vs. file size
axs[1, 1].scatter(df['file_size_mb'], df['word_count'], alpha=0.7)
axs[1, 1].set_title('Word Count vs. File Size (MB)')
axs[1, 1].set_xlabel('File Size (MB)')
axs[1, 1].set_ylabel('Word Count')
axs[1, 1].grid(True, linestyle='--')

# Histogram: Text density (MB per 1k words)
axs[2, 0].hist(df['text_density_ratio'], bins=20, edgecolor='black')
axs[2, 0].set_title('Text Density (MB per 1k Words)')
axs[2, 0].set_xlabel('MB per 1,000 Words')
axs[2, 0].set_ylabel('Documents')
axs[2, 0].grid(True, axis='y', linestyle='--')

# Optional: Clear the unused subplot
axs[2, 1].axis('off')  # Or display a summary/legend here

plt.tight_layout(rect=[0, 0, 1, 0.96])  # leave space for suptitle
plt.show()
