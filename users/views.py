import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.core.mail import EmailMultiAlternatives
from django.shortcuts import redirect, render
from django.template.loader import render_to_string

from .forms import UserPasswordResetForm, UserRegisterForm, UserUpdateForm
from movies.models import Booking, Movie

logger = logging.getLogger(__name__)

def home(request):
    movies= Movie.objects.all()
    return render(request,'home.html',{'movies':movies})
def register(request):
    if request.method == 'POST':
        form=UserRegisterForm(request.POST)
        if form.is_valid():
            form.save()
            username=form.cleaned_data.get('username')
            password=form.cleaned_data.get('password1')
            user=authenticate(username=username,password=password)
            login(request,user)
            return redirect('profile')
    else:
        form=UserRegisterForm()
    return render(request,'users/register.html',{'form':form})

def login_view(request):
    if request.method == 'POST':
        form=AuthenticationForm(request,data=request.POST)
        if form.is_valid():
            user=form.get_user()
            login(request,user)
            return redirect('/')
    else:
        form=AuthenticationForm()
    return render(request,'users/login.html',{'form':form})


def forgot_password(request):
    if request.method == 'POST':
        form = UserPasswordResetForm(request.POST)
        if form.is_valid():
            try:
                form.save(
                    request=request,
                    use_https=request.is_secure(),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    email_template_name='emails/password_reset.txt',
                    subject_template_name='emails/password_reset_subject.txt',
                    html_email_template_name='emails/password_reset.html',
                )
                messages.success(request, 'Password reset email sent. Please check your inbox.')
                return redirect('password_reset_done')
            except Exception:
                logger.exception('Password reset email failed for email=%s', form.cleaned_data.get('email'))
                messages.error(request, 'Password reset email could not be sent right now. Please try again.')
    else:
        form = UserPasswordResetForm()
    return render(request, 'users/reset_password.html', {'form': form})

@login_required
def profile(request):
    bookings= Booking.objects.filter(user=request.user)
    if request.method == 'POST':
        u_form = UserUpdateForm(request.POST, instance=request.user)
        if u_form.is_valid():
            u_form.save()
            return redirect('profile')
    else:
        u_form = UserUpdateForm(instance=request.user)

    return render(request, 'users/profile.html', {'u_form': u_form,'bookings':bookings})

@login_required
def reset_password(request):
    if request.method == 'POST':
        form=PasswordChangeForm(user=request.user,data=request.POST)
        if form.is_valid():
            form.save()
            _send_password_change_email(request.user)
            return redirect('login')
    else:
        form=PasswordChangeForm(user=request.user)
    return render(request,'users/reset_password.html',{'form':form})


def _send_password_change_email(user):
    if not user.email:
        return

    context = {
        'username': user.get_username(),
        'email': user.email,
        'site_name': 'BookMySeat',
    }
    try:
        subject = render_to_string('emails/password_changed_subject.txt', context).strip()
        text_body = render_to_string('emails/password_changed.txt', context)
        html_body = render_to_string('emails/password_changed.html', context)
        message = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email],
        )
        message.attach_alternative(html_body, 'text/html')
        message.send()
    except Exception:
        logger.exception('Password change email failed for user_id=%s', user.id)
