"""
Django management command to seed the database with Bible translations.

Imports Bible data from local JSON files (Bolls.life format).
JSON files are bundled in the Docker image at /app/data/translations/

Features:
- Idempotent: Skips translations where DB verse count matches JSON verse count
- Batch processing for memory efficiency
- Progress logging with timestamps

Usage:
    python manage.py seed_bible                           # Import all translations
    python manage.py seed_bible --translations ESV NIV    # Specific translations
    python manage.py seed_bible --json-dir /path/to/json  # Custom JSON directory
    python manage.py seed_bible --force                   # Re-import existing
"""
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from django.core.management.base import BaseCommand
from django.db import transaction
from bolls.models import Verses

# Default local JSON directory (bundled in Docker image at /app/data/)
DEFAULT_JSON_DIR = "/app/data/translations"


def log_timestamp():
    """Return UTC timestamp for logging."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Command(BaseCommand):
    help = "Seed the database with Bible translations from local JSON files"

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

    def log(self, message, style=None):
        """Log with timestamp."""
        ts = log_timestamp()
        if style:
            self.stdout.write(style(f"[{ts}] {message}"))
        else:
            self.stdout.write(f"[{ts}] {message}")

    def handle(self, *args, **options):
        force = options["force"]
        json_dir = Path(options["json_dir"])

        self.log("=" * 60)
        self.log("BIBLE SEEDING STARTED")
        self.log("=" * 60)
        start_time = time.time()

        # Auto-discover translations from JSON directory
        if options["translations"]:
            translations = options["translations"]
        elif json_dir.exists():
            translations = sorted([f.stem for f in json_dir.glob("*.json")])
            if translations:
                self.log(f"Found {len(translations)} JSON files in {json_dir}")
            else:
                self.log(f"No JSON files found in {json_dir}", self.style.ERROR)
                return
        else:
            self.log(f"JSON directory not found: {json_dir}", self.style.ERROR)
            return

        total = len(translations)
        imported = 0
        skipped = 0

        for idx, translation in enumerate(translations, 1):
            result = self.import_translation(translation, json_dir, force, idx, total)
            if result == "imported":
                imported += 1
            elif result == "skipped":
                skipped += 1

        elapsed = time.time() - start_time
        self.log("=" * 60)
        self.log(
            f"BIBLE SEEDING COMPLETE: {imported} imported, {skipped} skipped, "
            f"{total - imported - skipped} failed ({elapsed:.1f}s)",
            self.style.SUCCESS
        )
        self.log("=" * 60)

    def import_translation(self, translation, json_dir, force, current, total):
        """Import a single Bible translation from JSON."""
        json_path = json_dir / f"{translation}.json"

        if not json_path.exists():
            self.log(f"[{current}/{total}] {translation}: JSON file not found", self.style.ERROR)
            return "failed"

        # Get target count from JSON without loading full data into memory
        target_count = self._count_json_entries(json_path)
        if target_count == 0:
            self.log(f"[{current}/{total}] {translation}: Empty or invalid JSON", self.style.ERROR)
            return "failed"

        # Check if already fully imported (idempotency check)
        existing = Verses.objects.filter(translation=translation).count()

        if existing == target_count and not force:
            self.log(
                f"[{current}/{total}] {translation}: Already complete "
                f"({existing:,}/{target_count:,} verses). Skipping."
            )
            return "skipped"

        if existing > 0 and existing != target_count:
            self.log(
                f"[{current}/{total}] {translation}: Partial data "
                f"({existing:,}/{target_count:,}). Re-importing..."
            )
            Verses.objects.filter(translation=translation).delete()
        elif existing > 0 and force:
            self.log(f"[{current}/{total}] {translation}: Force re-import. Removing {existing:,} verses...")
            Verses.objects.filter(translation=translation).delete()

        # Parse and import
        self.log(f"[{current}/{total}] {translation}: Importing {target_count:,} verses...")
        verses_to_create = self._parse_json(translation, json_path)

        if not verses_to_create:
            self.log(f"[{current}/{total}] {translation}: No verses parsed", self.style.ERROR)
            return "failed"

        # Bulk create with smaller batch size for memory efficiency
        with transaction.atomic():
            Verses.objects.bulk_create(verses_to_create, batch_size=500)

        self.log(
            f"[{current}/{total}] {translation}: Imported {len(verses_to_create):,} verses",
            self.style.SUCCESS
        )
        return "imported"

    def _count_json_entries(self, json_path):
        """Count entries in JSON without loading full data."""
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return len(data) if isinstance(data, list) else 0
        except (json.JSONDecodeError, IOError):
            return 0

    def _parse_json(self, translation, json_path):
        """Parse Bolls.life JSON format."""
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
                ))
            except (ValueError, KeyError):
                pass

        return verses

