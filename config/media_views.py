from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404
from django.shortcuts import redirect

from pagos.models import Pago
from registros_legales.models import RegistroLegalEstudiante


PUBLIC_PREFIXES = ('qr_pagos/', 'videos_home/')


def _safe_media_path(relative_path):
    media_root = Path(settings.MEDIA_ROOT).resolve()
    requested = (media_root / relative_path).resolve()
    if media_root not in requested.parents or not requested.is_file():
        raise Http404
    return requested


def serve_media(request, path):
    normalized = path.replace('\\', '/').lstrip('/')
    file_path = _safe_media_path(normalized)
    if normalized.startswith(PUBLIC_PREFIXES):
        return FileResponse(file_path.open('rb'))
    if not request.user.is_authenticated:
        return redirect(f'{settings.LOGIN_URL}?next={request.path}')

    allowed = request.user.is_staff
    if normalized.startswith('comprobantes_pagos/'):
        allowed = allowed or Pago.objects.filter(
            comprobante=normalized, alumno__user=request.user
        ).exists()
    elif normalized.startswith('registros_estudiantes/fotos/'):
        allowed = allowed or RegistroLegalEstudiante.objects.filter(
            foto=normalized, documento=request.user.username
        ).exists()
    else:
        allowed = False
    if not allowed:
        raise Http404
    return FileResponse(file_path.open('rb'))
