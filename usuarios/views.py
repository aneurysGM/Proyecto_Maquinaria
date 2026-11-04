from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, IntegrityError, transaction
from django.db.models import Q
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST, require_http_methods

from .entregas import registrar_retorno, registrar_salida
from .forms import (
    MantenimientoForm, MaquinariaEdicionForm, MaquinariaForm,
    RegistroForm, RetornoMaquinariaForm, SalidaMaquinariaForm,
    SolicitudAlquilerForm,
)
from .models import SolicitudAlquiler, Unidad
from .roles import CLIENTE, permisos_panel


def _destino_seguro(request, por_defecto='maquinaria_lista'):
    """Devuelve el 'next' del POST solo si apunta a este mismo sitio."""
    destino = request.POST.get('next')
    if destino and url_has_allowed_host_and_scheme(
        destino, allowed_hosts={request.get_host()}
    ):
        return destino
    return por_defecto


# ---------------------------------------------------------------------------
# Públicas y autenticación
# ---------------------------------------------------------------------------

def home(request):
    return render(request, 'usuarios/index.html')


def acceso_denegado(request, exception):
    return render(request, 'usuarios/acceso_denegado.html', status=403)


def registro(request):
    if request.method == 'POST':
        form = RegistroForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('login')
    else:
        form = RegistroForm()
    return render(request, 'usuarios/registro.html', {'form': form})


# Exige una sesión activa para acceder al dashboard.
# Las variables de rol y permisos las inyecta el context processor
# contexto_panel (roles.py), por eso aquí solo se renderiza la plantilla.
@login_required
def dashboard(request):
    return render(request, 'usuarios/dashboard.html')


# ---------------------------------------------------------------------------
# Clientes
# ---------------------------------------------------------------------------

@login_required
def lista_clientes(request):
    if not permisos_panel(request.user)['puede_gestionar_clientes']:
        raise PermissionDenied
    clientes = User.objects.filter(groups__name=CLIENTE).order_by('-date_joined')
    return render(request, 'usuarios/cliente_lista.html', {'clientes': clientes})


# ---------------------------------------------------------------------------
# Maquinaria
# ---------------------------------------------------------------------------

@login_required
def maquinaria_lista(request):
    if not permisos_panel(request.user)['puede_consultar_maquinaria']:
        raise PermissionDenied
    maquinarias = Unidad.objects.select_related('maquinaria__categoria').filter(
        activo=True, maquinaria__activo=True
    )
    consulta = request.GET.get('q', '').strip()
    estado = request.GET.get('estado', '').strip()

    if consulta:
        maquinarias = maquinarias.filter(
            Q(maquinaria__codigo__icontains=consulta)
            | Q(maquinaria__nombre__icontains=consulta)
            | Q(maquinaria__categoria__nombre__icontains=consulta)
            | Q(numero_serie__icontains=consulta)
        )
    if estado:
        maquinarias = maquinarias.filter(estado=estado)

    return render(
        request,
        'usuarios/maquinaria_lista.html',
        {
            'maquinarias': maquinarias,
            'consulta': consulta,
            'estado_seleccionado': estado,
            'estados': MaquinariaForm.ESTADOS,
        },
    )


@login_required
def maquinaria_registrar(request):
    if not permisos_panel(request.user)['puede_registrar_maquinaria']:
        raise PermissionDenied
    if request.method == 'POST':
        form = MaquinariaForm(request.POST)
        if form.is_valid():
            maquinaria = form.save()
            messages.success(request, 'La maquinaria se registró correctamente.')
            return redirect('maquinaria_detalle', maquinaria_id=maquinaria.id)
    else:
        form = MaquinariaForm()

    return render(request, 'usuarios/maquinaria_form.html', {'form': form})


@login_required
def maquinaria_detalle(request, maquinaria_id):
    if not permisos_panel(request.user)['puede_consultar_maquinaria']:
        raise PermissionDenied
    maquinaria = get_object_or_404(
        Unidad.objects.select_related('maquinaria__categoria'),
        pk=maquinaria_id,
        activo=True,
        maquinaria__activo=True,
    )
    return render(
        request,
        'usuarios/maquinaria_detalle.html',
        {'maquinaria': maquinaria},
    )


@login_required
def maquinaria_editar(request, maquinaria_id):
    if not permisos_panel(request.user)['puede_editar_maquinaria']:
        raise PermissionDenied
    unidad = get_object_or_404(
        Unidad.objects.select_related('maquinaria__categoria'),
        pk=maquinaria_id, activo=True, maquinaria__activo=True,
    )
    form = MaquinariaEdicionForm(
        request.POST if request.method == 'POST' else None, unidad=unidad,
    )
    if request.method == 'POST' and form.is_valid():
        try:
            form.save()
        except ValidationError as error:
            form.add_error(None, error)
        except IntegrityError:
            form.add_error(
                None,
                'No se pudieron guardar los cambios. Comprueba que el código '
                'y el número de serie no estén en uso y vuelve a intentarlo.',
            )
        else:
            messages.success(request, 'La maquinaria se actualizó correctamente.')
            return redirect('maquinaria_detalle', maquinaria_id=unidad.id)
    return render(
        request, 'usuarios/maquinaria_form.html',
        {'form': form, 'edicion': True, 'maquinaria': unidad},
    )


