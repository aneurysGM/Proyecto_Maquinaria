# Guárdalo como usuarios/models_admin.py y, en usuarios/models.py, agrega esta línea:
#     from .models_admin import AutorizacionCliente, PerfilCliente  # noqa: F401
# (así Django detecta el modelo y crea la migración)
import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class AutorizacionCliente(models.Model):
    """Qué cambios tiene permitido hacer un cliente. Los decide un administrador."""

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='autorizacion_cliente',
    )
    puede_editar_perfil = models.BooleanField(
        'Puede editar sus datos personales', default=False
    )
    puede_solicitar_alquileres = models.BooleanField(
        'Puede solicitar alquileres', default=False
    )
    notas_internas = models.TextField('Notas internas', blank=True)
    modificado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )
    modificado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'autorización de cliente'
        verbose_name_plural = 'autorizaciones de clientes'

    def __str__(self):
        return f'Autorizaciones de {self.usuario}'


def cliente_puede(usuario, permiso):
    """Úsalo donde el cliente intente hacer un cambio.

    Ejemplo: cliente_puede(request.user, 'puede_editar_perfil') -> True o False
    """
    autorizacion = getattr(usuario, 'autorizacion_cliente', None)
    return bool(autorizacion and getattr(autorizacion, permiso, False))


def normalizar_cedula(valor):
    """Devuelve la cédula como 000-0000000-0 o lanza ValidationError.

    Valida que tenga 11 dígitos y que el último (dígito verificador)
    coincida con el algoritmo de la cédula dominicana.
    """
    digitos = re.sub(r'\D', '', valor or '')
    if len(digitos) != 11:
        raise ValidationError('La cédula debe tener 11 dígitos.')
    if len(set(digitos)) == 1:
        raise ValidationError('Ingresa un número de cédula válido.')

    suma = 0
    for digito, peso in zip(digitos[:10], (1, 2) * 5):
        producto = int(digito) * peso
        suma += producto - 9 if producto > 9 else producto
    if (10 - suma % 10) % 10 != int(digitos[10]):
        raise ValidationError('El número de cédula no es válido. Revísalo e inténtalo de nuevo.')

    return f'{digitos[:3]}-{digitos[3:10]}-{digitos[10]}'


class PerfilCliente(models.Model):
    """Datos de identidad del cliente que se piden al registrarse."""

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='perfil_cliente',
    )
    cedula = models.CharField('Cédula de identidad', max_length=13, unique=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'perfil de cliente'
        verbose_name_plural = 'perfiles de clientes'

    def __str__(self):
        return f'{self.usuario} · {self.cedula}'