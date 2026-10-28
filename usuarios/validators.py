from django.core.exceptions import ValidationError
import datetime

# Constante de espacios para cédulas
ESPACIOS_CEDULA = ' \t\n\r\xa0'

def anio_actual():
    return datetime.date.today().year

def validar_cedula(value):
    """Validador básico de cédula para asegurar que no esté vacía."""
    if not value or not str(value).strip():
        raise ValidationError('La cédula no puede estar vacía.')

def normalizar_cedula(cedula):
    """Elimina guiones y espacios de la cédula para normalizarla."""
    if not cedula:
        return ''
    cedula_limpia = str(cedula)
    for char in '-' + ESPACIOS_CEDULA:
        cedula_limpia = cedula_limpia.replace(char, '')
    return cedula_limpia