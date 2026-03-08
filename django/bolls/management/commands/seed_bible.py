"""
Django management command to seed the database with Bible translations.

Imports Bible data from local JSON files (Bolls.life format).
JSON files are bundled in the Docker image at /app/data/translations/

Usage:
    python manage.py seed_bible                           # Import all translations
    python manage.py seed_bible --translations ESV NIV    # Specific translations
    python manage.py seed_bible --json-dir /path/to/json  # Custom JSON directory
    python manage.py seed_bible --force                   # Re-import existing
"""
import json
from pathlib import Path
from django.core.management.base import BaseCommand
from django.db import transaction
from bolls.models import Verses

# Default local JSON directory (bundled in Docker image)
DEFAULT_JSON_DIR = "/app/data/translations"


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

    def handle(self, *args, **options):
        force = options["force"]
        json_dir = Path(options["json_dir"])

        # Auto-discover translations from JSON directory
        if options["translations"]:
            translations = options["translations"]
        elif json_dir.exists():
            translations = sorted([f.stem for f in json_dir.glob("*.json")])
            if translations:
                self.stdout.write(f"Found {len(translations)} JSON files in {json_dir}")
            else:
                self.stdout.write(self.style.ERROR(f"No JSON files found in {json_dir}"))
                return
        else:
            self.stdout.write(self.style.ERROR(f"JSON directory not found: {json_dir}"))
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

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Seeding complete: {imported} imported, {skipped} skipped, {total - imported - skipped} failed"
        ))

    def import_translation(self, translation, json_dir, force, current, total):
        """Import a single Bible translation from JSON."""
        json_path = json_dir / f"{translation}.json"

        if not json_path.exists():
            self.stdout.write(self.style.ERROR(
                f"[{current}/{total}] {translation}: JSON file not found"
            ))
            return "failed"

        # Check if already imported
        existing = Verses.objects.filter(translation=translation).count()
        if existing > 0 and not force:
            self.stdout.write(self.style.WARNING(
                f"[{current}/{total}] {translation}: Already has {existing} verses. Skipping."
            ))
            return "skipped"

        if existing > 0 and force:
            self.stdout.write(f"[{current}/{total}] {translation}: Removing {existing} existing verses...")
            Verses.objects.filter(translation=translation).delete()

        # Parse and import
        self.stdout.write(f"[{current}/{total}] {translation}: Importing...")
        verses_to_create = self._parse_json(translation, json_path)

        if not verses_to_create:
            self.stdout.write(self.style.ERROR(
                f"[{current}/{total}] {translation}: No verses parsed"
            ))
            return "failed"

        # Bulk create
        with transaction.atomic():
            Verses.objects.bulk_create(verses_to_create, batch_size=1000)

        self.stdout.write(self.style.SUCCESS(
            f"[{current}/{total}] {translation}: Imported {len(verses_to_create)} verses"
        ))
        return "imported"

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

