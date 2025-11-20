# interview/utils.py
# Utility functions for interview management

from .answer_evaluation import (
    evaluate_user_level,
    build_flag_record,
    next_level_from_flag,
    keyword_match_score,
    composite_answer_score,
    composite_breakdown,
)
from .db_operations import get_questions_by_skills, save_answers, get_session_data
from .models import Question
import random


# ============================================================
# FIXED QUESTION SELECTION FOR INTERVIEW (10 QUESTIONS TOTAL)
# ============================================================

def get_fixed_interview_questions(skills, counts=None, total=None):
    """Return a fixed set of questions by level counts.

    Default distribution (legacy): 4 beginner, 3 intermediate, 3 hard (total 10).
    For reverting to previous criteria (3 each level): pass counts={'beginner':3,'intermediate':3,'hard':3}.

    Args:
        skills (list): extracted skills
        counts (dict): level -> count desired
        total (int): optional total cap; if omitted uses sum(counts)

    Returns:
        list[dict]
    """
    if not skills or not isinstance(skills, list):
        skills = []

    # Default distribution
    if counts is None:
        counts = {"beginner": 4, "intermediate": 3, "hard": 3}

    if total is None:
        total = sum(counts.values())

    all_questions = get_questions_by_skills(skills, limit=300)
    if not all_questions:
        all_questions = [
            {
                "keywords": q.keywords if q.keywords else [],
                "tokens": q.tokens if hasattr(q, 'tokens') else [],
                "question_text": q.question_text,
                "level": q.level,
                "answer": q.answer,
            }
            for q in Question.objects.all()
        ]

    # Group by level
    grouped = {"beginner": [], "intermediate": [], "hard": []}
    for q in all_questions:
        lvl = q.get("level", "beginner")
        if lvl in grouped:
            grouped[lvl].append(q)

    selected = []
    for lvl, cnt in counts.items():
        bucket = grouped.get(lvl, [])
        selected.extend(bucket[:cnt])

    # Fill remainder if under target total
    if len(selected) < total:
        remaining = [q for q in all_questions if q not in selected]
        selected.extend(remaining[: (total - len(selected))])

    return selected[:total]


# ============================================================
# ANSWER SCORING FOR EACH QUESTION
# ============================================================

def score_single_answer(answer_text, expected_keywords, pre_tokenized=None, level='beginner'):
    """
    Score a single answer based on keyword matching.

    Args:
        answer_text: User's answer text
        expected_keywords: List of expected keywords (raw)
        pre_tokenized: List of pre-tokenized keywords (optional, preferred)
        level: Question difficulty level

    Returns:
        float: score between 0 and 1
    """
    # Use composite scoring with pre-tokenized keywords if available
    return composite_answer_score(answer_text, expected_keywords, level=level, pre_tokenized=pre_tokenized)


# ============================================================
# ADAPTIVE SYSTEM (OLD) - NOW USED ONLY FOR EVALUATION
# ============================================================

def evaluate_interview_answers(user_id, field, current_level, user_answers):
    """
    Evaluate user's answers and determine next difficulty level.

    Args:
        user_id: User identifier
        field: Question category
        current_level: beginner/intermediate/hard
        user_answers: Dict -> question_id : answer_text

    Returns:
        dict: evaluation and scoring summary
    """

    # Fetch expected questions for this level
    questions = Question.objects.filter(level=current_level)

    # Build mapping: question_id -> expected_keywords
    level_bank = {str(q.id): q.keywords for q in questions}

    # Perform scoring
    per_question, avg_score, overall_flag = evaluate_user_level(
        user_answers,
        level_bank,
        use_composite=True,
        level=current_level,
    )

    # Determine next difficulty
    next_level = next_level_from_flag(current_level, overall_flag)

    # Prepare DB-ready flag record
    flag_record = build_flag_record(
        user_id, 
        field, 
        current_level,
        per_question, 
        avg_score, 
        overall_flag
    )

    return {
        "per_question_scores": per_question,
        "average_score": avg_score,
        "overall_flag": overall_flag,
        "current_level": current_level,
        "recommended_next_level": next_level,
        "flag_record": flag_record
    }


# ============================================================
# OLD ADAPTIVE QUESTION FUNCTION (KEPT FOR COMPATIBILITY)
# ============================================================

