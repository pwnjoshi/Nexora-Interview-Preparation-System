from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Resume, Question, InterviewSession, Profile
from .resume_parser import extract_text_from_resume, extract_skills, parse_resume_complete
from .db_operations import insert_resume, get_questions_by_skills, save_answers, get_session_data
from .utils import get_adaptive_questions, calculate_interview_score, score_single_answer
from .utils import get_fixed_interview_questions
from .answer_evaluation import keyword_match_score
import random
import json
from django.utils import timezone

# Helper to ensure a single Profile per user (merging duplicates)
def get_single_profile(user):

    try:
        # first we try to get user profile from db
        profile = Profile.objects.filter(user=user).first()
        if profile:
            return profile
    except Exception as e:
        print(f"DEBUG: Error getting profile: {e}")
    
    # Create new if none exists
    try:
        profile = Profile.objects.create(
            user=user,
            unique_user_id=f"U{user.id}",
            name=user.username,
            email=user.email or "",
        )
        return profile
    except Exception as e:
        print(f"DEBUG: Error creating profile: {e}")
        # Last resort - return any existing profile
        return Profile.objects.filter(user=user).first()

# NOTE: Views updated to use new models and utilities
# Includes integration with answerflagging.py and mongo_conn.py

@login_required(login_url='/login/')
def upload_resume(request):
    profile = get_single_profile(request.user)
    if request.method == 'POST':
        resume_file = request.FILES.get('resume')
        if not resume_file:
            return render(request, 'interview/upload_resume_new.html', {'error': 'No file selected.'})
        try:
            import os
            from django.conf import settings
            temp_path = os.path.join(settings.MEDIA_ROOT, 'resumes', resume_file.name)
            os.makedirs(os.path.dirname(temp_path), exist_ok=True)
            with open(temp_path, 'wb+') as destination:
                for chunk in resume_file.chunks():
                    destination.write(chunk)
            parsed = parse_resume_complete(temp_path)
            if parsed.get('error'):
                return render(request, 'interview/upload_resume_new.html', {'error': parsed['error']})
            resume_data = {
                'username': request.user.username,
                'email': parsed.get('contact_info', {}).get('email') or request.user.email or '',
                'phone': parsed.get('contact_info', {}).get('phone') or '',
                'skills': parsed.get('skills', []),
                'skill_categories': parsed.get('skill_categories', {}),
                'experience': parsed.get('text', '')[:2000],
                'education': '\n'.join(parsed.get('education', {}).get('degrees', [])),
            }
            result = insert_resume(resume_data)
            if result.get('message'):
                messages.success(request, result['message'])
            else:
                messages.success(request, f"Resume uploaded successfully! Extracted {len(resume_data['skills'])} skills.")
            return redirect('interview_dashboard')
        except Exception as e:
            print(f"Could not parse resume or skills: {e}")
            import traceback
            traceback.print_exc()
            return render(request, 'interview/upload_resume_new.html', {'error': f'Error processing resume: {e}'})
    return render(request, 'interview/upload_resume_new.html')


