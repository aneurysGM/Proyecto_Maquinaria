"""Salida y retorno físicos sobre la solicitud aprobada, sin crear otro alquiler."""
from datetime import datetime

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from .models import SolicitudAlquiler, Unidad
from .roles import permisos_panel


def _validar_administrador(usuario):
    if not permisos_panel(usuario)['puede_gestionar_entregas']:
        raise PermissionDenied


def _validar_fecha(fecha):
    if not isinstance(fecha, datetime) or timezone.is_naive(fecha):
        raise ValidationError('Indica una fecha y hora válidas con zona horaria.')
    if fecha > timezone.now():
        raise ValidationError('La fecha y hora del movimiento no pueden estar en el futuro.')


def _bloquear_solicitud_y_unidad(solicitud_id):
    try:
        referencia = SolicitudAlquiler.objects.only('unidad_id').get(pk=solicitud_id)
        # Mismo orden de bloqueo que la revisión de solicitudes: unidad y solicitud.
        unidad = Unidad.objects.select_for_update().select_related('maquinaria').get(pk=referencia.unidad_id)
        solicitud = SolicitudAlquiler.objects.select_for_update().get(pk=solicitud_id)
    except (SolicitudAlquiler.DoesNotExist, Unidad.DoesNotExist) as error:
        raise ValidationError('La solicitud o su unidad ya no existen. Actualiza el listado.') from error
    if solicitud.unidad_id != unidad.pk:
        raise ValidationError('La unidad de la solicitud cambió. Actualiza el listado.')
    return solicitud, unidad


@transaction.atomic
def registrar_salida(solicitud_id, *, administrador, fecha_salida):
    _validar_administrador(administrador)
    _validar_fecha(fecha_salida)
    solicitud, unidad = _bloquear_solicitud_y_unidad(solicitud_id)
    if solicitud.estado != 'Aprobada':
        raise ValidationError('Solo se puede entregar una solicitud aprobada.')
    if solicitud.fecha_salida is not None:
        raise ValidationError('Esta solicitud ya fue entregada; no se puede registrar otra salida.')
    if not unidad.activo or not unidad.maquinaria.activo or unidad.estado != 'Disponible':
        raise ValidationError('La unidad debe estar activa y Disponible para registrar la salida.')
    if SolicitudAlquiler.objects.filter(
        unidad_id=unidad.pk, fecha_salida__isnull=False, fecha_retorno__isnull=True,
    ).exists():
        raise ValidationError('La unidad ya tiene una entrega pendiente de devolución.')
    solicitud.fecha_salida = fecha_salida
    solicitud.entregado_por = administrador
    solicitud.full_clean()
    solicitud.save(update_fields=['fecha_salida', 'entregado_por'])
    unidad.estado = 'Alquilado'
    unidad.save(update_fields=['estado'])
    return solicitud


@transaction.atomic
def registrar_retorno(solicitud_id, *, administrador, fecha_retorno):
    _validar_administrador(administrador)
    _validar_fecha(fecha_retorno)
    solicitud, unidad = _bloquear_solicitud_y_unidad(solicitud_id)
    if solicitud.fecha_salida is None:
        raise ValidationError('La solicitud todavía no tiene una salida registrada.')
    if solicitud.fecha_retorno is not None:
        raise ValidationError('El retorno de esta entrega ya fue registrado.')
    if solicitud.estado != 'Aprobada' or unidad.estado != 'Alquilado':
        raise ValidationError('El estado de la solicitud o de la unidad no corresponde a una entrega pendiente.')
    if fecha_retorno < solicitud.fecha_salida:
        raise ValidationError('El retorno no puede ser anterior a la salida.')
    # El retorno sigue siendo posible si la unidad o la cuenta se desactivaron:
    # se conserva el historial y se recupera físicamente la unidad entregada.
    solicitud.fecha_retorno = fecha_retorno
    solicitud.recibido_por = administrador
    solicitud.full_clean()
    solicitud.save(update_fields=['fecha_retorno', 'recibido_por'])
    unidad.estado = 'Disponible'
    unidad.save(update_fields=['estado'])
    return solicitud
