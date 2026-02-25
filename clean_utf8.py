"""
clean_utf8.py — UTF-8 / Emoji Symbol Cleaner
=============================================
Recursively scans .html, .js, and .css files in the repository,
replaces corrupted UTF-8 / mojibake / emoji sequences with their
correct counterparts, and ensures every HTML file has a proper
<meta charset="UTF-8"> tag.

Replacement mappings are loaded from ``replacements.csv`` (same
directory as this script) which must have two columns:
  Corrupted   – the broken byte sequence as it appears in the file
  Replacement – the correct Unicode character(s) to substitute

Usage:
    python clean_utf8.py [root_dir]

If ``root_dir`` is omitted the script uses its own directory as the
root, so it is safe to run from anywhere.

The script is idempotent: running it more than once will not
introduce further changes once all corrupted sequences have been
replaced.
"""

import csv
import os
import re
import sys

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

TARGET_EXTENSIONS = {".html", ".js", ".css"}

# Regex that matches a <head> tag (with or without attributes).
_HEAD_RE = re.compile(r"(<head(?:\s[^>]*)?>)", re.IGNORECASE)

# Regex that detects an *existing* charset meta tag so we don't add a
# duplicate (matches both the legacy http-equiv form and the HTML5 form).
_CHARSET_META_RE = re.compile(
    r'<meta\s[^>]*charset\s*=\s*["\']?utf-8["\']?[^>]*>',
    re.IGNORECASE,
)

CHARSET_META_TAG = '<meta charset="UTF-8">'

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_replacements(csv_path: str) -> list[tuple[str, str]]:
    """Return a list of (corrupted, replacement) pairs from *csv_path*."""
    pairs: list[tuple[str, str]] = []
    if not os.path.isfile(csv_path):
        print(
            f"[WARN] replacements.csv not found at {csv_path!r}. "
            "No symbol replacements will be applied."
        )
        return pairs

    with open(csv_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            corrupted = row.get("Corrupted", "")
            replacement = row.get("Replacement", "")
            if corrupted:
                pairs.append((corrupted, replacement))

    print(f"[INFO] Loaded {len(pairs)} replacement rule(s) from {csv_path!r}")
    return pairs


def apply_replacements(content: str, pairs: list[tuple[str, str]]) -> tuple[str, list[str]]:
    """Apply all *pairs* to *content*.

    Returns the updated content and a list of descriptions for every
    substitution that was actually made.
    """
    fixed: list[str] = []
    for corrupted, replacement in pairs:
        if corrupted in content:
            count = content.count(corrupted)
            content = content.replace(corrupted, replacement)
            fixed.append(
                f"  {corrupted!r} → {replacement!r}  ({count} occurrence(s))"
            )
    return content, fixed


def ensure_charset_meta(content: str) -> tuple[str, bool]:
    """Inject ``<meta charset="UTF-8">`` right after ``<head>`` if absent.

    Returns the (possibly updated) content and a boolean indicating
    whether the tag was inserted.
    """
    if _CHARSET_META_RE.search(content):
        return content, False

    match = _HEAD_RE.search(content)
    if not match:
        return content, False

    insert_pos = match.end()
    content = content[:insert_pos] + "\n  " + CHARSET_META_TAG + content[insert_pos:]
    return content, True


# ---------------------------------------------------------------------------
# Main scanning logic
# ---------------------------------------------------------------------------


def scan_and_fix(root: str, pairs: list[tuple[str, str]]) -> None:
    """Walk *root* recursively and fix every targeted file."""
    files_scanned = 0
    files_modified = 0

    for dirpath, _dirnames, filenames in os.walk(root):
        # Skip hidden directories (e.g. .git)
        _dirnames[:] = [d for d in _dirnames if not d.startswith(".")]

        for filename in sorted(filenames):
            ext = os.path.splitext(filename)[1].lower()
            if ext not in TARGET_EXTENSIONS:
                continue

            filepath = os.path.join(dirpath, filename)
            files_scanned += 1
            print(f"[SCAN] {filepath}")

            try:
                with open(filepath, "r", encoding="utf-8") as fh:
                    original = fh.read()
            except UnicodeDecodeError:
                print(f"[WARN] {filepath!r} contains bytes that are not valid UTF-8; "
                      "re-reading with replacement characters.")
                with open(filepath, "r", encoding="utf-8", errors="replace") as fh:
                    original = fh.read()
            except OSError as exc:
                print(f"[ERROR] Cannot read {filepath!r}: {exc}")
                continue

            content = original
            symbol_fixes: list[str] = []

            # 1. Apply symbol replacements
            content, symbol_fixes = apply_replacements(content, pairs)

            # 2. For HTML files, ensure charset meta tag
            charset_added = False
            if ext == ".html":
                content, charset_added = ensure_charset_meta(content)

            # 3. Write back only when something actually changed
            if content != original:
                try:
                    with open(filepath, "w", encoding="utf-8") as fh:
                        fh.write(content)
                except OSError as exc:
                    print(f"[ERROR] Cannot write {filepath!r}: {exc}")
                    continue

                files_modified += 1
                print(f"[FIXED] {filepath}")
                for line in symbol_fixes:
                    print(line)
                if charset_added:
                    print(f'  Added {CHARSET_META_TAG!r} to <head>')
            else:
                print(f"[OK]    {filepath}  (no changes needed)")

    print()
    print(f"=== Summary ===")
    print(f"Files scanned : {files_scanned}")
    print(f"Files modified: {files_modified}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    script_dir = os.path.dirname(os.path.abspath(__file__))

    root = sys.argv[1] if len(sys.argv) > 1 else script_dir
    root = os.path.abspath(root)

    csv_path = os.path.join(script_dir, "replacements.csv")

    print(f"[INFO] Root directory : {root!r}")
    print(f"[INFO] Replacements CSV: {csv_path!r}")
    print(f"[INFO] Target extensions: {', '.join(sorted(TARGET_EXTENSIONS))}")
    print()

    pairs = load_replacements(csv_path)
    scan_and_fix(root, pairs)


if __name__ == "__main__":
    main()
