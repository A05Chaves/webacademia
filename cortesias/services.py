from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db.models import Q
from django.utils import timezone
from django.utils.html import escape

from alumnos.models import Alumno

from .models import ClaseCortesia


def normalizar_documento(documento):
    return ''.join(caracter for caracter in (documento or '').upper() if caracter.isalnum())


def sincronizar_conversiones_cortesias():
    alumnos_por_documento = {
        normalizar_documento(alumno.documento): alumno
        for alumno in Alumno.objects.exclude(documento='')
    }
    actualizadas = 0
    for cortesia in ClaseCortesia.objects.filter(se_convirtio=False).exclude(documento__isnull=True):
        alumno = alumnos_por_documento.get(normalizar_documento(cortesia.documento))
        if not alumno or alumno.fecha_registro < cortesia.fecha_registro:
            continue
        cortesia.se_convirtio = True
        cortesia.alumno_convertido = alumno
        cortesia.fecha_conversion = alumno.fecha_registro
        cortesia.save(update_fields=['se_convirtio', 'alumno_convertido', 'fecha_conversion'])
        actualizadas += 1
    return actualizadas


def cortesias_elegibles_para_correo(configuracion):
    hoy = timezone.localdate()
    fecha_limite_clase = hoy - timedelta(days=configuracion.dias_espera)
    fecha_limite_ultimo_envio = timezone.now() - timedelta(days=configuracion.intervalo_dias)
    return ClaseCortesia.objects.filter(
        asistio=True,
        se_convirtio=False,
        fecha_clase__isnull=False,
        fecha_clase__lte=fecha_limite_clase,
        cantidad_correos_seguimiento__lt=configuracion.maximo_envios,
    ).exclude(
        Q(correo__isnull=True) | Q(correo='')
    ).filter(
        Q(fecha_ultimo_correo__isnull=True) |
        Q(fecha_ultimo_correo__lte=fecha_limite_ultimo_envio)
    )


def enviar_seguimiento_cortesias(configuracion, request=None):
    if not configuracion.activo:
        return 0, 0

    enviados = 0
    fallidos = 0
    for cortesia in cortesias_elegibles_para_correo(configuracion):
        nombre = f'{cortesia.nombres} {cortesia.apellidos}'.strip()
        texto = f'Hola {nombre},\n\n{configuracion.mensaje}'
        mensaje_html = escape(configuracion.mensaje).replace('\n', '<br>')
        imagen_html = ''
        if configuracion.publicidad:
            imagen_url = configuracion.publicidad.url
            if request is not None:
                imagen_url = request.build_absolute_uri(imagen_url)
            imagen_html = (
                f'<p><img src="{escape(imagen_url)}" alt="Publicidad Galeras BJJ" '
                'style="max-width:100%;height:auto;border-radius:12px"></p>'
            )
        html = (
            f'<p>Hola <strong>{escape(nombre)}</strong>,</p>'
            f'<p>{mensaje_html}</p>{imagen_html}'
            '<p><strong>GALERAS BJJ</strong></p>'
        )
        correo = EmailMultiAlternatives(
            subject=configuracion.asunto,
            body=texto,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[cortesia.correo],
        )
        correo.attach_alternative(html, 'text/html')
        try:
            correo.send(fail_silently=False)
        except Exception:
            fallidos += 1
            continue
        cortesia.cantidad_correos_seguimiento += 1
        cortesia.fecha_ultimo_correo = timezone.now()
        cortesia.save(update_fields=['cantidad_correos_seguimiento', 'fecha_ultimo_correo'])
        enviados += 1
    return enviados, fallidos
