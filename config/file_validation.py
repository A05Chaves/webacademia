import base64
import binascii
from io import BytesIO
from pathlib import Path

from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError


MAX_UPLOAD_SIZE = 5 * 1024 * 1024
MAX_SIGNATURE_SIZE = 2 * 1024 * 1024
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}
PAYMENT_EXTENSIONS = IMAGE_EXTENSIONS | {'.pdf'}
VIDEO_EXTENSIONS = {'.mp4', '.webm'}
MAX_SHORT_VIDEO_SIZE = 25 * 1024 * 1024


def _check_size(uploaded_file, maximum=MAX_UPLOAD_SIZE):
    if uploaded_file.size > maximum:
        limite_mb = maximum // (1024 * 1024)
        raise ValidationError(f'El archivo no puede superar {limite_mb} MB.')


def validate_image(uploaded_file):
    _check_size(uploaded_file)
    extension = Path(uploaded_file.name).suffix.lower()
    if extension not in IMAGE_EXTENSIONS:
        raise ValidationError('Solo se permiten imágenes JPG, PNG o WEBP.')
    position = uploaded_file.tell()
    try:
        image = Image.open(uploaded_file)
        image.verify()
        if image.format not in {'JPEG', 'PNG', 'WEBP'}:
            raise ValidationError('El formato real de la imagen no es válido.')
    except (UnidentifiedImageError, OSError, SyntaxError) as error:
        raise ValidationError('El archivo no contiene una imagen válida.') from error
    finally:
        uploaded_file.seek(position)


def validate_payment_receipt(uploaded_file):
    _check_size(uploaded_file)
    extension = Path(uploaded_file.name).suffix.lower()
    if extension not in PAYMENT_EXTENSIONS:
        raise ValidationError('El comprobante debe ser PDF, JPG, PNG o WEBP.')
    if extension == '.pdf':
        position = uploaded_file.tell()
        header = uploaded_file.read(5)
        uploaded_file.seek(position)
        if header != b'%PDF-':
            raise ValidationError('El archivo no contiene un PDF válido.')
        return
    validate_image(uploaded_file)


def validate_short_video(uploaded_file):
    _check_size(uploaded_file, MAX_SHORT_VIDEO_SIZE)
    extension = Path(uploaded_file.name).suffix.lower()
    if extension not in VIDEO_EXTENSIONS:
        raise ValidationError('El video debe estar en formato MP4 o WEBM.')
    position = uploaded_file.tell()
    header = uploaded_file.read(16)
    uploaded_file.seek(position)
    is_mp4 = extension == '.mp4' and len(header) >= 12 and header[4:8] == b'ftyp'
    is_webm = extension == '.webm' and header.startswith(b'\x1aE\xdf\xa3')
    if not (is_mp4 or is_webm):
        raise ValidationError('El archivo no contiene un video MP4 o WEBM válido.')


def validate_base64_signature(signature):
    prefix = 'data:image/png;base64,'
    if not signature or not signature.startswith(prefix):
        raise ValidationError('La firma debe ser una imagen PNG válida.')
    try:
        decoded = base64.b64decode(signature[len(prefix):], validate=True)
    except (ValueError, binascii.Error) as error:
        raise ValidationError('La firma contiene datos inválidos.') from error
    if not decoded.startswith(b'\x89PNG\r\n\x1a\n'):
        raise ValidationError('La firma no contiene una imagen PNG válida.')
    if len(decoded) > MAX_SIGNATURE_SIZE:
        raise ValidationError('La firma no puede superar 2 MB.')
    try:
        image = Image.open(BytesIO(decoded)).convert('RGBA')
        image.load()
        pixels_with_ink = sum(
            1 for red, green, blue, alpha in image.getdata()
            if alpha > 20 and min(red, green, blue) < 220
        )
    except (UnidentifiedImageError, OSError, SyntaxError) as error:
        raise ValidationError('La firma no contiene una imagen válida.') from error
    if pixels_with_ink < 20:
        raise ValidationError('Debe realizar una firma visible antes de enviar.')