@login_required(login_url='/login/')
def dashboard(request):
    try:
        profile = get_single_profile(request.user)
        
        # Get the latest resume
        latest_resume = Resume.objects.filter(username=request.user.username).order_by('-uploaded_at').first()
        
        # Get all interview sessions for this user (newest first)
        sessions = InterviewSession.objects.filter(username=request.user.username).order_by('-created_at')
        
        # Calculate statistics
        total_interviews = sessions.count()
        avg_score = 0
        confidence_level = 0
        technical_accuracy = 0
        
        insights = []
        chart_labels = []
        chart_scores = []
        if total_interviews > 0:
            # Calculate average score across all sessions
            total_score_sum = sum(session.score for session in sessions)
            avg_score = (total_score_sum / total_interviews) * 100
            
            # Confidence level based on trend (simple: recent 3 vs overall)
            recent_sessions = list(sessions[:3])
            if recent_sessions:
                recent_avg = sum(s.score for s in recent_sessions) / len(recent_sessions)
                confidence_level = min(recent_avg * 100, 100)
                overall_avg = (total_score_sum / total_interviews)
                # Insight 1: Improvement trend
                if recent_avg > overall_avg + 0.03:  # >3 pts improvement
                    insights.append({
                        'icon': 'emoji-smile',
                        'tone': 'success',
                        'text': "You're improving in technical clarity. Focus next on communication skills."
                    })
                elif recent_avg < overall_avg - 0.05:
                    insights.append({
                        'icon': 'exclamation-triangle',
                        'tone': 'warning',
                        'text': "Recent performance dipped a bit. Revisit fundamentals and pace your answers."
                    })
                
                # Insight 2: Structure vs metrics based on per-question scores
                per_q_scores = []
                for s in recent_sessions:
                    if isinstance(s.answers, dict):
                        for v in s.answers.values():
                            try:
                                per_q_scores.append(float(v.get('score', 0)))
                            except Exception:
                                continue
                if per_q_scores:
                    n = len(per_q_scores)
                    high = sum(1 for x in per_q_scores if x >= 0.75) / n
                    mid = sum(1 for x in per_q_scores if 0.4 <= x < 0.75) / n
                    low = sum(1 for x in per_q_scores if x < 0.4) / n
                    if high >= 0.4 and mid >= 0.25:
                        insights.append({
                            'icon': 'hand-thumbs-up',
                            'tone': 'success',
                            'text': "Great structure in STAR responses. Add metric-driven outcomes."
                        })
                    elif low >= 0.4:
                        insights.append({
                            'icon': 'lightbulb',
                            'tone': 'warning',
                            'text': "Focus on core keywords in answers. Mention definitions and key trade-offs."
                        })
            
            # Technical accuracy: percentage of sessions with score > 0.7
            passing_sessions = [s for s in sessions if s.score >= 0.7]
            technical_accuracy = (len(passing_sessions) / total_interviews) * 100

            # Build improvement-over-time arrays from last 8 sessions (chronological)
            last8 = list(sessions[:8])
            for s in reversed(last8):
                try:
                    chart_labels.append(s.created_at.strftime('%d %b'))
                except Exception:
                    chart_labels.append('')
                chart_scores.append(round(s.score * 100, 1))
        
        # Extract experience years from resume
        experience_years = "N/A"
        if latest_resume:
            from .resume_parser import extract_experience_years
            exp_data = extract_experience_years(latest_resume.experience or "")
            if exp_data.get('total_years', 0) > 0:
                experience_years = f"{exp_data['total_years']} yrs"
        
        # Extract education from resume
        education_level = "N/A"
        if latest_resume and latest_resume.education:
            # Parse first degree mentioned
            education_level = latest_resume.education.split('\n')[0] if latest_resume.education else "N/A"

        # Build radar data from resume skill categories (top 6 categories by count)
        radar_labels = []
        radar_values = []
        if latest_resume and isinstance(latest_resume.skill_categories, dict) and latest_resume.skill_categories:
            items = []
            for cat, skills in latest_resume.skill_categories.items():
                cnt = len(skills) if isinstance(skills, list) else 0
                items.append((cat, cnt))
            items.sort(key=lambda x: x[1], reverse=True)
            top = items[:6]
            radar_labels = [c for c, _ in top]
            radar_values = [v for _, v in top]

        chart_payload = {
            'labels': chart_labels,
            'scores': chart_scores,
            'radar_labels': radar_labels,
            'radar_values': radar_values,
        }
        
        context = {
            'profile': profile,
            'resume': latest_resume,
            'skills': latest_resume.skills if latest_resume else [],
            'skill_categories': latest_resume.skill_categories if latest_resume else {},
            'stats': {
                'total_interviews': total_interviews,
                'avg_score': round(avg_score, 1),
                'avg_feedback_score': round(avg_score / 20, 1),  # Convert to /5 scale
                'confidence_level': round(confidence_level, 0),
                'technical_accuracy': round(technical_accuracy, 0),
                'experience_years': experience_years,
                'education_level': education_level,
                'questions_per_interview': 9,
            },
            'insights': insights,
            'chart_json': json.dumps(chart_payload)
        }
        return render(request, 'interview/dashboard_new.html', context)
    except Exception:
        return redirect('upload_resume')