def _build_question_pool(skills):
    """Return a pool of questions (skill-matched first, fallback to all)."""
    if not skills or not isinstance(skills, list):
        skills = []
    pool = get_questions_by_skills(skills, limit=300)
    if not pool:
        pool = [
            {
                "keywords": q.keywords if q.keywords else [],
                "tokens": q.tokens if hasattr(q, 'tokens') else [],
                "question_text": q.question_text,
                "level": q.level,
                "answer": q.answer,
            }
            for q in Question.objects.all()
        ]
    # Shuffle for variety but keep deterministic slice use later
    random.shuffle(pool)
    return pool


def get_adaptive_questions(skills, answered, target_total=10, base_level='beginner'):
    """
    Real-time adaptive question selection.

    Args:
        skills (list): extracted skills
        answered (list[dict]): list of {'question_text','score','level'} already answered
        target_total (int): interview length
        base_level (str): starting difficulty

    Returns:
        dict | None: next question dictionary or None if interview complete

    Policy:
        - Target distribution: 4 beginner, 3 intermediate, 3 hard (like fixed mode)
        - Difficulty escalation: if rolling avg (last 2) > 0.75 and quota not met -> move up
        - Difficulty de-escalation: if rolling avg (last 2) < 0.40 -> move down (unless already beginner)
        - Otherwise maintain current level
        - Avoid duplicates; fallback to any remaining question if quota depleted
    """
    # Interview complete
    if len(answered) >= target_total:
        return None

    pool = _build_question_pool(skills)

    # Keep track of used question texts for exclusion
    used_texts = {a['question_text'] for a in answered}

    # Count per level answered so far
    counts = {'beginner': 0, 'intermediate': 0, 'hard': 0}
    for a in answered:
        lvl = a.get('level','beginner')
        if lvl in counts:
            counts[lvl] += 1

    # Determine current working level
    last_level = answered[-1]['level'] if answered else base_level

    # Rolling performance
    recent = answered[-2:]  # last two answers
    avg_recent = sum(a.get('score',0) for a in recent) / len(recent) if recent else 0

    # Desired level before distribution constraints
    desired = last_level
    escalate_map = {'beginner': 'intermediate', 'intermediate': 'hard'}
    descend_map = {'hard': 'intermediate', 'intermediate': 'beginner'}

    if avg_recent > 0.75 and last_level in escalate_map:
        desired = escalate_map[last_level]
    elif avg_recent < 0.40 and last_level in descend_map:
        desired = descend_map[last_level]

    # Enforce distribution caps (4/3/3)
    caps = {'beginner': 4, 'intermediate': 3, 'hard': 3}
    if counts.get(desired,0) >= caps[desired]:
        # Pick a level with remaining quota (priority order beginner->intermediate->hard)
        for lvl in ['beginner','intermediate','hard']:
            if counts[lvl] < caps[lvl]:
                desired = lvl
                break

    # Filter candidate questions
    candidates = [q for q in pool if q.get('level') == desired and q.get('question_text') not in used_texts]

    if not candidates:
        # Fallback: any unused question
        candidates = [q for q in pool if q.get('question_text') not in used_texts]

    if not candidates:
        return None  # No questions available

    # Select first candidate (pool shuffled earlier)
    return candidates[0]


# ============================================================
# FINAL SCORING FOR WHOLE INTERVIEW SESSION
# ============================================================

def calculate_interview_score(session_id):
    """
    Generate the final score + grade for an interview session.

    Args:
        session_id: Interview Session ID

    Returns:
        dict: score, percentage, feedback
    """

    session_data = get_session_data(session_id)

    if not session_data:
        return None

    answers = session_data.get("answers", {})
    total_questions = len(answers)

    if total_questions == 0:
        return {
            "total_score": 0,
            "percentage": 0,
            "grade": "N/A",
            "feedback": "No answers submitted"
        }

    score = session_data.get("score", 0)
    percentage = score * 100 if score <= 1 else score

    # Grade assignment
    if percentage >= 90:
        grade = "A+"
        feedback = "Excellent! Outstanding performance."
    elif percentage >= 80:
        grade = "A"
        feedback = "Great job! Very good understanding."
    elif percentage >= 70:
        grade = "B"
        feedback = "Good work! Solid understanding."
    elif percentage >= 60:
        grade = "C"
        feedback = "Fair performance. Room for improvement."
    elif percentage >= 50:
        grade = "D"
        feedback = "Needs improvement. Consider reviewing the topics."
    else:
        grade = "F"
        feedback = "Needs significant improvement. Please study more."

    return {
        "session_id": session_id,
        "username": session_data.get("username"),
        "total_questions": total_questions,
        "total_score": score,
        "percentage": round(percentage, 2),
        "grade": grade,
        "feedback": feedback,
        "skills_tested": session_data.get("skills", [])
    }
