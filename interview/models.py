# interview/models.py

from djongo import models
from django.contrib.auth.models import User

#  Feedback Model
class Feedback(models.Model):
    RATING_CHOICES = [
        (1, '1 - Poor'),
        (2, '2 - Fair'),
        (3, '3 - Good'),
        (4, '4 - Very Good'),
        (5, '5 - Excellent'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=100, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    rating = models.IntegerField(choices=RATING_CHOICES)
    category = models.CharField(max_length=50, choices=[
        ('feature', 'Feature Request'),
        ('bug', 'Bug Report'),
        ('general', 'General Feedback'),
        ('improvement', 'Suggestion'),
    ], default='general')
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        user_name = self.user.username if self.user else self.name or 'Anonymous'
        return f"{user_name} - {self.rating} stars - {self.created_at.strftime('%Y-%m-%d')}"
    
    class Meta:
        verbose_name = "Feedback"
        verbose_name_plural = "Feedbacks"
        ordering = ['-created_at']


#  Resume Storage Model
class Resume(models.Model):
    username = models.CharField(max_length=100)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    skills = models.JSONField(default=list)
    skill_categories = models.JSONField(default=dict)
    experience = models.TextField(blank=True, null=True)
    education = models.TextField(blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.username}'s Resume"
    
    class Meta:
        verbose_name = "Resume"
        verbose_name_plural = "Resumes"
        ordering = ['-uploaded_at']


#  Question Storage Model
class Question(models.Model):
    keywords = models.JSONField(default=list)  # list of raw keywords/phrases
    tokens = models.JSONField(default=list)  # pre-tokenized keywords (lowercase, no stopwords)
    level = models.CharField(max_length=50, default="beginner")
    question_text = models.TextField()
    answer = models.TextField(blank=True, null=True)  # reference answer (not used for scoring)

    def __str__(self):
        level_str = self.level.capitalize() if self.level else "Unknown"
        keywords_str = ', '.join(self.keywords) if self.keywords else "No keywords"
        return f"{level_str} - {keywords_str}"
    
    class Meta:
        verbose_name = "Question"
        verbose_name_plural = "Questions"


#  Interview (Session) Model
class InterviewSession(models.Model):
    session_id = models.CharField(max_length=100, unique=True, default='TEMP_SESSION')
    username = models.CharField(max_length=100)
    skills = models.JSONField(default=list)
    skill_categories = models.JSONField(default=dict)
    answers = models.JSONField(default=dict)
    score = models.FloatField(default=0)
    current_level = models.CharField(max_length=50, default='beginner')
    recommended_next_level = models.CharField(max_length=50, blank=True, null=True)
    evaluation_flag = models.CharField(max_length=20, blank=True, null=True)
    flag_records = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Session: {self.session_id} - {self.username}"
    
    class Meta:
        verbose_name = "Interview Session"
        verbose_name_plural = "Interview Sessions"
        ordering = ['-created_at']


#  Profile Model (Authenticated User)
class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    unique_user_id = models.CharField(max_length=100, unique=True)
    session_id = models.CharField(max_length=100, blank=True, null=True)
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True, null=True)
    linkedin_url = models.URLField(blank=True, null=True)
    preferences = models.JSONField(default=dict)  # notification + interview + appearance + privacy settings
    current_level = models.CharField(max_length=50, default='beginner')  # Track user's current difficulty level
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Profile of {self.name} ({self.user.username})"
    
    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"
        ordering = ['-created_at']
