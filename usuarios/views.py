from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, IntegrityError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .forms import MantenimientoForm, MaquinariaEdicionForm, MaquinariaForm, OperadorForm
from .roles import permisos_panel
from .models import Operador, Unidad


def acceso_denegado(request, exception):
    return render(request, 'usuarios/acceso_denegado.html', status=403)


# Exige una sesión activa para acceder al dashboard.
@login_required
def dashboard(request):
    # Muestra la plantilla del dashboard.
    return render(request, 'usuarios/dashboard.html')


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
def operador_registrar(request):
    if not permisos_panel(request.user)['puede_registrar_operador']:
        raise PermissionDenied
    form = OperadorForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        try:
            operador = form.save()
        except IntegrityError:
            form.add_error(None, 'No se pudo registrar el operador. Comprueba que la cédula no esté registrada y vuelve a intentarlo.')
        else:
            messages.success(request, 'El operador se registró correctamente.')
            return redirect('operador_detalle', operador_id=operador.pk)
    return render(request, 'usuarios/operador_form.html', {'form': form})


@login_required
def operador_lista(request):
    if not permisos_panel(request.user)['puede_consultar_operadores']:
        raise PermissionDenied
    return render(request, 'usuarios/operador_lista.html', {'operadores': Operador.objects.all()})


@login_required
def operador_detalle(request, operador_id):
    if not permisos_panel(request.user)['puede_consultar_operadores']:
        raise PermissionDenied
    operador = get_object_or_404(Operador, pk=operador_id)
    return render(request, 'usuarios/operador_detalle.html', {'operador': operador})


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
