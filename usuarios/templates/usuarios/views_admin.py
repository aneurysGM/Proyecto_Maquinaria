# Guárdalo como usuarios/views_clientes_admin.py
import re
from datetime import timedelta
from functools import wraps

from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q, Value
from django.db.models.functions import Replace
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models_admin import AutorizacionCliente
from .roles import ADMINISTRADOR, permisos_panel

Usuario = get_user_model()


def solo_administrador(vista):
    """Exige sesión iniciada y rol de administrador."""

    @login_required
    @wraps(vista)
    def envoltura(request, *args, **kwargs):
        if not permisos_panel(request.user)['puede_gestionar_clientes']:
            raise PermissionDenied
        return vista(request, *args, **kwargs)

    return envoltura


def clientes():
    """Usuarios registrados que no son administradores."""
    return (
        Usuario.objects.filter(is_superuser=False)
        .exclude(groups__name=ADMINISTRADOR)
        .select_related('autorizacion_cliente', 'perfil_cliente')
    )


class AutorizacionClienteForm(forms.ModelForm):
    class Meta:
        model = AutorizacionCliente
        fields = ['puede_editar_perfil', 'puede_solicitar_alquileres', 'notas_internas']
        widgets = {
            'puede_editar_perfil': forms.CheckboxInput(
                attrs={'class': 'form-check-input', 'role': 'switch'}
            ),
            'puede_solicitar_alquileres': forms.CheckboxInput(
                attrs={'class': 'form-check-input', 'role': 'switch'}
            ),
            'notas_internas': forms.Textarea(
                attrs={
                    'class': 'form-control',
                    'rows': 3,
                    'placeholder': 'Apuntes visibles solo para administradores (opcional)',
                }
            ),
        }


@solo_administrador
def cliente_lista(request):
    consulta = request.GET.get('q', '').strip()
    estado = request.GET.get('estado', '')

    base = clientes()
    resultados = base.order_by('-date_joined')

    if consulta:
        filtro = (
            Q(username__icontains=consulta)
            | Q(first_name__icontains=consulta)
            | Q(last_name__icontains=consulta)
            | Q(email__icontains=consulta)
            | Q(perfil_cliente__cedula__icontains=consulta)
        )
        # Permite buscar la cédula sin guiones (ej. 0011234567)
        digitos = re.sub(r'\D', '', consulta)
        if digitos:
            resultados = resultados.annotate(
                cedula_limpia=Replace('perfil_cliente__cedula', Value('-'), Value(''))
            )
            filtro |= Q(cedula_limpia__icontains=digitos)
        resultados = resultados.filter(filtro)
    if estado == 'activos':
        resultados = resultados.filter(is_active=True)
    elif estado == 'inactivos':
        resultados = resultados.filter(is_active=False)

    resumen = {
        'total': base.count(),
        'activos': base.filter(is_active=True).count(),
        'inactivos': base.filter(is_active=False).count(),
        'nuevos': base.filter(date_joined__gte=timezone.now() - timedelta(days=30)).count(),
    }

    pagina = Paginator(resultados, 10).get_page(request.GET.get('page'))

    # Conserva los filtros al cambiar de página
    parametros = request.GET.copy()
    parametros.pop('page', None)

    contexto = {
        'pagina': pagina,
        'consulta': consulta,
        'estado_seleccionado': estado,
        'resumen': resumen,
        'parametros': parametros.urlencode(),
        **permisos_panel(request.user),
    }
    return render(request, 'usuarios/clientes_lista_admin.html', contexto)


@solo_administrador
def cliente_detalle(request, cliente_id):
    cliente = get_object_or_404(clientes(), pk=cliente_id)
    autorizacion, _ = AutorizacionCliente.objects.get_or_create(usuario=cliente)
    nombre = cliente.get_full_name() or cliente.get_username()

    form = AutorizacionClienteForm(instance=autorizacion)

    if request.method == 'POST':
        accion = request.POST.get('accion')

        if accion == 'autorizaciones':
            form = AutorizacionClienteForm(request.POST, instance=autorizacion)
            if form.is_valid():
                registro = form.save(commit=False)
                registro.modificado_por = request.user
                registro.save()
                messages.success(request, f'Autorizaciones de {nombre} actualizadas.')
                return redirect('cliente_detalle', cliente_id=cliente.pk)

        elif accion in ('activar', 'desactivar'):
            cliente.is_active = accion == 'activar'
            cliente.save(update_fields=['is_active'])
            if cliente.is_active:
                messages.success(request, f'La cuenta de {nombre} fue activada.')
            else:
                messages.warning(request, f'La cuenta de {nombre} fue desactivada.')
            return redirect('cliente_detalle', cliente_id=cliente.pk)

    contexto = {
        'cliente': cliente,
        'nombre_cliente': nombre,
        'autorizacion': autorizacion,
        'form': form,
        **permisos_panel(request.user),
    }
    return render(request, 'usuarios/cliente_detalle_admin.html', contexto)