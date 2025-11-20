"""
Django management command to import questions from JSON with pre-tokenized keywords.

Usage:
    python manage.py import_questions <json_file_path> [--clear]

Expected JSON format:
[
    {
        "question": "What is Machine Learning?",
        "level": "beginner",
        "answer": {
            "keywords": ["machine learning", "algorithms", "data", "patterns"],
            "tokens": ["machine", "learning", "algorithms", "data", "patterns"],  # Optional
            "text": "Machine Learning is..."  # Optional reference answer
        }
    },
    ...
]
"""

import json
import re
from django.core.management.base import BaseCommand, CommandError
from interview.models import Question


class Command(BaseCommand):
    help = 'Import questions from JSON file with pre-tokenized keywords'

    def tokenize_keywords(self, keywords):
        """Convert keywords to pre-tokenized format"""
        tokens = []
        for kw in keywords:
            # Split phrases into individual words
            parts = [p.strip().lower() for p in re.split(r"[\s\-/]+", kw) if p.strip()]
            tokens.extend(parts)
        # Remove duplicates while preserving order
        seen = set()
        unique_tokens = []
        for t in tokens:
            if t not in seen:
                seen.add(t)
                unique_tokens.append(t)
        return unique_tokens

    def add_arguments(self, parser):
        parser.add_argument(
            'json_file',
            type=str,
            help='Path to JSON file containing questions'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing questions before importing'
        )

    def handle(self, *args, **options):
        json_file = options['json_file']
        clear_existing = options['clear']

        # Validate file exists
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except FileNotFoundError:
            raise CommandError(f'File not found: {json_file}')
        except json.JSONDecodeError as e:
            raise CommandError(f'Invalid JSON: {e}')

        if not isinstance(data, list):
            raise CommandError('JSON must contain a list of questions')

        # Clear existing questions if requested
        if clear_existing:
            count = Question.objects.count()
            Question.objects.all().delete()
            self.stdout.write(self.style.WARNING(f'Cleared {count} existing questions'))

        # Import questions
        created_count = 0
        updated_count = 0
        skipped_count = 0

        for idx, item in enumerate(data, 1):
            try:
                # Extract fields
                question_text = item.get('question', '').strip()
                level = item.get('level', 'beginner').lower()
                answer_obj = item.get('answer', {})

                if not question_text:
                    self.stdout.write(self.style.WARNING(f'Skipping item {idx}: missing question text'))
                    skipped_count += 1
                    continue

                # Extract keywords and tokens
                if isinstance(answer_obj, dict):
                    keywords = answer_obj.get('keywords', [])
                    tokens = answer_obj.get('tokens', [])
                    reference_answer = answer_obj.get('text', '')  # optional reference answer
                else:
                    # Fallback if answer is just a list of keywords
                    keywords = answer_obj if isinstance(answer_obj, list) else []
                    tokens = []
                    reference_answer = ''

                # Validate data types
                if not isinstance(keywords, list):
                    self.stdout.write(self.style.WARNING(f'Skipping item {idx}: keywords must be a list'))
                    skipped_count += 1
                    continue

                if tokens and not isinstance(tokens, list):
                    self.stdout.write(self.style.WARNING(f'Skipping item {idx}: tokens must be a list'))
                    skipped_count += 1
                    continue
                
                # Auto-generate tokens if missing
                if not tokens and keywords:
                    tokens = self.tokenize_keywords(keywords)

                # Normalize level
                valid_levels = ['beginner', 'intermediate', 'hard']
                if level not in valid_levels:
                    self.stdout.write(self.style.WARNING(
                        f'Item {idx}: invalid level "{level}", defaulting to "beginner"'
                    ))
                    level = 'beginner'

                # Check if question already exists
                existing = Question.objects.filter(question_text=question_text).first()

                if existing:
                    # Update existing question
                    existing.keywords = keywords
                    existing.tokens = tokens if tokens else []
                    existing.level = level
                    if reference_answer:
                        existing.answer = reference_answer
                    existing.save()
                    updated_count += 1
                    self.stdout.write(f'Updated: {question_text[:50]}...')
                else:
                    # Create new question
                    Question.objects.create(
                        question_text=question_text,
                        keywords=keywords,
                        tokens=tokens if tokens else [],
                        level=level,
                        answer=reference_answer or ''
                    )
                    created_count += 1
                    self.stdout.write(f'Created: {question_text[:50]}...')

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error processing item {idx}: {e}'))
                skipped_count += 1
                continue

        # Summary
        self.stdout.write(self.style.SUCCESS(
            f'\nImport complete: {created_count} created, {updated_count} updated, {skipped_count} skipped'
        ))
