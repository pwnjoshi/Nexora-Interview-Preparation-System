# interview/answer_evaluation.py

import re
import string
from typing import Dict, List, Tuple
from difflib import SequenceMatcher
from datetime import datetime


def tokenize(text: str) -> List[str]:
    """Convert text to lowercase tokens without stopwords or punctuation."""
    if not text:
        return []
    text = text.lower().translate(str.maketrans('', '', string.punctuation))
    tokens = re.split(r'\W+', text)
    stopwords = {
        "a", "an", "the", "is", "and", "or", "of", "in", "to", "for", "on",
        "with", "as", "by", "at", "it", "that", "this", "are", "was", "be",
        "from", "if", "you", "your", "can", "will", "what", "how", "why",
        "i", "we", "they", "he", "she"
    }
    return [t for t in tokens if t and t not in stopwords]


def keyword_match_score(user_ans: str, correct_keywords: List[str]) -> float:
    """Find how many correct keywords appear in the user answer."""
    if not correct_keywords or not user_ans:
        return 0.0
    user_tokens = set(tokenize(user_ans))
    correct_tokens = set(tokenize(" ".join(correct_keywords)))
    if not correct_tokens:
        return 0.0
    matched = sum(1 for t in correct_tokens if t in user_tokens)
    return matched / len(correct_tokens)


# ------------------------
# Composite scoring
# ------------------------

def _fuzzy_token_hit(user_tokens: List[str], term: str, threshold: float = 0.84) -> bool:
    """Loose fuzzy contains: true if any user token is similar to term above threshold."""
    if not term:
        return False
    term = term.lower().strip()
    for ut in user_tokens:
        if ut == term:
            return True
        if len(term) > 3 and len(ut) > 3:
            if SequenceMatcher(None, ut, term).ratio() >= threshold:
                return True
    return False


def _coverage_score(user_ans: str, correct_keywords: List[str]) -> float:
    tokens = tokenize(user_ans)
    if not correct_keywords:
        return 0.0
    wanted = [w.strip().lower() for w in correct_keywords if isinstance(w, str) and w.strip()]
    if not wanted:
        return 0.0
    hits = 0
    for kw in wanted:
        # split phrases to main words and try fuzzy match
        parts = [p for p in re.split(r"[\s\-/]+", kw) if p]
        # consider keyword hit if all constituent parts are present fuzzily
        if parts and all(_fuzzy_token_hit(tokens, p) for p in parts):
            hits += 1
        elif _fuzzy_token_hit(tokens, kw):
            hits += 1
    return hits / max(1, len(wanted))


def _structure_features(user_ans: str) -> Tuple[float, float, float]:
    """Return (definition, example, tradeoff) feature scores in 0..1."""
    if not user_ans:
        return 0.0, 0.0, 0.0
    text = user_ans.strip().lower()
    # definition cues near start
    definition_cues = [" is a ", " is an ", " refers to ", " is used to ", " means "]
    def_hit = 1.0 if any(cue in text[:160] for cue in definition_cues) else 0.0
    # example cues
    example_cues = ["for example", "e.g.", "such as", "for instance"]
    ex_hit = 1.0 if any(cue in text for cue in example_cues) else 0.0
    # trade-off/comparison cues
    trade_cues = ["however", "but", "versus", "vs", "compared to", "trade-off", "advantages", "disadvantages", "pros", "cons"]
    tr_hit = 1.0 if any(cue in text for cue in trade_cues) else 0.0
    return def_hit, ex_hit, tr_hit


def _clarity_conciseness_score(user_ans: str, level: str = 'beginner') -> float:
    """Score based on length window and hedging; returns 0..1."""
    if not user_ans:
        return 0.0
    words = re.findall(r"\w+", user_ans)
    wc = len(words)
    # target window varies a bit by level
    if level == 'beginner':
        low, high = 30, 180
    elif level == 'intermediate':
        low, high = 40, 220
    else:
        low, high = 50, 260
    # length component: 1 in window, falls off outside
    if wc <= 0:
        length_score = 0.0
    elif wc < low:
        length_score = max(0.0, wc / low)
    elif wc > high:
        # linear decay beyond high, down to 0.5 at 2x high
        length_score = max(0.5, 1 - (wc - high) / max(1, high))
    else:
        length_score = 1.0
    # hedging/filler penalties
    hedges = ["maybe", "probably", "i think", "i guess", "not sure", "kind of", "sort of"]
    text = user_ans.lower()
    hedge_hits = sum(1 for h in hedges if h in text)
    hedge_penalty = min(0.3, 0.1 * hedge_hits)
    return max(0.0, length_score - hedge_penalty)


def _depth_score(user_ans: str) -> float:
    """Approximate depth: unique long tokens and presence of metrics/numbers."""
    tokens = tokenize(user_ans)
    long_terms = {t for t in tokens if len(t) >= 6}
    depth_base = min(1.0, len(long_terms) / 12.0)  # saturate around 12 distinct long terms
    has_numbers = 1.0 if re.search(r"\d", user_ans) else 0.0
    return min(1.0, 0.8 * depth_base + 0.2 * has_numbers)


