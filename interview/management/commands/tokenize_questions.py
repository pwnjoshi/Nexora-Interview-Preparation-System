"""
Django management command to tokenize existing questions in the database.

This script updates the 'tokens' field for all questions that have keywords
but no pre-tokenized tokens. Uses the same tokenization logic from answer_evaluation.

Usage:
    python manage.py tokenize_questions [--force]
"""

from django.core.management.base import BaseCommand
from interview.models import Question
from interview.answer_evaluation import tokenize
import re


class Command(BaseCommand):
    help = 'Tokenize keywords for existing questions in database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Re-tokenize all questions, even if tokens already exist'
        )

    def handle(self, *args, **options):
        force = options['force']

        # Get questions that need tokenization
        if force:
            questions = Question.objects.all()
            self.stdout.write(f'Force mode: processing all {questions.count()} questions')
        else:
            questions = Question.objects.filter(tokens=[])
            self.stdout.write(f'Processing {questions.count()} questions without tokens')

        if not questions.exists():
            self.stdout.write(self.style.SUCCESS('No questions to process'))
            return

        updated_count = 0
        error_count = 0

        for q in questions:
            try:
                keywords = q.keywords if q.keywords else []
                
                if not keywords:
                    self.stdout.write(self.style.WARNING(
                        f'Skipping question "{q.question_text[:50]}..." - no keywords'
                    ))
                    continue

                # Tokenize all keywords
                tokens = []
                for kw in keywords:
                    if isinstance(kw, str) and kw.strip():
                        # Split phrases into words and tokenize
                        parts = [p.strip().lower() for p in re.split(r"[\s\-/]+", kw) if p.strip()]
                        tokens.extend(parts)
                
                # Remove duplicates while preserving order
                seen = set()
                unique_tokens = []
                for t in tokens:
                    if t not in seen:
                        seen.add(t)
                        unique_tokens.append(t)
                
                # Update question
                q.tokens = unique_tokens
                q.save()
                
                updated_count += 1
                self.stdout.write(
                    f'Tokenized: {q.question_text[:40]}... '
                    f'({len(keywords)} keywords → {len(unique_tokens)} tokens)'
                )

            except Exception as e:
                error_count += 1
                self.stdout.write(self.style.ERROR(
                    f'Error processing question "{q.question_text[:50]}...": {e}'
                ))

        # Summary
        self.stdout.write(self.style.SUCCESS(
            f'\nTokenization complete: {updated_count} updated, {error_count} errors'
        ))
