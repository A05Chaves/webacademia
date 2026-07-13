import base64
import binascii
from pathlib import Path

from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError


MAX_UPLOAD_SIZE = 5 * 1024 * 1024
MAX_SIGNATURE_SIZE = 2 * 1024 * 1024
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}
PAYMENT_EXTENSIONS = IMAGE_EXTENSIONS | {'.pdf'}


def _check_size(uploaded_file, maximum=MAX_UPLOAD_SIZE):
    if uploaded_file.size > maximum:
        raise ValidationError('El archivo no puede superar 5 MB.')


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