@login_required(login_url='/login/')
def reports_view(request):
    """View for reports page showing interview analytics with range filter."""
    from .models import InterviewSession, Resume
    from .resume_parser import extract_experience_years
    
    # Get all interview sessions for the user
    sessions = InterviewSession.objects.filter(username=request.user.username).order_by('-created_at')
    total_interviews = len(sessions)
    
    # Calculate statistics
    if total_interviews > 0:
        # Average score
        total_score_sum = sum(session.score for session in sessions)
        avg_score = (total_score_sum / total_interviews) * 100
        
        # Pass rate (sessions with score >= 0.7)
        passing_sessions = [s for s in sessions if s.score >= 0.7]
        pass_rate = (len(passing_sessions) / total_interviews) * 100
        
        # Calculate total practice time (estimate: 2 minutes per question)
        total_questions = total_interviews * 9  # 9 questions per interview
        total_minutes = total_questions * 2
        total_hours = total_minutes / 60
        
        # Monthly comparison (timezone-aware)
        from datetime import timedelta
        last_month = timezone.now() - timedelta(days=30)
        recent_sessions = []
        for s in sessions:
            created = s.created_at
            # Ensure aware datetime for comparison
            if timezone.is_naive(created):
                try:
                    created = timezone.make_aware(created, timezone.get_current_timezone())
                except Exception:
                    # If making aware fails, skip comparison for this item
                    continue
            if created >= last_month:
                recent_sessions.append(s)
        monthly_change = (len(recent_sessions) / total_interviews) * 100 if total_interviews > 0 else 0
    else:
        avg_score = 0
        pass_rate = 0
        total_hours = 0
        monthly_change = 0
    
    # Get recent sessions for activity
    recent_sessions_data = []
    for session in sessions[:5]:  # Last 5 sessions
        recent_sessions_data.append({
            'created_at': session.created_at,
            'score': round(session.score * 100, 0),
            'skills': ', '.join(session.skills[:3]) if session.skills else 'General',
            'level': session.current_level,
        })

    # Build chart data for performance breakdown (last 12 sessions)
    chart_labels = []
    chart_scores = []
    last12 = list(sessions[:12])
    for s in reversed(last12):  # chronological
        try:
            chart_labels.append(s.created_at.strftime('%d %b'))
        except Exception:
            chart_labels.append('')
        chart_scores.append(round(s.score * 100, 1))

    # Compute strengths and weaknesses from recent answers (last 10 sessions)
    from collections import defaultdict
    kw_scores = defaultdict(list)
    for s in sessions[:10]:
        answers = s.answers if isinstance(s.answers, dict) else {}
        for meta in answers.values():
            try:
                sc = float(meta.get('score', 0))
            except Exception:
                sc = 0.0
            kws = meta.get('keywords', []) or ['General']
            for kw in kws:
                if isinstance(kw, str) and kw.strip():
                    kw_scores[kw.strip()].append(sc)

    strengths = []
    weaknesses = []
    if kw_scores:
        # average per keyword
        avgs = [(k, sum(v)/len(v) if v else 0.0, len(v)) for k, v in kw_scores.items()]
        # strengths: avg >= 0.75 with at least 2 samples
        strong = [(k, a) for k, a, n in avgs if a >= 0.75 and n >= 2]
        strong.sort(key=lambda x: x[1], reverse=True)
        strengths = [{'label': k, 'accuracy': round(a*100)} for k, a in strong[:3]]
        # weaknesses: avg <= 0.5
        weak = [(k, a) for k, a, n in avgs if a <= 0.5 and n >= 1]
        weak.sort(key=lambda x: x[1])
        weaknesses = [{'label': k, 'accuracy': round(a*100)} for k, a in weak[:3]]
    
    stats = {
        'total_interviews': total_interviews,
        'avg_score': round(avg_score, 0),
        'pass_rate': round(pass_rate, 0),
        'total_hours': round(total_hours, 1),
        'monthly_change': round(monthly_change, 0),
        'recent_sessions': recent_sessions_data,
        'chart': {'labels': chart_labels, 'scores': chart_scores},
        'strengths': strengths,
        'weaknesses': weaknesses,
    }
    
    import json
    return render(request, 'interview/reports.html', {'stats': stats, 'chart_json': json.dumps(stats['chart'])})