def composite_answer_score(user_ans: str,
                           correct_keywords: List[str],
                           level: str = 'beginner',
                           reference_answer: str = None) -> float:
    """Composite 0..1 score combining coverage, structure, clarity, and depth."""
    if not user_ans:
        return 0.0
    cov = _coverage_score(user_ans, correct_keywords)
    def_hit, ex_hit, tr_hit = _structure_features(user_ans)
    struct = 0.5 * def_hit + 0.25 * ex_hit + 0.25 * tr_hit
    clarity = _clarity_conciseness_score(user_ans, level)
    depth = _depth_score(user_ans)
    # weights (sum to 1)
    if level == 'hard':
        w_cov, w_struct, w_clarity, w_depth = 0.40, 0.20, 0.15, 0.25
    elif level == 'intermediate':
        w_cov, w_struct, w_clarity, w_depth = 0.45, 0.18, 0.17, 0.20
    else:
        w_cov, w_struct, w_clarity, w_depth = 0.50, 0.15, 0.20, 0.15
    score = (w_cov * cov) + (w_struct * struct) + (w_clarity * clarity) + (w_depth * depth)
    return max(0.0, min(1.0, score))


def composite_breakdown(user_ans: str,
                        correct_keywords: List[str],
                        level: str = 'beginner') -> dict:
    """Return breakdown dict with coverage, structure, clarity, depth, and final score (0..1)."""
    cov = _coverage_score(user_ans or '', correct_keywords or [])
    def_hit, ex_hit, tr_hit = _structure_features(user_ans or '')
    struct = 0.5 * def_hit + 0.25 * ex_hit + 0.25 * tr_hit
    clarity = _clarity_conciseness_score(user_ans or '', level)
    depth = _depth_score(user_ans or '')
    if level == 'hard':
        w_cov, w_struct, w_clarity, w_depth = 0.40, 0.20, 0.15, 0.25
    elif level == 'intermediate':
        w_cov, w_struct, w_clarity, w_depth = 0.45, 0.18, 0.17, 0.20
    else:
        w_cov, w_struct, w_clarity, w_depth = 0.50, 0.15, 0.20, 0.15
    final = (w_cov * cov) + (w_struct * struct) + (w_clarity * clarity) + (w_depth * depth)
    return {
        'coverage': round(cov, 3),
        'structure': round(struct, 3),
        'clarity': round(clarity, 3),
        'depth': round(depth, 3),
        'final': round(max(0.0, min(1.0, final)), 3),
        'structure_components': {
            'definition': int(def_hit),
            'example': int(ex_hit),
            'tradeoff': int(tr_hit)
        }
    }


def flag_for_score(score: float,
                   threshold_same: float = 0.5,
                   threshold_higher: float = 0.8) -> str:
    """Convert numeric score into a difficulty flag."""
    if score < threshold_same:
        return "Easier"
    elif score >= threshold_higher:
        return "Harder"
    else:
        return "Same"


def evaluate_user_level(user_answers: Dict[str, str],
                        level_bank: Dict[str, List[str]],
                        threshold_same: float = 0.5,
                        threshold_higher: float = 0.8,
                        *,
                        use_composite: bool = True,
                        level: str = 'beginner') -> Tuple[Dict, float, str]:
    """Evaluate all answers for one level (e.g., beginner)."""
    per_question = {}
    total_score = 0.0
    count = 0

    for qid, keywords in level_bank.items():
        ans = user_answers.get(qid, "")
        if use_composite:
            score = composite_answer_score(ans, keywords, level=level)
        else:
            score = keyword_match_score(ans, keywords)
        flag = flag_for_score(score, threshold_same, threshold_higher)
        per_question[qid] = {"score": round(score, 2), "flag": flag}
        total_score += score
        count += 1

    avg = total_score / count if count else 0.0
    overall_flag = flag_for_score(avg, threshold_same, threshold_higher)
    return per_question, round(avg, 2), overall_flag


LEVEL_ORDER = ["beginner", "intermediate", "hard"]


def next_level_from_flag(current_level: str, flag: str) -> str:
    """Find the next difficulty level based on flag."""
    try:
        idx = LEVEL_ORDER.index(current_level)
    except ValueError:
        idx = 0
    if flag == "Easier":
        return LEVEL_ORDER[max(0, idx - 1)]
    elif flag == "Harder":
        return LEVEL_ORDER[min(len(LEVEL_ORDER) - 1, idx + 1)]
    else:
        return current_level


def build_flag_record(user_id: str, field: str, current_level: str,
                      per_question: dict, avg_score: float, overall_flag: str) -> dict:
    """Build a record to save in MongoDB."""
    return {
        "user_id": user_id,
        "field": field,
        "level": current_level,
        "per_question": per_question,
        "avg_score": avg_score,
        "overall_flag": overall_flag,
        "timestamp": datetime.utcnow().isoformat()
    }
