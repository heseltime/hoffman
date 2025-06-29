import os
import fitz  # PyMuPDF
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# Define the folder where your PDFs are stored
pdf_directory = '../../finetuning'  # Adjust to actual location

# Collect metrics for document pairs
records = []

for filename in os.listdir(pdf_directory):
    if filename.endswith('.pdf') and not filename.endswith(' bf.pdf'):
        base_name = filename[:-4]
        bf_name = f"{base_name} bf.pdf"

        original_path = os.path.join(pdf_directory, filename)
        bf_path = os.path.join(pdf_directory, bf_name)

        if not os.path.exists(bf_path):
            continue  # Skip if corresponding bf version not found

        def extract_metrics(path):
            with fitz.open(path) as doc:
                num_pages = len(doc)
                text = ""
                word_count = 0
                for page in doc:
                    text += page.get_text()
                    word_count += len(page.get_text("words"))
                char_count = len(text)
            file_size = os.path.getsize(path)
            return {
                'num_pages': num_pages,
                'word_count': word_count,
                'char_count': char_count,
                'file_size_bytes': file_size,
                'file_size_mb': file_size / (1024 * 1024)
            }

        original = extract_metrics(original_path)
        bf = extract_metrics(bf_path)

        records.append({
            'filename_base': base_name,
            'orig_pages': original['num_pages'],
            'bf_pages': bf['num_pages'],
            'orig_words': original['word_count'],
            'bf_words': bf['word_count'],
            'orig_chars': original['char_count'],
            'bf_chars': bf['char_count'],
            'orig_size': original['file_size_mb'],
            'bf_size': bf['file_size_mb'],
            'words_diff': bf['word_count'] - original['word_count'],
            'chars_diff': bf['char_count'] - original['char_count'],
            'pages_diff': bf['num_pages'] - original['num_pages'],
            'size_diff': bf['file_size_mb'] - original['file_size_mb'],
            'words_per_page_diff': (bf['word_count']/bf['num_pages'] if bf['num_pages'] else 0) -
                                   (original['word_count']/original['num_pages'] if original['num_pages'] else 0),
            'words_per_mb_diff': (bf['word_count']/bf['file_size_mb'] if bf['file_size_mb'] else 0) -
                                 (original['word_count']/original['file_size_mb'] if original['file_size_mb'] else 0)
        })

df = pd.DataFrame(records)

# Plot all differences in a grid
fig, axs = plt.subplots(3, 2, figsize=(14, 12))
fig.suptitle('Differences Between Original and Accessible PDF Versions', fontsize=16)

axs[0, 0].hist(df['words_diff'], bins=20, edgecolor='black')
axs[0, 0].set_title('Word Count Difference (BF - Original)')
axs[0, 0].set_xlabel('Words')
axs[0, 0].set_ylabel('Document Pairs')

axs[0, 1].hist(df['chars_diff'], bins=20, edgecolor='black')
axs[0, 1].set_title('Character Count Difference')
axs[0, 1].set_xlabel('Characters')
axs[0, 1].set_ylabel('Document Pairs')

axs[1, 0].hist(df['pages_diff'], bins=15, edgecolor='black')
axs[1, 0].set_title('Page Count Difference')
axs[1, 0].set_xlabel('Pages')
axs[1, 0].set_ylabel('Document Pairs')

axs[1, 1].hist(df['size_diff'], bins=20, edgecolor='black')
axs[1, 1].set_title('File Size Difference (MB)')
axs[1, 1].set_xlabel('MB')
axs[1, 1].set_ylabel('Document Pairs')

axs[2, 0].hist(df['words_per_page_diff'], bins=20, edgecolor='black')
axs[2, 0].set_title('Words per Page Difference')
axs[2, 0].set_xlabel('Δ Words/Page')
axs[2, 0].set_ylabel('Document Pairs')

axs[2, 1].hist(df['words_per_mb_diff'], bins=20, edgecolor='black')
axs[2, 1].set_title('Words per MB Difference')
axs[2, 1].set_xlabel('Δ Words/MB')
axs[2, 1].set_ylabel('Document Pairs')

plt.tight_layout(rect=[0, 0, 1, 0.96])
plt.show()

# Save the collected metrics to a CSV file
output_csv_path = 'pdf_pair_differences.csv'
df.to_csv(output_csv_path, index=False)

output_csv_path