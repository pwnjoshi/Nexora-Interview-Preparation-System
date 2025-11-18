from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.contrib.auth import logout, login
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password


# Create your views here.

def index(request):
    return render(request, 'index.html')

def login_view(request):
    if request.method == 'POST':
        username = (request.POST.get('username') or '').strip()
        password = (request.POST.get('password') or '').strip()

        # check if users have entered correct credentials
        user = authenticate(username=username, password=password)

        if user is not None:
            login(request, user)
            next_url = request.GET.get('next') or request.POST.get('next')
            return redirect(next_url or 'home')
        else:
            messages.error(request, 'Invalid username or password')
            return render(request, 'login.html', status=401)

    return render(request, 'login.html')

def logout_view(request):
    logout(request)
    return redirect("login")


def register_view(request):
    if request.method == 'POST':
        username = (request.POST.get('username') or '').strip()
        email = (request.POST.get('email') or '').strip()
        password1 = request.POST.get('password1') or ''
        password2 = request.POST.get('password2') or ''

        # Basic validation
        if not username or not password1 or not password2:
            messages.error(request, 'Username and passwords are required.')
            return render(request, 'register.html', status=400)

        if password1 != password2:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'register.html', status=400)

        if User.objects.filter(username__iexact=username).exists():
            messages.error(request, 'Username is already taken.')
            return render(request, 'register.html', status=400)

        # Optional: prevent duplicate emails if provided
        if email and User.objects.filter(email__iexact=email).exists():
            messages.error(request, 'Email is already in use.')
            return render(request, 'register.html', status=400)

        # Validate password using Django validators
        try:
            validate_password(password1)
        except ValidationError as e:
            for err in e:
                messages.error(request, err)
            return render(request, 'register.html', status=400)

        # Create user
        user = User.objects.create_user(username=username, email=email or '', password=password1)

        # Auto-login and redirect
        login(request, user)
        next_url = request.GET.get('next') or request.POST.get('next')
        return redirect(next_url or 'interview_dashboard')

    return render(request, 'register.html')