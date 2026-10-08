from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def es_profesor_activo(user):
    instructor = getattr(user, 'perfil_instructor', None)
    return bool(instructor and instructor.activo)


def es_administrador(user):
    """Distingue al administrador-profesor del profesor con acceso operativo."""
    return bool(
        user.is_staff
        and (
            user.is_superuser
            or getattr(user, 'rol', None) == 'ADMIN'
            or not es_profesor_activo(user)
        )
    )


def administrador_required(view_func):
    """Restringe áreas administrativas sin excluir al administrador-profesor."""

    @login_required
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        user = request.user
        if not es_administrador(user):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return wrapper
