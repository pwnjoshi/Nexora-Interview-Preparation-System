from django.core.management.base import BaseCommand
from interview.models import Profile
from django.contrib.auth.models import User
from django.db import connection


class Command(BaseCommand):
    help = 'Clean up duplicate Profile records, keeping only the most recent one per user'

    def handle(self, *args, **options):
        # Get MongoDB collection directly
        from pymongo import MongoClient
        from django.conf import settings
        
        # Connect to MongoDB
        db_settings = settings.DATABASES['default']
        client = MongoClient(db_settings.get('CLIENT', {}).get('host', 'localhost'))
        db_name = db_settings['NAME']
        db = client[db_name]
        profiles_collection = db['interview_profile']
        
        self.stdout.write(f"Connected to MongoDB database: {db_name}")
        
        # Get all users
        users = User.objects.all()
        total_deleted = 0
        
        for user in users:
            # Find all profiles for this user in MongoDB
            user_profiles = list(profiles_collection.find({'user_id': user.id}).sort('created_at', -1))
            
            if len(user_profiles) > 1:
                # Keep the most recent one
                keep_id = user_profiles[0]['_id']
                self.stdout.write(f"\nUser: {user.username}")
                self.stdout.write(f"  Total profiles: {len(user_profiles)}")
                self.stdout.write(f"  Keeping profile with _id: {keep_id}")
                
                # Delete all others
                delete_ids = [p['_id'] for p in user_profiles[1:]]
                result = profiles_collection.delete_many({'_id': {'$in': delete_ids}})
                deleted_count = result.deleted_count
                total_deleted += deleted_count
                
                self.stdout.write(self.style.SUCCESS(f"  Deleted {deleted_count} duplicate profiles"))
        
        self.stdout.write(self.style.SUCCESS(f"\n✓ Cleanup complete! Total deleted: {total_deleted}"))
        client.close()
