# interview/db_operations.py

from .models import Resume, Question, InterviewSession, Profile
from django.contrib.auth.models import User
from django.utils.crypto import get_random_string
import logging

logger = logging.getLogger(__name__)

#  Insert Resume + Show User ID
def insert_resume(resume_data):
    username = resume_data.get("username")
    email = resume_data.get("email")

    #  Check if user exists or create a new one
    user, created = User.objects.get_or_create(
        username=username,
        defaults={"email": email or ""}
    )

    #  Check if profile exists or create new one
    profile, profile_created = Profile.objects.get_or_create(
        user=user,
        defaults={
            "unique_user_id": f"USER_{user.id}_{username}",
            "name": username,
            "email": email or ""
        }
    )

    # Create and save resume
    resume = Resume.objects.create(**resume_data)

    # Log to server console
    logger.info(f" Resume inserted successfully for {username}")
    logger.info(f"📝 User ID: {profile.unique_user_id}")

    return {
        "resume": resume, 
        "user_id": profile.unique_user_id, 
        "profile": profile,
        "message": f"Resume uploaded successfully! Your skills: {', '.join(resume_data.get('skills', []))}"
    }


# Fetch Questions Based on Skills
def get_questions_by_skills(skills, limit=10):
    if not skills:
        skills = []
    
    lower_skills = [s.lower() for s in skills]
    matched_questions = []

    for q in Question.objects.all():
        # Handle None keywords
        if not q.keywords:
            continue
            
        question_keywords = [k.lower() for k in q.keywords if k]
        
        # Match skills with keywords
        if any(skill in k or k in skill for k in question_keywords for skill in lower_skills):
            matched_questions.append({
                "keywords": q.keywords,
                "question_text": q.question_text,
                "level": q.level,
                "answer": q.answer,
            })
            if len(matched_questions) >= limit:
                break

    return matched_questions


# Save Interview Answers
def save_answers(username, skills, answers, score):
    session_id = get_random_string(12)
    InterviewSession.objects.create(
        session_id=session_id,
        username=username,
        skills=skills,
        answers=answers,
        score=score
    )
    logger.info(f" Answers saved successfully for {username} - Session: {session_id}")
    return session_id


#  Retrieve Saved Session Data
def get_session_data(session_id):
    try:
        session = InterviewSession.objects.get(session_id=session_id)
        return {
            "username": session.username,
            "skills": session.skills,
            "answers": session.answers,
            "score": session.score,
        }
    except InterviewSession.DoesNotExist:
        return None



logger = logging.getLogger(__name__)
def get_user_profile(user):
    """
    Get or create Profile for the authenticated user.
    If profile doesn't exist, it is automatically created.
    """
    try:
        profile, created = Profile.objects.get_or_create(
            user=user,
            defaults={
                "unique_user_id": f"USER_{user.id}_{user.username}",
                "name": user.username,
                "email": user.email or ""
            }
        )

        if created:
            logger.info(f" New profile created for user: {user.username}")
        else:
            logger.info(f" Existing profile fetched for user: {user.username}")

        return profile

    except Exception as e:
        logger.error(f" Error retrieving or creating profile for {user.username}: {str(e)}")
        return None


def get_latest_resume(username):
    """
    Retrieve the most recent resume uploaded by a specific user.
    Returns None if no resume exists.
    """
    try:
        resume = Resume.objects.filter(username=username).order_by('-uploaded_at').first()
        if resume:
            logger.info(f"Latest resume fetched for {username}")
        else:
            logger.warning(f" No resume found for {username}")
        return resume

    except Exception as e:
        logger.error(f" Error fetching latest resume for {username}: {str(e)}")
        return None


def get_all_questions(limit=10):
    """
    Fetch a limited number of questions from the Question collection.
    Can be customized later to filter by skill or level.
    """
    try:
        questions = Question.objects.all()[:limit]
        logger.info(f" Retrieved {len(questions)} questions (limit={limit})")
        return questions

    except Exception as e:
        logger.error(f" Error retrieving questions: {str(e)}")
        return []
def get_interview_session(session_id):
    """
    Retrieve a specific interview session using its unique session_id.
    Returns None if not found.
    """
    try:
        session = InterviewSession.objects.filter(session_id=session_id).first()
        if session:
            logger.info(f"Interview session '{session_id}' retrieved successfully.")
        else:
            logger.warning(f" Interview session '{session_id}' not found.")
        return session

    except Exception as e:
        logger.error(f" Error retrieving session {session_id}: {str(e)}")
        return None

def update_session_results(session_id, score, evaluation_data, profile_updates):
    """
    Update session results after evaluation.
    Also updates the user's profile if performance level changes.
    """
    try:
        session = InterviewSession.objects.filter(session_id=session_id).first()
        if not session:
            logger.warning(f" Session '{session_id}' not found for update.")
            return {"success": False, "message": "Session not found"}

        # Update session fields
        session.score = score
        # Align with evaluate_interview_answers output keys
        session.flag_records = evaluation_data.get("flag_record", {}) if evaluation_data else {}
        session.recommended_next_level = evaluation_data.get("recommended_next_level") if evaluation_data else session.recommended_next_level
        session.evaluation_flag = evaluation_data.get("overall_flag") if evaluation_data else session.evaluation_flag
        session.save()

        logger.info(f"Updated interview session '{session_id}' with new score: {score}")

        # Update user's profile if needed
        if profile_updates and ("username" in profile_updates or "user" in profile_updates):
            username = profile_updates.get("username") or getattr(profile_updates.get("user"), "username", None)
            user = User.objects.filter(username=username).first() if username else None
            if user:
                profile = Profile.objects.filter(user=user).first()
                if profile:
                    new_level = profile_updates.get("current_level") or profile_updates.get("recommended_next_level")
                    if new_level:
                        profile.current_level = new_level
                        profile.save()
                        logger.info(f"Updated {user.username}'s level to {new_level}")

        return {"success": True, "message": "Session and profile updated successfully"}

    except Exception as e:
        logger.error(f" Error updating session '{session_id}': {str(e)}")
        return {"success": False, "message": str(e)}
