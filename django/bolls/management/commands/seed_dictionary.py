"""
Django management command to seed the database with dictionary data.

Imports dictionary data (Hebrew/Greek lexicons) from local JSON files.
JSON files are bundled in the Docker image at /app/data/dictionaries/

Usage:
    python manage.py seed_dictionary                           # Import all dictionaries
    python manage.py seed_dictionary --dictionaries BDBT       # Specific dictionary
    python manage.py seed_dictionary --json-dir /path/to/json  # Custom JSON directory
    python manage.py seed_dictionary --force                   # Re-import existing
"""
import json
from pathlib import Path
from django.core.management.base import BaseCommand
from django.db import transaction
from bolls.models import Dictionary

# Default local JSON directory (bundled in Docker image)
DEFAULT_JSON_DIR = "/app/data/dictionaries"


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

    def handle(self, *args, **options):
        json_dir = Path(options["json_dir"])
        force = options["force"]
        requested = options.get("dictionaries")

        if not json_dir.exists():
            self.stderr.write(self.style.ERROR(f"Directory not found: {json_dir}"))
            return

        # Find all JSON files
        json_files = sorted(json_dir.glob("*.json"))
        if not json_files:
            self.stderr.write(self.style.ERROR(f"No JSON files found in {json_dir}"))
            return

        # Filter if specific dictionaries requested
        if requested:
            json_files = [f for f in json_files if f.stem in requested]

        total = len(json_files)
        self.stdout.write(f"Found {total} dictionary file(s) to process")

        for i, json_file in enumerate(json_files, 1):
            dict_code = json_file.stem
            self._import_dictionary(i, total, dict_code, json_file, force)

        self.stdout.write(self.style.SUCCESS("Dictionary seeding complete!"))

    def _import_dictionary(self, index, total, dict_code, json_file, force):
        """Import a single dictionary from JSON file."""
        # Check if already imported
        existing = Dictionary.objects.filter(dictionary=dict_code).count()
        if existing > 0 and not force:
            self.stdout.write(
                f"[{index}/{total}] [{dict_code}] Already exists ({existing:,} entries) - skipping"
            )
            return

        self.stdout.write(f"[{index}/{total}] [{dict_code}] Importing...")

        # Delete existing if force
        if existing > 0:
            Dictionary.objects.filter(dictionary=dict_code).delete()
            self.stdout.write(f"  Deleted {existing:,} existing entries")

        # Load JSON
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
            Dictionary.objects.bulk_create(objects, batch_size=1000)

        self.stdout.write(
            self.style.SUCCESS(f"[{index}/{total}] [{dict_code}] Imported {len(objects):,} entries")
        )

