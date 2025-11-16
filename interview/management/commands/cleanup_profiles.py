from django.core.management.base import BaseCommand
from interview.models import Profile
from django.contrib.auth.models import User

class Command(BaseCommand):
    help = 'Clean up ObjectId-based Profile records, merging into int-pk Profile and deleting duplicates.'

    def handle(self, *args, **options):
        users = User.objects.all()
        total_merged = 0
        total_deleted = 0
        for user in users:
            profiles = list(Profile.objects.filter(user=user).order_by('-created_at'))
            if not profiles:
                continue
            int_profiles = [p for p in profiles if isinstance(p.pk, int)]
            if int_profiles:
                primary = int_profiles[0]
            else:
                primary = Profile.objects.create(
                    user=user,
                    unique_user_id=f"U{user.id}",
                    name=user.username,
                    email=user.email or "",
                )
            merged = primary.preferences if isinstance(primary.preferences, dict) else {}
            for extra in profiles:
                if extra is primary:
                    continue
                if isinstance(extra.preferences, dict):
                    for k, v in extra.preferences.items():
                        if k not in merged:
                            merged[k] = v
                # delete only safe duplicates (ObjectId pk or int pk distinct from primary)
                if extra.pk != primary.pk and extra.pk is not None:
                    extra.delete()
                    total_deleted += 1
            primary.preferences = merged
            try:
                if isinstance(primary.pk, int):
                    primary.save()
                    total_merged += 1
            except Exception:
                pass
        self.stdout.write(self.style.SUCCESS(f"Cleanup complete. Merged: {total_merged}, Deleted: {total_deleted}"))
