import hashlib
from datetime import timedelta
from io import BytesIO

from django.conf import settings
from django.core.mail import EmailMessage
from django.db.models import Q
from django.utils import timezone

from .models import Pago


MARCA_ACADEMIA = 'GALERAS BJJ'


def calcular_hash_archivo(archivo):
    posicion = archivo.tell() if hasattr(archivo, 'tell') else 0
    archivo.seek(0)
    digest = hashlib.sha256()
    for bloque in iter(lambda: archivo.read(1024 * 1024), b''):
        digest.update(bloque)
    archivo.seek(posicion)
    return digest.hexdigest()


def marcar_posible_duplicado(pago):
    """Marca coincidencias; no bloquea casos legítimos como pagos de hermanos."""
    if pago.comprobante:
        pago.comprobante_hash = calcular_hash_archivo(pago.comprobante)

    candidatos = Pago.objects.exclude(pk=pago.pk).order_by('-fecha_reporte')
    condiciones = Q()
    if pago.comprobante_hash:
        condiciones |= Q(comprobante_hash=pago.comprobante_hash)
    if pago.referencia_pago:
        condiciones |= Q(
            metodo_qr=pago.metodo_qr,
            referencia_pago__iexact=pago.referencia_pago.strip(),
        )
    if pago.alumno_id:
        condiciones |= Q(
            alumno_id=pago.alumno_id,
            valor=pago.valor,
            fecha_reporte__gte=timezone.now() - timedelta(days=2),
        )
    elif pago.pagador_documento:
        condiciones |= Q(
            pagador_documento__iexact=pago.pagador_documento.strip(),
            valor=pago.valor,
            fecha_reporte__gte=timezone.now() - timedelta(days=2),
        )

    coincidencia = candidatos.filter(condiciones).first() if condiciones else None
    pago.posible_duplicado = coincidencia is not None
    pago.duplicado_de = coincidencia
    return coincidencia


def destinatario_comprobante(pago):
    if pago.pagador_correo:
        return pago.pagador_correo
    if hasattr(pago, 'inscripcion_evento') and pago.inscripcion_evento.correo:
        return pago.inscripcion_evento.correo
    if pago.alumno_id and pago.alumno.user.email:
        return pago.alumno.user.email
    return ''


def generar_pdf_comprobante_pago(pago):
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buffer = BytesIO()
    documento = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        title=f'Comprobante {pago.numero_comprobante}',
        author=MARCA_ACADEMIA,
    )
    estilos = getSampleStyleSheet()
    estilos.add(ParagraphStyle(
        name='MarcaAcademia', parent=estilos['Title'], fontName='Helvetica-Bold',
        fontSize=18, textColor=colors.HexColor('#17365D'), spaceAfter=3,
    ))
    estilos.add(ParagraphStyle(name='DerechaPago', parent=estilos['Normal'], alignment=TA_RIGHT))
    estilos.add(ParagraphStyle(
        name='PiePago', parent=estilos['Normal'], alignment=TA_CENTER,
        fontSize=8, textColor=colors.HexColor('#666666'),
    ))
    historia = []
    ruta_logo = settings.BASE_DIR / 'static' / 'img' / 'galeras-bjj-logo.png'
    if ruta_logo.exists():
        logo = Image(str(ruta_logo), width=42 * mm, height=24 * mm)
        logo.hAlign = 'CENTER'
        historia.extend([logo, Spacer(1, 2 * mm)])
    historia.extend([
        Paragraph(MARCA_ACADEMIA, estilos['MarcaAcademia']),
        Paragraph('Comprobante interno de pago', estilos['Normal']),
        Spacer(1, 7 * mm),
    ])

    fecha = timezone.localtime(pago.fecha_validacion or pago.fecha_reporte)
    cabecera = Table([
        [Paragraph(f'<b>Comprobante:</b> {pago.numero_comprobante}', estilos['Normal']),
         Paragraph(f'<b>Fecha:</b> {fecha:%d/%m/%Y %H:%M}', estilos['DerechaPago'])],
        [Paragraph(f'<b>Estado:</b> {pago.get_estado_display()}', estilos['Normal']),
         Paragraph(f'<b>Tipo:</b> {pago.get_tipo_display()}', estilos['DerechaPago'])],
    ], colWidths=[85 * mm, 85 * mm])
    cabecera.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), .6, colors.HexColor('#AAB7C4')),
        ('INNERGRID', (0, 0), (-1, -1), .3, colors.HexColor('#D7DEE5')),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F3F6F8')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    historia.extend([cabecera, Spacer(1, 6 * mm)])

    estudiante = str(pago.alumno) if pago.alumno_id else 'Participante externo'
    documento_estudiante = pago.alumno.documento if pago.alumno_id else 'No asociado'
    historia.append(Paragraph(
        f'<b>Estudiante/participante:</b> {estudiante}<br/>'
        f'<b>Documento:</b> {documento_estudiante}<br/>'
        f'<b>Pagador:</b> {pago.pagador_nombre or estudiante}<br/>'
        f'<b>Documento del pagador:</b> {pago.pagador_documento or documento_estudiante}',
        estilos['Normal'],
    ))
    historia.append(Spacer(1, 6 * mm))

    filas = [
        ['Concepto', pago.concepto_detalle or pago.get_tipo_display()],
        ['Valor pagado', f'$ {pago.valor:,.2f} COP'],
        ['Método', str(pago.metodo_qr)],
        ['Referencia', pago.referencia_pago or 'Sin referencia'],
    ]
    if pago.suscripcion_id:
        filas.extend([
            ['Inicio de cobertura', pago.suscripcion.fecha_inicio.strftime('%d/%m/%Y')],
            ['Fin de cobertura', pago.suscripcion.fecha_vencimiento.strftime('%d/%m/%Y')],
        ])
    tabla = Table(filas, colWidths=[55 * mm, 115 * mm])
    tabla.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), .4, colors.HexColor('#BCC7D1')),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#F3F6F8')),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
    ]))
    historia.extend([tabla, Spacer(1, 10 * mm)])
    historia.append(Paragraph(
        'Este comprobante es un soporte interno y no reemplaza la factura electrónica cuando legalmente sea exigible.',
        estilos['PiePago'],
    ))
    documento.build(historia)
    return buffer.getvalue()


def enviar_comprobante_pago(pago):
    destinatario = destinatario_comprobante(pago)
    if not destinatario:
        raise ValueError('El pago no tiene un correo asociado.')
    pdf = generar_pdf_comprobante_pago(pago)
    mensaje = EmailMessage(
        subject=f'Comprobante {pago.numero_comprobante} - {MARCA_ACADEMIA}',
        body=(
            'Hola,\n\nAdjuntamos el comprobante de pago aprobado por '
            f'${pago.valor:,.2f} COP.\n\n{MARCA_ACADEMIA}'
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[destinatario],
    )
    mensaje.attach(
        f'comprobante-{pago.numero_comprobante}.pdf', pdf, 'application/pdf'
    )
    mensaje.send(fail_silently=False)
    pago.correo_comprobante_enviado_a = destinatario
    pago.fecha_envio_comprobante = timezone.now()
    pago.error_envio_comprobante = ''
    pago.save(update_fields=[
        'correo_comprobante_enviado_a', 'fecha_envio_comprobante',
        'error_envio_comprobante',
    ])
