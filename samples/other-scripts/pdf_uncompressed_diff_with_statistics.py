import difflib
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import subprocess

def uncompress_pdf(input_path: Path, output_path: Path):
    print(f"[+] Uncompressing: {input_path.name}")
    result = subprocess.run([
        'qpdf', '--qdf', '--object-streams=disable',
        str(input_path), str(output_path)
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    if result.returncode != 0:
        print(f"[!] qpdf failed on {input_path.name}")
        print(result.stderr.decode())
        return False
    else:
        print(f"[✓] Uncompressed: {output_path.name}")
        return True

def read_lines(path):
    with open(path, 'r', encoding='latin1') as f:
        return f.readlines()

def filter_streams(lines):
    """Remove binary stream content to clean up diffs."""
    filtered = []
    in_stream = False
    for line in lines:
        stripped = line.strip()
        if stripped == 'stream':
            in_stream = True
            filtered.append('<<STREAM OMITTED>>\n')
        elif stripped == 'endstream':
            in_stream = False
        elif not in_stream:
            filtered.append(line)
    return filtered

def analyze_diff(lines1, lines2):
    diff = list(difflib.unified_diff(lines1, lines2, lineterm=''))
    total_lines = max(len(lines1), len(lines2)) or 1
    stats = {'added': 0, 'removed': 0, 'modified': 0, 'positions': []}

    for i, line in enumerate(diff):
        if line.startswith('+') and not line.startswith('+++'):
            stats['added'] += 1
            stats['positions'].append(i / total_lines)
        elif line.startswith('-') and not line.startswith('---'):
            stats['removed'] += 1
            stats['positions'].append(i / total_lines)

    stats['modified'] = min(stats['added'], stats['removed'])  # crude estimate
    return stats

def plot_diff_positions(relative_positions, filename, output_dir):
    plt.figure(figsize=(10, 2))
    plt.hist(relative_positions, bins=50, range=(0, 1), color='black')
    plt.title(f"Change distribution in {filename}")
    plt.xlabel("Relative Position in File")
    plt.ylabel("Change Count")
    plot_path = output_dir / f"plot_{filename}.png"
    plt.tight_layout()
    plt.savefig(plot_path)
    plt.close()
    return plot_path.name

def process_all_pdf_pairs(base_dir: Path, output_csv: Path, plot_output_dir: Path):
    data = []
    plot_output_dir.mkdir(exist_ok=True)
    
    for original_pdf in base_dir.glob("*.pdf"):
        if " bf" in original_pdf.stem:
            continue

        bf_pdf = original_pdf.with_name(original_pdf.stem + " bf" + original_pdf.suffix)
        if not bf_pdf.exists():
            continue
        
        uncompressed1 = original_pdf.with_name(original_pdf.stem + "_uncompressed.pdf")
        uncompressed2 = bf_pdf.with_name(original_pdf.stem + "_bf_uncompressed.pdf")

        success1 = uncompress_pdf(original_pdf, uncompressed1)
        success2 = uncompress_pdf(bf_pdf, uncompressed2)
        if not (success1 and success2):
            print(f"[!] Skipping pair: {original_pdf.name}")
            continue

        lines1 = filter_streams(read_lines(uncompressed1))
        lines2 = filter_streams(read_lines(uncompressed2))

        stats = analyze_diff(lines1, lines2)
        plot_name = plot_diff_positions(stats['positions'], original_pdf.stem, plot_output_dir)

        data.append({
            'filename': original_pdf.stem,
            'added': stats['added'],
            'removed': stats['removed'],
            'modified': stats['modified'],
            'change_density_plot': plot_name
        })

    df = pd.DataFrame(data)
    df.to_csv(output_csv, index=False)
    return df

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Compare PDF pairs in a directory and summarize diffs.")
    parser.add_argument("directory", type=str, help="Path to the directory containing PDF pairs")
    args = parser.parse_args()

    base_directory = Path(args.directory).resolve()
    if not base_directory.exists() or not base_directory.is_dir():
        print(f"[ERROR] '{base_directory}' is not a valid directory.")
        exit(1)

    csv_output = base_directory / "pdf_diff_summary.csv"
    plots_dir = base_directory / "diff_plots"

    df_result = process_all_pdf_pairs(base_directory, csv_output, plots_dir)
    print(f"\n[✓] Summary saved to: {csv_output}")
    print(df_result)
