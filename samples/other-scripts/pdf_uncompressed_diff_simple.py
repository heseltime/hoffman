import sys
import subprocess
import difflib
from pathlib import Path

def uncompress_pdf(input_pdf_path: Path, output_pdf_path: Path):
    print(f"[+] Uncompressing: {input_pdf_path.name}")
    subprocess.run([
        'qpdf', '--qdf', '--object-streams=disable',
        str(input_pdf_path), str(output_pdf_path)
    ], check=True)
    print(f"[✓] Saved uncompressed file to: {output_pdf_path.name}")

def read_file_lines(path):
    with open(path, 'r', encoding='latin1') as f:
        return f.readlines()

def filter_streams(lines):
    """Remove content between 'stream' and 'endstream' to clean up binary data."""
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

def write_diff_to_file(diff_lines, output_path):
    print(f"[+] Writing diff to: {output_path.name}")
    with open(output_path, 'w', encoding='utf-8') as f:
        for line in diff_lines:
            print(line, end='')  # Console output
            f.write(line)
    print(f"[✓] Diff complete.\n")

def main():
    if len(sys.argv) != 2:
        print("Usage: python pdf_uncompressed_diff_simple.py <original.pdf>")
        sys.exit(1)

    original_path = Path(sys.argv[1])
    if not original_path.exists():
        print(f"[!] Error: File '{original_path}' does not exist.")
        sys.exit(1)

    name_stem = original_path.stem
    suffix = original_path.suffix
    bf_path = original_path.with_name(f"{name_stem} bf{suffix}")

    if not bf_path.exists():
        print(f"[!] Error: Expected second file '{bf_path}' does not exist.")
        sys.exit(1)

    print(f"\n[~] Comparing:")
    print(f"   Original: {original_path.name}")
    print(f"   Modified: {bf_path.name}")

    uncompressed1 = original_path.with_name(f"{name_stem}_uncompressed.pdf")
    uncompressed2 = original_path.with_name(f"{name_stem}_bf_uncompressed.pdf")

    uncompress_pdf(original_path, uncompressed1)
    uncompress_pdf(bf_path, uncompressed2)

    lines1 = filter_streams(read_file_lines(uncompressed1))
    lines2 = filter_streams(read_file_lines(uncompressed2))

    diff_lines = list(difflib.unified_diff(
        lines1, lines2,
        fromfile=original_path.name,
        tofile=bf_path.name
    ))

    diff_file = original_path.with_name(f"{name_stem}__vs__{name_stem}_bf.diff.txt")
    write_diff_to_file(diff_lines, diff_file)

if __name__ == "__main__":
    main()
