"""
Django management command to seed the database with dictionary data.

Imports dictionary data (Hebrew/Greek lexicons) from local JSON files.
JSON files are bundled in the Docker image at /app/data/dictionaries/

Features:
- Idempotent: Skips dictionaries where DB entry count matches JSON entry count
- Batch processing for memory efficiency
- Progress logging with timestamps

Usage:
    python manage.py seed_dictionary                           # Import all dictionaries
    python manage.py seed_dictionary --dictionaries BDBT       # Specific dictionary
    python manage.py seed_dictionary --json-dir /path/to/json  # Custom JSON directory
    python manage.py seed_dictionary --force                   # Re-import existing
"""
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from django.core.management.base import BaseCommand
from django.db import transaction
from bolls.models import Dictionary

# Default local JSON directory (bundled in Docker image at /app/data/)
DEFAULT_JSON_DIR = "/app/data/dictionaries"


def log_timestamp():
    """Return UTC timestamp for logging."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Command(BaseCommand):
    help = "Seed dictionary data from local JSON files"

    def add_arguments(self, parser):
        parser.add_argument(
            "--json-dir",
            type=str,
            default=DEFAULT_JSON_DIR,
            help=f"Directory containing dictionary JSON files (default: {DEFAULT_JSON_DIR})",
        )
        parser.add_argument(
            "--dictionaries",
            nargs="+",
            type=str,
            help="Specific dictionary codes to import (e.g., BDBT RUSD SCGES)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Re-import dictionaries even if they already exist",
        )

    def log(self, message, style=None):
        """Log with timestamp."""
        ts = log_timestamp()
        if style:
            self.stdout.write(style(f"[{ts}] {message}"))
        else:
            self.stdout.write(f"[{ts}] {message}")

    def handle(self, *args, **options):
        json_dir = Path(options["json_dir"])
        force = options["force"]
        requested = options.get("dictionaries")

        self.log("=" * 60)
        self.log("DICTIONARY SEEDING STARTED")
        self.log("=" * 60)
        start_time = time.time()

        if not json_dir.exists():
            self.log(f"Directory not found: {json_dir}", self.style.ERROR)
            return

        # Find all JSON files
        json_files = sorted(json_dir.glob("*.json"))
        if not json_files:
            self.log(f"No JSON files found in {json_dir}", self.style.ERROR)
            return

        # Filter if specific dictionaries requested
        if requested:
            json_files = [f for f in json_files if f.stem in requested]

        total = len(json_files)
        imported = 0
        skipped = 0

        self.log(f"Found {total} dictionary file(s) to process")

        for i, json_file in enumerate(json_files, 1):
            dict_code = json_file.stem
            result = self._import_dictionary(i, total, dict_code, json_file, force)
            if result == "imported":
                imported += 1
            elif result == "skipped":
                skipped += 1

        elapsed = time.time() - start_time
        self.log("=" * 60)
        self.log(
            f"DICTIONARY SEEDING COMPLETE: {imported} imported, {skipped} skipped, "
            f"{total - imported - skipped} failed ({elapsed:.1f}s)",
            self.style.SUCCESS
        )
        self.log("=" * 60)

    def _count_json_entries(self, json_path):
        """Count entries in JSON without loading full data."""
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return len(data) if isinstance(data, list) else 0
        except (json.JSONDecodeError, IOError):
            return 0

    def _import_dictionary(self, index, total, dict_code, json_file, force):
        """Import a single dictionary from JSON file."""
        # Get target count from JSON
        target_count = self._count_json_entries(json_file)
        if target_count == 0:
            self.log(f"[{index}/{total}] [{dict_code}] Empty or invalid JSON", self.style.ERROR)
            return "failed"

        # Check if already fully imported (idempotency check)
        existing = Dictionary.objects.filter(dictionary=dict_code).count()

        if existing == target_count and not force:
            self.log(
                f"[{index}/{total}] [{dict_code}] Already complete "
                f"({existing:,}/{target_count:,} entries). Skipping."
            )
            return "skipped"

        if existing > 0 and existing != target_count:
            self.log(
                f"[{index}/{total}] [{dict_code}] Partial data "
                f"({existing:,}/{target_count:,}). Re-importing..."
            )
            Dictionary.objects.filter(dictionary=dict_code).delete()
        elif existing > 0 and force:
            self.log(f"[{index}/{total}] [{dict_code}] Force re-import. Removing {existing:,} entries...")
            Dictionary.objects.filter(dictionary=dict_code).delete()

        # Load JSON and import
        self.log(f"[{index}/{total}] [{dict_code}] Importing {target_count:,} entries...")

        with open(json_file, "r", encoding="utf-8") as f:
            entries = json.load(f)

        # Create dictionary entries in bulk
        objects = []
        for entry in entries:
            objects.append(
                Dictionary(
                    dictionary=dict_code,
                    topic=entry.get("topic", ""),
                    definition=entry.get("definition", ""),
                    lexeme=entry.get("lexeme", ""),
                    transliteration=entry.get("transliteration", ""),
                    pronunciation=entry.get("pronunciation", ""),
                    short_definition=entry.get("short_definition", ""),
                )
            )

        # Bulk create with transaction
        with transaction.atomic():
            Dictionary.objects.bulk_create(objects, batch_size=500)

        self.log(
            f"[{index}/{total}] [{dict_code}] Imported {len(objects):,} entries",
            self.style.SUCCESS
        )
        return "imported"