from django.template.loader import get_template
from django.http import HttpResponse
def reports_pdf_view(request):
    """Generate PDF of the current filtered report."""
    # Reuse logic via internal call (DRY-ish). Simpler: call reports_view, but we need data.
    request.GET = request.GET.copy()  # ensure mutable
    # Build same context as reports_view without rendering template twice
    range_param = request.GET.get('range', 'all')
    # Quick reuse: invoke reports_view logic by calling function components
    # For simplicity, call reports_view and extract its context dict from response (not ideal).
    # Instead, duplicate minimal data fetch (could refactor later).
    all_sessions = InterviewSession.objects.filter(username=request.user.username).order_by('-created_at')
    from datetime import timedelta
    if range_param == '7':
        cutoff = timezone.now() - timedelta(days=7)
        sessions = [s for s in all_sessions if s.created_at >= cutoff]
    elif range_param == '30':
        cutoff = timezone.now() - timedelta(days=30)
        sessions = [s for s in all_sessions if s.created_at >= cutoff]
    else:
        sessions = list(all_sessions)
    total_interviews = len(sessions)
    if total_interviews:
        avg_score = (sum(s.score for s in sessions) / total_interviews) * 100
        passing_sessions = [s for s in sessions if s.score >= 0.7]
        pass_rate = (len(passing_sessions) / total_interviews) * 100
    else:
        avg_score = 0
        pass_rate = 0
    template = get_template('interview/report_pdf.html')
    context = {
        'generated_at': timezone.now(),
        'range_param': range_param,
        'total_interviews': total_interviews,
        'avg_score': round(avg_score,1),
        'pass_rate': round(pass_rate,0),
        'sessions': sessions,
    }
    html = template.render(context)
    try:
        from xhtml2pdf import pisa
    except ImportError:
        return HttpResponse('PDF generation library not installed.', status=500)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="nexora_report.pdf"'
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse('Error generating PDF', status=500)
    return response


@login_required(login_url='/login/')
def help_view(request):
    """View for help and FAQ page."""
    return render(request, 'interview/help.html')


@login_required(login_url='/login/')
def settings_view(request):
    profile = get_single_profile(request.user)
    
    # Debug: Check what profile we're working with
    print(f"DEBUG: Profile pk={profile.pk}, type={type(profile.pk)}, name={profile.name}, email={profile.email}, phone={profile.phone}")
    
    prefs = profile.preferences if isinstance(profile.preferences, dict) else {}
    # Defaults
    if 'notifications' not in prefs:
        prefs['notifications'] = {'email': True, 'practice_reminders': True, 'weekly_reports': False}
    if 'interview' not in prefs:
        prefs['interview'] = {'duration': '9', 'distribution': 'fixed', 'show_hints': False}
    if 'appearance' not in prefs:
        prefs['appearance'] = {'theme': 'light'}
    profile.preferences = prefs

    if request.method == 'POST':
        # Update profile fields directly on the object
        profile.name = request.POST.get('full_name', '').strip() or request.user.username
        profile.email = request.POST.get('email', '').strip() or request.user.email
        profile.phone = request.POST.get('phone', '').strip()
        profile.linkedin_url = request.POST.get('linkedin_url', '').strip()
        new_level = request.POST.get('current_level', 'beginner')
        
        print(f"DEBUG: Updating profile for {request.user.username}")
        print(f"DEBUG: New values - Name: {profile.name}, Email: {profile.email}, Phone: {profile.phone}, Level: {new_level}")
        
        if new_level in ['beginner','intermediate','advanced']:
            profile.current_level = new_level
        
        try:
            # Save directly - let djongo handle it
            profile.save()
            print(f"DEBUG: Profile saved successfully")
            messages.success(request, 'Settings saved successfully.')
        except Exception as e:
            print(f"DEBUG: Error saving profile: {e}")
            import traceback
            traceback.print_exc()
            messages.error(request, f'Could not save settings: {e}')
        return redirect('settings')

    return render(request, 'interview/settings.html', {'profile': profile, 'prefs': prefs})


@login_required(login_url='/login/')
def feedback_view(request):
    """View for feedback page."""
    return render(request, 'interview/feedback.html')


