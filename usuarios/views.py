from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .forms import MaquinariaEdicionForm, MaquinariaForm
from .roles import permisos_panel
from .models import Unidad


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
