from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.http import HttpResponseForbidden
from django.http import JsonResponse


def _has_admin_analytics_role(user):
    if not user.is_authenticated:
        return False
    return user.is_staff or user.is_superuser or user.groups.filter(name='analytics_admin').exists()


def admin_analytics_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not _has_admin_analytics_role(request.user):
            return HttpResponseForbidden('Forbidden')
        return view_func(request, *args, **kwargs)

    return _wrapped


def admin_analytics_api_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'detail': 'Authentication required'}, status=401)
        if not _has_admin_analytics_role(request.user):
            return JsonResponse({'detail': 'Forbidden'}, status=403)
        return view_func(request, *args, **kwargs)

    return _wrapped
