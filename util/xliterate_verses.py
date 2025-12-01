"""
transliterate .yml files in an input directory.

For each .yml file (non-recursive):
- call do_xliterate_file(input_lang, output_lang, in_file_path, out_file_path)

No type annotations, no logging.

uses aksharamukha for transliteration
https://github.com/virtualvinodh/aksharamukha-python
"""


import argparse
import tempfile
import os
from pathlib import Path
import shutil
import re
import sys

from aksharamukha import transliterate_file

# Build language-specific options
# Lang (script actually) identifiers and options: https://www.aksharamukha.com/documentation
# Option "indicDandas" is not documented: found it in source code
def get_post_options(output_lang):
    """
    Return a list of post_options strings for aksharamukha based on output_lang.

    Rules:
    - If output_lang == 'Devanagari', include 'DevanagariAnusvara'
    - Otherwise include 'indicDandas'
    - If output_lang == 'IAST', also include 'AnusvaratoNasalASTISO'
    """
    options = []
    if output_lang == "Devanagari":
        options.append("DevanagariAnusvara")
    else:
        options.append("indicDandas")

    if output_lang == "IAST":
        options.append("AnusvaratoNasalASTISO")

    return options


# Maintain a dictionary of options, one entry (options array) per lang
_post_options_cache = {}
def get_cached_post_options(output_lang):
    """
    Return post options for output_lang, computing them once and caching the result.
    """
    if output_lang not in _post_options_cache:
        _post_options_cache[output_lang] = get_post_options(output_lang)
    return _post_options_cache[output_lang]


def _fix_devanagari_keys_in_yaml_file(yml_path):
    """
    Replace trailing '।5' with '.5' in YAML keys that end with '।5',
    operating on the given file in-place and using UTF-8 encoding.

    This reads and writes with newline="" so existing line endings are preserved.
    Returns the number of replacements made.
    """
    yml_path = Path(yml_path)
    try:
        with yml_path.open("r", encoding="utf-8", newline="") as fh:
            text = fh.read()
    except Exception as exc:
        print(f"Could not read {yml_path} for Devanagari key fix: {exc}", file=sys.stderr)
        return 0

    # Pattern: start of line, capture indentation, capture key body (non-greedy, not including colon or newline),
    # then the Devanagari danda + '5' sequence, followed by optional spaces and a colon.
    pattern = r"^(\s*)([^:\n]*?)।5(?=\s*:)"
    repl = r"\1\2.5"

    new_text, count = re.subn(pattern, repl, text, flags=re.MULTILINE)
    if count > 0:
        try:
            with yml_path.open("w", encoding="utf-8", newline="") as fh:
                fh.write(new_text)
            print(f"Replaced {count} key suffix(es) '।5' -> '.5' in {yml_path}")
        except Exception as exc:
            print(f"Failed to write fixes to {yml_path}: {exc}", file=sys.stderr)
            return 0

    return count


def _fix_iast_dandas_in_yaml_file(yml_path):
    """
    Replace ASCII pipe sequences used as danda markers while preserving YAML block headers.

    Replacements (performed on non-header lines):
    - " ||" -> " ॥"
    - " |"  -> " ।"

    The function skips lines that are YAML block scalar headers (e.g., "1: |-", "chapter: |").
    Operates in-place using UTF-8 and preserves existing line endings.
    Returns the total number of replacements made.
    """
    yml_path = Path(yml_path)
    try:
        with yml_path.open("r", encoding="utf-8", newline="") as fh:
            lines = fh.readlines()
    except Exception as exc:
        print(f"Could not read {yml_path} for IAST danda fix: {exc}", file=sys.stderr)
        return 0

    out_lines = []
    total = 0

    for line in lines:
        # Skip YAML block scalar headers like "key: |", "key: |-", "key: |+"
        if line.rstrip().endswith((': |', ': |-', ': |+')):
            out_lines.append(line)
            continue

        # Count double-bar occurrences first; single-bar count should exclude those
        count_double = line.count(" ||")
        count_single = line.count(" |") - count_double
        total += (count_double + max(0, count_single))

        # Replace double-bar first, then single-bar
        new_line = line.replace(" ||", " ॥").replace(" |", " ।")
        out_lines.append(new_line)

    if total > 0:
        try:
            with yml_path.open("w", encoding="utf-8", newline="") as fh:
                fh.writelines(out_lines)
            print(f"Replaced {total} IAST danda marker(s) in {yml_path}")
        except Exception as exc:
            print(f"Failed to write IAST fixes to {yml_path}: {exc}", file=sys.stderr)
            return 0

    return total


