#!/usr/bin/env python3
"""
Download Bible translations from Bolls.life API and save as JSON files.

These files can be committed to the repo and used for seeding the database
without requiring network access during deployment.

Usage:
    python download_translations.py                    # Download all English
    python download_translations.py --translations ESV NIV NKJV
    python download_translations.py --all              # Download ALL translations
    python download_translations.py --list             # List available translations
"""

import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

# Bolls.life API endpoints
LANGUAGES_URL = "https://bolls.life/static/bolls/app/views/languages.json"
TRANSLATION_URL = "https://bolls.life/static/translations/{translation}.json"

# Output directory (relative to script location)
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data" / "translations"

# Default: All English translations from Bolls.life
ENGLISH_TRANSLATIONS = [
    "YLT", "CJB", "KJV", "NKJV", "WEB", "RSV", "TS2009", "LXXE", "TLV", "LSB",
    "NASB", "ESV", "GNV", "DRB", "NIV2011", "NIV", "NLT", "NRSVCE", "NET",
    "NJB1985", "SPE", "LBP", "AMP", "MSG", "LSV", "BSB", "MEV", "RSV2CE",
    "NABRE", "CSB17", "CEVD", "CEB", "AUV", "GNTD", "ERV", "ASV", "GNT", "ISV", "NLV"
]


def fetch_json(url: str) -> dict | list:
    """Fetch JSON from URL with error handling."""
    try:
        with urllib.request.urlopen(url, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as e:
        print(f"  Error fetching {url}: {e}", file=sys.stderr)
        return None


def get_all_translations() -> dict:
    """Fetch all available translations grouped by language."""
    print("Fetching translation list from Bolls.life...")
    languages = fetch_json(LANGUAGES_URL)
    if not languages:
        return {}
    
    result = {}
    for lang in languages:
        lang_name = lang.get("language", "Unknown")
        translations = lang.get("translations", [])
        result[lang_name] = [t.get("short_name") for t in translations]
    return result


def download_translation(code: str, output_dir: Path) -> bool:
    """Download a single translation and save as JSON."""
    output_file = output_dir / f"{code}.json"
    
    # Check if already exists
    if output_file.exists():
        size = output_file.stat().st_size
        print(f"  [{code}] Already exists ({size:,} bytes) - skipping")
        return True
    
    url = TRANSLATION_URL.format(translation=code)
    print(f"  [{code}] Downloading from {url}...")
    
    data = fetch_json(url)
    if not data:
        print(f"  [{code}] Failed to download", file=sys.stderr)
        return False
    
    # Save to file
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    
    verse_count = len(data) if isinstance(data, list) else 0
    file_size = output_file.stat().st_size
    print(f"  [{code}] Saved {verse_count:,} verses ({file_size:,} bytes)")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Download Bible translations from Bolls.life API"
    )
    parser.add_argument(
        "--translations", "-t", nargs="+",
        help="Specific translation codes to download (e.g., ESV NIV NKJV)"
    )
    parser.add_argument(
        "--all", "-a", action="store_true",
        help="Download ALL available translations"
    )
    parser.add_argument(
        "--english", "-e", action="store_true", default=True,
        help="Download all English translations (default)"
    )
    parser.add_argument(
        "--list", "-l", action="store_true",
        help="List all available translations and exit"
    )
    parser.add_argument(
        "--output", "-o", type=Path, default=DATA_DIR,
        help=f"Output directory (default: {DATA_DIR})"
    )
    parser.add_argument(
        "--force", "-f", action="store_true",
        help="Re-download even if file exists"
    )
    
    args = parser.parse_args()
    
    # List mode
    if args.list:
        all_trans = get_all_translations()
        for lang, codes in all_trans.items():
            print(f"\n{lang}:")
            print(f"  {', '.join(codes)}")
        total = sum(len(c) for c in all_trans.values())
        print(f"\nTotal: {total} translations")
        return
    
    # Determine which translations to download
    if args.translations:
        to_download = args.translations
    elif args.all:
        all_trans = get_all_translations()
        to_download = [code for codes in all_trans.values() for code in codes]
    else:
        to_download = ENGLISH_TRANSLATIONS
    
    print(f"Downloading {len(to_download)} translations to {args.output}")
    print("=" * 60)
    
    # Remove existing files if force
    if args.force:
        for code in to_download:
            f = args.output / f"{code}.json"
            if f.exists():
                f.unlink()
    
    success = 0
    failed = []
    for i, code in enumerate(to_download, 1):
        print(f"[{i}/{len(to_download)}]", end="")
        if download_translation(code, args.output):
            success += 1
        else:
            failed.append(code)
        time.sleep(0.5)  # Be nice to the server
    
    print("=" * 60)
    print(f"Complete: {success} downloaded, {len(failed)} failed")
    if failed:
        print(f"Failed: {', '.join(failed)}")


if __name__ == "__main__":
    main()

