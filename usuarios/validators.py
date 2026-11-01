from django.utils import timezone
from django.core.exceptions import ValidationError


# Compatibilidad con la migración histórica 0006; no existe un módulo activo de operadores.
# Espacios reconocidos por str.isspace(), también eliminados en SQL Server.
ESPACIOS_CEDULA = ' \t\n\r\v\f\x1c\x1d\x1e\x1f\x85\xa0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000'


def normalizar_cedula(valor):
    return valor.translate(str.maketrans('', '', '-' + ESPACIOS_CEDULA))


def validar_cedula(valor):
    normalizada = normalizar_cedula(valor)
    if not normalizada or len(normalizada) > 20 or any(
        caracter not in '0123456789' for caracter in normalizada
    ):
        raise ValidationError('Introduce una cédula de hasta 20 dígitos; puedes usar guiones y espacios.')


def anio_actual():
    return timezone.localdate().year
