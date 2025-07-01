import pandas as pd
import matplotlib.pyplot as plt

# Load CSV
df = pd.read_csv("pdf_diff_summary.csv")

# Derived fields
df['filename_short'] = df['filename'].str.slice(0, 30) + "..."
df['total_changes'] = df['added'] + df['removed']
df['mod_add_ratio'] = df['modified'] / (df['added'] + 1)
top_20 = df.nlargest(20, 'total_changes')

# Setup single figure with 5 subplots
fig, axs = plt.subplots(3, 2, figsize=(18, 14))
fig.suptitle("PDF Fine-tuning Dataset Diff Overview", fontsize=16, fontweight='bold')
axs = axs.flatten()

# Plot 1: Total changes (bar chart, top 20)
axs[0].barh(top_20['filename_short'], top_20['total_changes'], color='skyblue')
axs[0].set_title("Top 20 Documents by Total Changes")
axs[0].set_xlabel("Total Changes (added + removed)")
axs[0].invert_yaxis()

# Plot 2: Stacked bar chart (added vs removed)
axs[1].barh(top_20['filename_short'], top_20['added'], label='Added', color='green')
axs[1].barh(top_20['filename_short'], top_20['removed'], left=top_20['added'], label='Removed', color='red')
axs[1].set_title("Added vs Removed Lines (Top 20 Docs)")
axs[1].set_xlabel("Line Changes")
axs[1].legend()
axs[1].invert_yaxis()

# Plot 3: Scatter of added vs removed
axs[2].scatter(df['added'], df['removed'], alpha=0.6)
axs[2].set_title("Removed vs Added")
axs[2].set_xlabel("Added Lines")
axs[2].set_ylabel("Removed Lines")
axs[2].grid(True)

# Plot 4: Histogram of total changes
axs[3].hist(df['total_changes'], bins=30, color='purple', edgecolor='black')
axs[3].set_title("Total Changes")
axs[3].set_xlabel("Total Changes")
axs[3].set_ylabel("Document Count")

# Plot 5: Histogram of modified-to-added ratio
axs[4].hist(df['mod_add_ratio'], bins=30, color='orange', edgecolor='black')
axs[4].set_title("Modified-to-Added Line Ratio")
axs[4].set_xlabel("Modified / (Added + 1)")
axs[4].set_ylabel("Document Count")

# Hide unused subplot if needed
if len(axs) > 5:
    axs[5].axis('off')

plt.tight_layout(rect=[0, 0.03, 1, 0.95])
plt.savefig("pdf_diff_overview.png", dpi=150)
plt.show()