@login_required
@require_POST
def maquinaria_cambiar_estado(request, maquinaria_id):
    if not permisos_panel(request.user)['puede_registrar_maquinaria']:
        raise PermissionDenied
    unidad = get_object_or_404(Unidad, pk=maquinaria_id, activo=True)
    nuevo_estado = request.POST.get('estado')
    estados_validos = [valor for valor, _ in MaquinariaForm.ESTADOS]
    if nuevo_estado in estados_validos:
        unidad.estado = nuevo_estado
        unidad.save()
        messages.success(request, f'El estado cambió a: {nuevo_estado}')
    else:
        messages.error(request, 'Estado inválido.')
    return redirect(_destino_seguro(request))


@login_required
@require_POST
def maquinaria_dar_de_baja(request, maquinaria_id):
    if not permisos_panel(request.user)['puede_registrar_maquinaria']:
        raise PermissionDenied
    unidad = get_object_or_404(Unidad, pk=maquinaria_id, activo=True)
    # Baja lógica: se desactiva la unidad pero el registro se conserva.
    unidad.activo = False
    unidad.save()
    messages.success(request, 'La unidad fue dada de baja correctamente.')
    return redirect(_destino_seguro(request))


# ---------------------------------------------------------------------------
# Mantenimientos
# ---------------------------------------------------------------------------

@login_required
def mantenimiento_lista(request):
    if not permisos_panel(request.user)['puede_consultar_mantenimientos']:
        raise PermissionDenied
    unidades = Unidad.objects.select_related('maquinaria')
    consulta = request.GET.get('q', '').strip()
    if consulta:
        unidades = unidades.filter(
            Q(maquinaria__codigo__icontains=consulta)
            | Q(maquinaria__nombre__icontains=consulta)
            | Q(numero_serie__icontains=consulta)
        )
    return render(request, 'usuarios/mantenimiento_lista.html', {'unidades': unidades, 'consulta': consulta})


@login_required
def mantenimiento_registrar(request):
    if not permisos_panel(request.user)['puede_registrar_mantenimiento']:
        raise PermissionDenied
    form = MantenimientoForm(
        request.POST if request.method == 'POST' else None,
        initial={'unidad': request.GET.get('unidad')},
    )
    if request.method == 'POST' and form.is_valid():
        try:
            mantenimiento = form.save(tecnico=request.user)
        except ValidationError as error:
            form.add_error(None, ' '.join(error.messages))
        except DatabaseError:
            form.add_error(None, 'No se pudo registrar el mantenimiento. No se guardaron cambios. Vuelve a intentarlo.')
        else:
            messages.success(request, 'El mantenimiento se registró correctamente. La unidad está en mantenimiento.')
            return redirect('mantenimiento_historial', unidad_id=mantenimiento.unidad_id)
    return render(request, 'usuarios/mantenimiento_form.html', {'form': form})


@login_required
def mantenimiento_historial(request, unidad_id):
    if not permisos_panel(request.user)['puede_consultar_mantenimientos']:
        raise PermissionDenied
    # El historial permanece consultable aunque la unidad o el catálogo se desactiven.
    unidad = get_object_or_404(Unidad.objects.select_related('maquinaria'), pk=unidad_id)
    mantenimientos = unidad.mantenimientos.select_related('tecnico')
    return render(request, 'usuarios/mantenimiento_historial.html', {'unidad': unidad, 'mantenimientos': mantenimientos})


# ---------------------------------------------------------------------------
# Solicitudes de alquiler
# ---------------------------------------------------------------------------

@login_required
def solicitud_registrar(request, unidad_id):
    if not permisos_panel(request.user)['puede_solicitar_alquiler']:
        raise PermissionDenied
    unidad = get_object_or_404(Unidad.objects.select_related('maquinaria'), pk=unidad_id, activo=True, maquinaria__activo=True)
    form = SolicitudAlquilerForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        try:
            form.save(cliente=request.user, unidad=unidad)
        except ValidationError as error:
            form.add_error(None, error)
        except DatabaseError:
            form.add_error(None, 'No se pudo guardar la solicitud. Vuelve a intentarlo.')
        else:
            messages.success(request, 'Solicitud enviada. El administrador revisará tu solicitud.')
            return redirect('solicitud_lista')
    return render(request, 'usuarios/solicitud_form.html', {'form': form, 'unidad': unidad})


