from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def es_profesor_activo(user):
    instructor = getattr(user, 'perfil_instructor', None)
    return bool(instructor and instructor.activo)


def administrador_required(view_func):
    """Restringe áreas administrativas y financieras a no profesores."""

    @login_required
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        user = request.user
        if not user.is_staff:
            raise PermissionDenied
        if es_profesor_activo(user) and not user.is_superuser:
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return wrapper