@login_required(login_url='/login/')
def profile_view(request):
    """View for user profile page."""
    from .models import InterviewSession, Resume, Profile
    from .resume_parser import extract_experience_years
    
    # Get user profile
    try:
        profile = get_single_profile(request.user)
    except Exception:
        profile = None
    
    # Get latest resume
    try:
        latest_resume = Resume.objects.filter(username=request.user.username).order_by('-uploaded_at').first()
    except Resume.DoesNotExist:
        latest_resume = None
    
    # Get interview sessions
    sessions = InterviewSession.objects.filter(username=request.user.username).order_by('-created_at')
    total_interviews = sessions.count()
    
    # Calculate statistics
    if total_interviews > 0:
        total_score_sum = sum(session.score for session in sessions)
        avg_score = (total_score_sum / total_interviews) * 100
        
        # Calculate total practice time
        total_questions = total_interviews * 9
        total_minutes = total_questions * 2
        total_hours = total_minutes / 60
    else:
        avg_score = 0
        total_hours = 0
    
    # Pagination for recent activity
    page_size = 6
    try:
        page = int(request.GET.get('page', '1'))
        if page < 1:
            page = 1
    except ValueError:
        page = 1

    # Build full activity list
    full_activity = []
    from datetime import datetime
    for session in sessions:
        activity_type = 'Completed Interview'
        activity_detail = f"Score: {round(session.score * 100, 0)}% • 9 questions"
        time_diff = datetime.now() - session.created_at.replace(tzinfo=None)
        if time_diff.days == 0:
            if time_diff.seconds < 3600:
                time_ago = f"{time_diff.seconds // 60} minutes ago"
            else:
                time_ago = f"{time_diff.seconds // 3600} hours ago"
        elif time_diff.days == 1:
            time_ago = "1 day ago"
        else:
            time_ago = f"{time_diff.days} days ago"
        score_pct = session.score * 100
        # Icon selection based on score tiers
        if score_pct >= 85:
            icon = 'trophy-fill'
        elif score_pct >= 60:
            icon = 'lightning-fill'
        else:
            icon = 'exclamation-triangle-fill'
        full_activity.append({
            'type': activity_type,
            'detail': activity_detail,
            'time_ago': time_ago,
            'score': session.score,
            'skills': ', '.join(session.skills[:2]) if session.skills else 'General',
            'icon': icon,
        })

    total_items = len(full_activity)
    total_pages = (total_items // page_size) + (1 if total_items % page_size else 0)
    start = (page - 1) * page_size
    end = start + page_size
    recent_activity = full_activity[start:end]
    has_prev = page > 1
    has_next = page < total_pages
    
    stats = {
        'total_interviews': total_interviews,
        'avg_score': round(avg_score, 0),
        'total_hours': round(total_hours, 1),
        'current_level': profile.current_level if profile else 'Beginner',
        'skills': latest_resume.skills if latest_resume else [],
        'recent_activity': recent_activity,
        'page': page,
        'total_pages': total_pages,
        'has_prev': has_prev,
        'has_next': has_next,
    }
    
    return render(request, 'interview/profile.html', {'stats': stats, 'resume': latest_resume})
    
# start interview view
@login_required(login_url='/login/')
def start_interview_view(request):
    """Start interview with fixed 3-per-level distribution (previous criteria)."""
    profile = get_single_profile(request.user)
    latest_resume = Resume.objects.filter(username=request.user.username).order_by('-uploaded_at').first()

    if not latest_resume:
        return redirect('upload_resume')

    skills = latest_resume.skills if isinstance(latest_resume.skills, list) else []
    current_level = getattr(profile, 'current_level', 'beginner')

    # 3 per level (beginner/intermediate/hard) -> total 9
    questions = get_fixed_interview_questions(skills, counts={"beginner":3,"intermediate":3,"hard":3}, total=9)

    if not questions:
        return render(request, 'interview/dashboard_new.html', {
            'error': 'No questions available. Please contact administrator.'
        })

    request.session['interview_questions'] = questions
    request.session['current_question_index'] = 0
    request.session['user_answers'] = {}
    request.session['interview_level'] = current_level

    return redirect('interview_question')

@login_required(login_url='/login/')
def interview_question_view(request):
    questions = request.session.get('interview_questions', [])
    current_index = request.session.get('current_question_index', 0)
    user_answers = request.session.get('user_answers', {})
    interview_level = request.session.get('interview_level', 'beginner')

    if not questions or current_index >= len(questions):
        return redirect('interview_dashboard')

    if request.method == 'POST':
        answer_text = request.POST.get('answer', '')
        question = questions[current_index]
        user_answers[question['question_text']] = answer_text
        request.session['user_answers'] = user_answers
        next_index = current_index + 1
        request.session['current_question_index'] = next_index

        if next_index >= len(questions):
            latest_resume = Resume.objects.filter(username=request.user.username).order_by('-uploaded_at').first()
            profile = get_single_profile(request.user)

            total_score = 0
            scored_answers = {}
            for q in questions:
                q_text = q['question_text']
                ans_text = user_answers.get(q_text, '')
                keywords = q.get('keywords', [])
                score = keyword_match_score(ans_text, keywords)
                total_score += score
                scored_answers[q_text] = {
                    'answer': ans_text,
                    'score': round(score,2),
                    'keywords': keywords
                }
            avg_score = total_score / len(questions) if questions else 0

            from .utils import evaluate_interview_answers
            user_answers_for_eval = {q_text: data['answer'] for q_text, data in scored_answers.items()}
            try:
                eval_results = evaluate_interview_answers(
                    user_id=profile.unique_user_id,
                    field='general',
                    current_level=interview_level,
                    user_answers=user_answers_for_eval
                )
            except Exception as e:
                print(f"Evaluation error: {e}")
                eval_results = None

            from .models import InterviewSession as InterviewSessionModel
            from django.utils.crypto import get_random_string
            session_id = get_random_string(12)
            interview_session = InterviewSessionModel(
                session_id=session_id,
                username=request.user.username,
                skills=latest_resume.skills if latest_resume else [],
                answers=scored_answers,
                score=round(avg_score,2),
                current_level=interview_level,
                recommended_next_level=eval_results['recommended_next_level'] if eval_results else interview_level,
                evaluation_flag=eval_results['overall_flag'] if eval_results else 'Same',
                flag_records=eval_results['flag_record'] if eval_results else {}
            )
            interview_session.save()

            if eval_results and eval_results['recommended_next_level'] != interview_level:
                profile.current_level = eval_results['recommended_next_level']
                profile.save()

            messages.success(request, f"Interview completed! Your score: {round(avg_score*100,1)}%")

            # Clear session keys
            for key in ['interview_questions','current_question_index','user_answers','interview_level']:
                if key in request.session:
                    del request.session[key]
            return redirect('interview_results', session_id=session_id)
        else:
            return redirect('interview_question')

    current_question = questions[current_index]
    context = {
        'question': {'text': current_question.get('question_text','')},
        'question_number': current_index + 1,
        'total_questions': len(questions),
        'current_level': interview_level
    }
    return render(request, 'interview/question_page.html', context)



@login_required(login_url='/login/')
def results_view(request, session_id):
    # Get session data using mongo_conn utility
    session_data = get_session_data(session_id)
    
    if not session_data:
        return redirect('interview_dashboard')
    
    # Verify it's the current user's session
    if session_data['username'] != request.user.username:
        return redirect('interview_dashboard')
    
    # Get the InterviewSession object for level information
    try:
        from .models import InterviewSession
        interview_session = InterviewSession.objects.get(session_id=session_id)
    except InterviewSession.DoesNotExist:
        interview_session = None
    
    # Calculate detailed scores
    score_details = calculate_interview_score(session_id)

    # Build lightweight analytics from answers
    answers = session_data['answers'] if isinstance(session_data.get('answers'), dict) else {}
    total_q = len(answers)
    strong = mid = weak = 0
    total_score = 0.0
    from collections import Counter
    kw_counter = Counter()
    weak_kw_counter = Counter()
    for meta in answers.values():
        try:
            s = float(meta.get('score', 0))
        except Exception:
            s = 0.0
        total_score += s
        if s >= 0.75:
            strong += 1
        elif s >= 0.4:
            mid += 1
        else:
            weak += 1
        for kw in (meta.get('keywords') or []):
            if kw:
                kw_counter[kw] += 1
                if s < 0.5:
                    weak_kw_counter[kw] += 1

    avg_pct = round((total_score / total_q) * 100, 1) if total_q else 0
    analytics = {
        'total': total_q,
        'avg_pct': avg_pct,
        'strong': strong,
        'mid': mid,
        'weak': weak,
        'top_keywords': [k for k, _ in kw_counter.most_common(6)],
        'weak_keywords': [k for k, _ in weak_kw_counter.most_common(6)],
    }

    context = {
        'session': {
            'final_score': session_data['score'],
            'username': session_data['username'],
            'current_level': interview_session.current_level if interview_session else 'beginner',
            'recommended_next_level': interview_session.recommended_next_level if interview_session else None,
            'evaluation_flag': interview_session.evaluation_flag if interview_session else None,
        },
        'answers': answers,
        'skills': session_data['skills'],
        'score_details': score_details,
        'analytics': analytics,
    }
    
    return render(request, 'interview/results_page.html', context)