@login_required
def solicitud_lista(request):
    permisos = permisos_panel(request.user)
    if not permisos['puede_consultar_solicitudes']:
        raise PermissionDenied
    solicitudes = SolicitudAlquiler.objects.select_related('unidad__maquinaria', 'cliente', 'revisado_por')
    if not permisos['puede_gestionar_solicitudes']:
        solicitudes = solicitudes.filter(cliente=request.user)
    return render(request, 'usuarios/solicitud_lista.html', {'solicitudes': solicitudes})


@login_required
@require_POST
def solicitud_resolver(request, solicitud_id):
    if not permisos_panel(request.user)['puede_gestionar_solicitudes']:
        raise PermissionDenied
    decision = request.POST.get('decision')
    if decision not in ('Aprobada', 'Rechazada'):
        return HttpResponseBadRequest('Decisión inválida.')
    try:
        with transaction.atomic():
            # Bloqueo común por unidad: serializa la aprobación de solicitudes distintas.
            referencia = get_object_or_404(SolicitudAlquiler, pk=solicitud_id)
            unidad = Unidad.objects.select_for_update().select_related('maquinaria').get(pk=referencia.unidad_id)
            solicitud = SolicitudAlquiler.objects.select_for_update().get(pk=solicitud_id)
            if solicitud.estado != 'Pendiente':
                raise ValidationError('Esta solicitud ya fue revisada.')
            if decision == 'Aprobada':
                if solicitud.fecha_inicio < timezone.localdate():
                    raise ValidationError('No se puede aprobar una solicitud con fecha de inicio pasada.')
                if not unidad.activo or not unidad.maquinaria.activo or unidad.estado != 'Disponible':
                    raise ValidationError('La unidad no está disponible para aprobar el alquiler.')
                if SolicitudAlquiler.objects.filter(unidad=unidad, estado='Aprobada', fecha_inicio__lte=solicitud.fecha_fin, fecha_fin__gte=solicitud.fecha_inicio).exists():
                    raise ValidationError('Ya existe una solicitud aprobada para esas fechas.')
            solicitud.estado = decision
            solicitud.revisado_por = request.user
            solicitud.fecha_revision = timezone.now()
            solicitud.save(update_fields=['estado', 'revisado_por', 'fecha_revision'])
    except ValidationError as error:
        messages.error(request, ' '.join(error.messages))
    except DatabaseError:
        messages.error(request, 'No se pudo actualizar la solicitud. Vuelve a intentarlo.')
    else:
        messages.success(request, f'Solicitud {decision.lower()} correctamente.')
    return redirect('solicitud_lista')


# ---------------------------------------------------------------------------
# Entregas
# ---------------------------------------------------------------------------

@login_required
def entrega_lista(request):
    if not permisos_panel(request.user)['puede_gestionar_entregas']:
        raise PermissionDenied
    estado = request.GET.get('estado', 'pendientes')
    if estado not in ('pendientes', 'devueltas', 'todas'):
        return HttpResponseBadRequest('Filtro de entregas inválido.')
    entregas = SolicitudAlquiler.objects.filter(fecha_salida__isnull=False).select_related(
        'unidad__maquinaria', 'cliente', 'entregado_por', 'recibido_por',
    ).order_by('-fecha_salida', '-id')
    if estado == 'pendientes':
        entregas = entregas.filter(fecha_retorno__isnull=True)
    elif estado == 'devueltas':
        entregas = entregas.filter(fecha_retorno__isnull=False)
    return render(request, 'usuarios/entrega_lista.html', {'entregas': entregas, 'estado': estado})


def _registrar_movimiento(request, solicitud_id, *, retorno):
    if not permisos_panel(request.user)['puede_gestionar_entregas']:
        raise PermissionDenied
    solicitud = get_object_or_404(
        SolicitudAlquiler.objects.select_related('unidad__maquinaria', 'cliente'), pk=solicitud_id,
    )
    clase = RetornoMaquinariaForm if retorno else SalidaMaquinariaForm
    form = clase(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        try:
            if retorno:
                registrar_retorno(solicitud.pk, administrador=request.user, **form.cleaned_data)
            else:
                registrar_salida(solicitud.pk, administrador=request.user, **form.cleaned_data)
        except ValidationError as error:
            form.add_error(None, error)
        except DatabaseError:
            form.add_error(None, 'No se pudo registrar el movimiento. No se guardaron cambios. Actualiza e inténtalo de nuevo.')
        else:
            messages.success(request, 'Retorno registrado. Estado de la unidad: Disponible.' if retorno else 'Salida registrada. Estado de la unidad: Alquilado.')
            return redirect('entrega_lista')
    return render(request, 'usuarios/entrega_form.html', {
        'solicitud': solicitud, 'form': form, 'retorno': retorno,
    })


@login_required
@require_http_methods(['GET', 'POST'])
def entrega_salida(request, solicitud_id):
    return _registrar_movimiento(request, solicitud_id, retorno=False)


@login_required
@require_http_methods(['GET', 'POST'])
def entrega_retorno(request, solicitud_id):
    return _registrar_movimiento(request, solicitud_id, retorno=True)