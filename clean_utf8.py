"""
clean_utf8.py — UTF-8 / Emoji Symbol Cleaner
=============================================
Recursively scans .html, .js, and .css files in the repository,
replaces corrupted UTF-8 / mojibake / emoji sequences with their
correct counterparts, strips UTF-8 BOMs, and ensures every HTML
file has a proper <meta charset="UTF-8"> tag.

Two-pass replacement strategy:
  1. Algorithmic auto-detection: scans for sequences of characters
     whose CP1252/Latin-1 byte values form a valid UTF-8 sequence
     for a single Unicode code point and replaces them automatically.
     This handles box-drawing chars (─ ═ ━), emoji, math symbols, etc.
     without requiring manual CSV entries.
  2. CSV-driven replacement: applies explicit (Corrupted, Replacement)
     pairs from ``replacements.csv`` as a belt-and-suspenders fallback.

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

# The Unicode BOM character that some editors prepend to UTF-8 files.
UTF8_BOM = "\ufeff"

# ---------------------------------------------------------------------------
# Algorithmic mojibake auto-detection
# ---------------------------------------------------------------------------


def _char_to_byte(c: str):
    """Return the single Latin-1/CP1252 byte value for *c*, or None."""
    try:
        return c.encode("latin-1")[0]
    except UnicodeEncodeError:
        try:
            return c.encode("cp1252")[0]
        except (UnicodeEncodeError, UnicodeDecodeError):
            return None


def fix_mojibake_auto(content: str) -> tuple:
    """Fix CP1252-re-encoded UTF-8 (mojibake) algorithmically.

    Scans for sequences of characters whose CP1252/Latin-1 byte values
    form a valid 2-4 byte UTF-8 sequence for exactly one Unicode code
    point, and replaces each such sequence with the correct character.

    Returns ``(fixed_content, count)`` where *count* is the number of
    sequences that were replaced.
    """
    result: list = []
    count = 0
    i = 0
    n = len(content)

    while i < n:
        c = content[i]
        lead = _char_to_byte(c)

        # Only attempt decode when the byte value looks like the start
        # of a multi-byte UTF-8 sequence (0xC0..0xFF).
        if lead is not None and lead >= 0xC0:
            replaced = False
            # Try longest match first (4 input chars → 4-byte UTF-8 → 1 emoji)
            for length in (4, 3, 2):
                if i + length > n:
                    continue
                seq = content[i : i + length]
                raw = bytearray()
                ok = True
                for ch in seq:
                    bval = _char_to_byte(ch)
                    if bval is None:
                        ok = False
                        break
                    raw.append(bval)
                if not ok:
                    continue
                try:
                    decoded = raw.decode("utf-8")
                    if len(decoded) == 1:          # exactly one Unicode char
                        result.append(decoded)
                        count += 1
                        i += length
                        replaced = True
                        break
                except UnicodeDecodeError:
                    pass
            if not replaced:
                result.append(c)
                i += 1
        else:
            result.append(c)
            i += 1

    return "".join(result), count

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

            # 1. Strip UTF-8 BOM if present
            bom_stripped = False
            if content.startswith(UTF8_BOM):
                content = content[len(UTF8_BOM):]
                bom_stripped = True

            # 1a. Algorithmic mojibake auto-detection (CP1252 re-encoding)
            content, auto_count = fix_mojibake_auto(content)
            if auto_count:
                symbol_fixes.append(
                    f"  Auto-fixed {auto_count} mojibake sequence(s) algorithmically"
                )

            # 2. Apply symbol replacements
            content, symbol_fixes = apply_replacements(content, pairs)

            # 3. For HTML files, ensure charset meta tag
            charset_added = False
            if ext == ".html":
                content, charset_added = ensure_charset_meta(content)

            # 4. Write back only when something actually changed
            if content != original:
                try:
                    with open(filepath, "w", encoding="utf-8") as fh:
                        fh.write(content)
                except OSError as exc:
                    print(f"[ERROR] Cannot write {filepath!r}: {exc}")
                    continue

                files_modified += 1
                print(f"[FIXED] {filepath}")
                if bom_stripped:
                    print(f"  Stripped UTF-8 BOM")
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
