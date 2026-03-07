"""
Django management command to seed the database with Bible translations.

Supports two data sources:
1. Local JSON files (from Bolls.life format) - preferred
2. CSV files from scrollmapper/bible_databases - fallback

Usage:
    python manage.py seed_bible                           # Import from local JSON/CSV
    python manage.py seed_bible --translations ESV NIV    # Specific translations
    python manage.py seed_bible --json-dir /path/to/json  # Custom JSON directory
    python manage.py seed_bible --force                   # Re-import existing
"""
import csv
import json
import os
import urllib.request
from pathlib import Path
from django.core.management.base import BaseCommand
from django.db import transaction
from bolls.models import Verses

# Book name to ID mapping (for CSV import)
BOOK_MAP = {
    "Genesis": 1, "Exodus": 2, "Leviticus": 3, "Numbers": 4, "Deuteronomy": 5,
    "Joshua": 6, "Judges": 7, "Ruth": 8, "I Samuel": 9, "II Samuel": 10,
    "I Kings": 11, "II Kings": 12, "I Chronicles": 13, "II Chronicles": 14,
    "Ezra": 15, "Nehemiah": 16, "Esther": 17, "Job": 18, "Psalms": 19,
    "Proverbs": 20, "Ecclesiastes": 21, "Song of Solomon": 22, "Isaiah": 23,
    "Jeremiah": 24, "Lamentations": 25, "Ezekiel": 26, "Daniel": 27,
    "Hosea": 28, "Joel": 29, "Amos": 30, "Obadiah": 31, "Jonah": 32,
    "Micah": 33, "Nahum": 34, "Habakkuk": 35, "Zephaniah": 36, "Haggai": 37,
    "Zechariah": 38, "Malachi": 39, "Matthew": 40, "Mark": 41, "Luke": 42,
    "John": 43, "Acts": 44, "Romans": 45, "I Corinthians": 46, "II Corinthians": 47,
    "Galatians": 48, "Ephesians": 49, "Philippians": 50, "Colossians": 51,
    "I Thessalonians": 52, "II Thessalonians": 53, "I Timothy": 54, "II Timothy": 55,
    "Titus": 56, "Philemon": 57, "Hebrews": 58, "James": 59, "I Peter": 60,
    "II Peter": 61, "I John": 62, "II John": 63, "III John": 64, "Jude": 65,
    "Revelation": 66, "Revelation of John": 66,
}

# Fallback: scrollmapper CSV downloads
BIBLE_BASE_URL = "https://raw.githubusercontent.com/scrollmapper/bible_databases/master/formats/csv"
SCROLLMAPPER_TRANSLATIONS = ["ASV", "BSB", "ChiSB", "KJV", "TR", "WLC", "YLT"]

# Default local JSON directory (bundled in Docker image)
DEFAULT_JSON_DIR = "/app/data/translations"


class Command(BaseCommand):
    help = "Seed the database with Bible translations from local JSON or CSV files"

    def add_arguments(self, parser):
        parser.add_argument(
            "--translations",
            nargs="+",
            help="List of translation codes to import (default: all found in json-dir)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force re-import even if data exists",
        )
        parser.add_argument(
            "--json-dir",
            default=DEFAULT_JSON_DIR,
            help=f"Directory containing JSON files (default: {DEFAULT_JSON_DIR})",
        )
        parser.add_argument(
            "--csv-dir",
            default="/tmp/bible_data",
            help="Fallback directory for CSV files",
        )

    def handle(self, *args, **options):
        force = options["force"]
        json_dir = Path(options["json_dir"])
        csv_dir = options["csv_dir"]

        # Auto-discover translations from JSON directory if not specified
        if options["translations"]:
            translations = options["translations"]
        elif json_dir.exists():
            translations = [f.stem for f in json_dir.glob("*.json")]
            if translations:
                self.stdout.write(f"Found {len(translations)} JSON files in {json_dir}")
            else:
                translations = SCROLLMAPPER_TRANSLATIONS
                self.stdout.write(f"No JSON files found, using scrollmapper defaults")
        else:
            translations = SCROLLMAPPER_TRANSLATIONS
            self.stdout.write(f"JSON dir not found, using scrollmapper defaults")

        os.makedirs(csv_dir, exist_ok=True)

        for translation in sorted(translations):
            self.import_translation(translation, json_dir, csv_dir, force)

    def import_translation(self, translation, json_dir, csv_dir, force):
        """Import a single Bible translation from JSON or CSV."""
        # Check if already imported
        existing = Verses.objects.filter(translation=translation).count()
        if existing > 0 and not force:
            self.stdout.write(
                self.style.WARNING(f"[{translation}] Already has {existing} verses. Skipping.")
            )
            return

        if existing > 0 and force:
            self.stdout.write(f"[{translation}] Removing {existing} existing verses...")
            Verses.objects.filter(translation=translation).delete()

        # Try JSON first (Bolls.life format), then CSV (scrollmapper)
        json_path = json_dir / f"{translation}.json"
        csv_path = os.path.join(csv_dir, f"{translation}.csv")

        if json_path.exists():
            verses_to_create = self._parse_json(translation, json_path)
        elif os.path.exists(csv_path):
            verses_to_create = self._parse_csv(translation, csv_path)
        elif translation in SCROLLMAPPER_TRANSLATIONS:
            # Download CSV from scrollmapper
            url = f"{BIBLE_BASE_URL}/{translation}.csv"
            self.stdout.write(f"[{translation}] Downloading from scrollmapper...")
            urllib.request.urlretrieve(url, csv_path)
            verses_to_create = self._parse_csv(translation, csv_path)
        else:
            self.stdout.write(self.style.ERROR(f"[{translation}] No data file found"))
            return

        if not verses_to_create:
            self.stdout.write(self.style.ERROR(f"[{translation}] No verses parsed"))
            return

        # Bulk create
        with transaction.atomic():
            Verses.objects.bulk_create(verses_to_create, batch_size=1000)

        self.stdout.write(
            self.style.SUCCESS(f"[{translation}] Imported {len(verses_to_create)} verses")
        )

    def _parse_json(self, translation, json_path):
        """Parse Bolls.life JSON format."""
        self.stdout.write(f"[{translation}] Importing from JSON...")
        verses = []

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        for item in data:
            try:
                verses.append(Verses(
                    translation=translation,
                    book=item.get("book"),
                    chapter=item.get("chapter"),
                    verse=item.get("verse"),
                    text=item.get("text", "").strip(),
                    comment=item.get("comment", ""),
                ))
            except (ValueError, KeyError):
                pass

        return verses

    def _parse_csv(self, translation, csv_path):
        """Parse scrollmapper CSV format."""
        self.stdout.write(f"[{translation}] Importing from CSV...")
        verses = []

        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                book_name = row.get("Book", "").strip()
                book_id = BOOK_MAP.get(book_name)
                if not book_id:
                    continue

                try:
                    chapter = int(row.get("Chapter", 0))
                    verse_num = int(row.get("Verse", 0))
                    text = row.get("Text", "").strip()
                    # Clean up formatting tags
                    text = text.replace("<FI>", "").replace("<Fi>", "")
                    text = text.replace("<FR>", "").replace("<Fr>", "")

                    verses.append(Verses(
                        translation=translation,
                        book=book_id,
                        chapter=chapter,
                        verse=verse_num,
                        text=text,
                    ))
                except (ValueError, KeyError):
                    pass

        return verses