def do_xliterate_file(input_lang, output_lang, in_file_path, out_file_path, temp_dir):
    """
    Parameters:
    - input_lang: source language code or name
    - output_lang: target language code or name
    - in_file_path: path to the original .yml file
    - out_file_path: path to the result .yml file
    - temp_dir: path to dir to create intermediate files

    Behavior:
    - copy in_file_path to temp_dir/am_convert.txt (overwrite)
    - remove any existing intermediate output file am_convert_<input><output>.txt before calling aksharamukha
    - call aksharamukha to process the intermediate file with post_options from get_cached_post_options
    - early return if the expected intermediate output file does not appear
    - if the intermediate output exists and is non-empty:
        - if output_lang == 'Devanagari', apply key-fix to the intermediate result (UTF-8)
        - copy the intermediate result to out_file_path
    """
    in_path = Path(in_file_path)
    out_path = Path(out_file_path)
    temp_dir = Path(temp_dir)

    # Intermediate paths inside temp dir
    intermediate_txt_in = temp_dir / "am_convert.txt"
    ilol_name = f"am_convert_{input_lang}{output_lang}.txt"
    intermediate_txt_out = temp_dir / ilol_name

    # Copy input file into temp dir as am_convert.txt
    try:
        shutil.copyfile(in_path, intermediate_txt_in)
        print(f"Copied {in_path} -> {intermediate_txt_in}")
    except Exception as exc:
        print(f"Failed to copy {in_path} to {intermediate_txt_in}: {exc}", file=sys.stderr)
        return

    # Remove any existing intermediate output in the temp dir (defensive)
    if intermediate_txt_out.exists():
        try:
            intermediate_txt_out.unlink()
            print(f"Removed existing intermediate output {intermediate_txt_out}")
        except Exception as exc:
            print(f"Could not remove existing intermediate output {intermediate_txt_out}: {exc}", file=sys.stderr)

    # Run transliteration with cwd set to the temp dir
    post_opts = get_cached_post_options(output_lang)
    old_cwd = Path.cwd()
    try:
        os.chdir(temp_dir)
        transliterate_file.process(input_lang, output_lang, str(intermediate_txt_in), post_options=post_opts)
    finally:
        os.chdir(old_cwd)

    # Early return if the transliteration did not produce the expected intermediate output
    if not intermediate_txt_out.exists():
        print(f"No intermediate output produced: {intermediate_txt_out}; skipping {out_path}")
        return

    # Skip empty output
    try:
        size = intermediate_txt_out.stat().st_size
    except Exception as exc:
        print(f"Could not stat {intermediate_txt_out}: {exc}", file=sys.stderr)
        return

    if size == 0:
        print(f"Found {intermediate_txt_out} but it is empty (0 bytes); not copying to {out_path}")
        return

    # Clean the intermediate result
    # - Devanagari: fix yaml keys for second part of verses
    # - IAST: fix ASCII pipe danda markers
    if output_lang == "Devanagari":
        _fix_devanagari_keys_in_yaml_file(intermediate_txt_out)
    elif output_lang == "IAST":
        _fix_iast_dandas_in_yaml_file(intermediate_txt_out)


    # Ensure destination directory exists
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Move the intermediate result into the output directory
    try:
        shutil.move(str(intermediate_txt_out), str(out_path))
        print(f"Moved {intermediate_txt_out} -> {out_path}")
    except Exception as exc:
        print(f"Failed to move {intermediate_txt_out} to {out_path}: {exc}", file=sys.stderr)
        return


def do_xliterate_dir(input_lang, output_lang, input_dir, output_dir):
    input_path = Path(input_dir)
    output_path = Path(output_dir)

    if not input_path.is_dir():
        print(f"Error: input path is not a directory: {input_path}", file=sys.stderr)
        return

    if not output_path.is_dir():
        print(f"Error: output path is not a directory: {output_path}", file=sys.stderr)
        return

    yml_files = sorted(input_path.glob("v*.yml"))
    if not yml_files:
        print(f"No .yml files found in {input_path}")
        return

    # Create one temporary directory for the entire run
    with tempfile.TemporaryDirectory() as td:
        temp_dir = Path(td)
        print(f"Using temporary directory {temp_dir} for intermediate files")

        for yml_file in yml_files:
            try:
                size = yml_file.stat().st_size
            except Exception as exc:
                print(f"Could not stat {yml_file}: {exc}", file=sys.stderr)
                continue

            if size == 0:
                print(f"Skipping empty input file {yml_file} (0 bytes)")
                continue

            try:
                out_file_path = output_path / yml_file.name
                do_xliterate_file(input_lang, output_lang, str(yml_file), str(out_file_path), temp_dir)
            except Exception as exc:
                print(f"Failed to process {yml_file}: {exc}", file=sys.stderr)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Process .yml files and call do_xliterate_file."
    )
    parser.add_argument("input_lang", help="Input language identifier (e.g., en)")
    parser.add_argument("output_lang", help="Output language identifier (e.g., hi)")
    parser.add_argument("input_dir", help="Path to the input directory containing .yml files")
    parser.add_argument("output_dir", help="Path to the output directory (created if missing)")
    return parser.parse_args()


def main():
    args = parse_args()
    do_xliterate_dir(args.input_lang, args.output_lang, args.input_dir, args.output_dir)


if __name__ == "__main__":
    main()
