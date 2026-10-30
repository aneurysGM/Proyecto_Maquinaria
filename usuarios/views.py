from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import render
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .forms import MaquinariaForm
from .roles import permisos_panel
from .models import Unidad


def home(request):
    return render(request, "usuarios/index.html")


def acceso_denegado(request, exception):
    return render(request, "usuarios/acceso_denegado.html", status=403)

@login_required
def lista_clientes(request):
    clientes = User.objects.filter(is_staff=False).order_by('-date_joined')
    return render(request, 'usuarios/cliente_lista.html', {'clientes': clientes})

# Exige una sesión activa para acceder al dashboard.
@login_required
def dashboard(request):
    usuario = request.user
    
    # Estas variables son las que tu base.html y tu dashboard.html necesitan:
    context = {
        'nombre_usuario': usuario.get_full_name() or usuario.username,
        'rol_usuario': 'Administrador' if usuario.is_staff else 'Usuario',
        'puede_consultar_maquinaria': True,  # Cambia según la lógica de tu app
        'puede_registrar_maquinaria': usuario.is_staff,
    }
    
    return render(request, 'usuarios/dashboard.html', context)


@login_required
def maquinaria_lista(request):
    if not permisos_panel(request.user)["puede_consultar_maquinaria"]:
        raise PermissionDenied
    maquinarias = Unidad.objects.select_related("maquinaria__categoria").filter(
        activo=True, maquinaria__activo=True
    )
    consulta = request.GET.get("q", "").strip()
    estado = request.GET.get("estado", "").strip()

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
        "usuarios/maquinaria_lista.html",
        {
            "maquinarias": maquinarias,
            "consulta": consulta,
            "estado_seleccionado": estado,
            "estados": MaquinariaForm.ESTADOS,
        },
    )


@login_required
def maquinaria_registrar(request):
    if not permisos_panel(request.user)["puede_registrar_maquinaria"]:
        raise PermissionDenied
    if request.method == "POST":
        form = MaquinariaForm(request.POST)
        if form.is_valid():
            maquinaria = form.save()
            messages.success(request, "La maquinaria se registró correctamente.")
            return redirect("maquinaria_detalle", maquinaria_id=maquinaria.id)
    else:
        form = MaquinariaForm()

    return render(request, "usuarios/maquinaria_form.html", {"form": form})


@login_required
def maquinaria_detalle(request, maquinaria_id):
    if not permisos_panel(request.user)["puede_consultar_maquinaria"]:
        raise PermissionDenied
    maquinaria = get_object_or_404(
        Unidad.objects.select_related("maquinaria__categoria"),
        pk=maquinaria_id,
        activo=True,
        maquinaria__activo=True,
    )
    return render(
        request,
        "usuarios/maquinaria_detalle.html",
        {"maquinaria": maquinaria},
    )

from .forms import RegistroForm, MaquinariaForm # (o importa RegistroForm)
from django.shortcuts import render, redirect

def registro(request):
    if request.method == 'POST':
        form = RegistroForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('login')
    else:
        form = RegistroForm()
    return render(request, 'usuarios/registro.html', {'form': form})

@login_required
def lista_clientes(request):
    clientes = User.objects.filter(is_staff=False).order_by('-date_joined')
    return render(request, 'usuarios/cliente_lista.html', {'clientes': clientes})

@login_required
def maquinaria_editar(request, maquinaria_id):
    if not permisos_panel(request.user)["puede_registrar_maquinaria"]:
        raise PermissionDenied
    
    unidad = get_object_or_404(
        Unidad.objects.select_related("maquinaria"), 
        pk=maquinaria_id, 
        activo=True, 
        maquinaria__activo=True
    )
    
    if request.method == 'POST':
        form = MaquinariaForm(request.POST, instance=unidad)
        if form.is_valid():
            form.save()
            messages.success(request, "La maquinaria se actualizó correctamente.")
            return redirect('maquinaria_detalle', maquinaria_id=unidad.id)
    else:
        form = MaquinariaForm(instance=unidad)
    
    return render(request, 'usuarios/maquinaria_form.html', {'form': form, 'unidad': unidad})


@login_required
def maquinaria_cambiar_estado(request, maquinaria_id):
    if not permisos_panel(request.user)["puede_registrar_maquinaria"]:
        raise PermissionDenied
        
    unidad = get_object_or_404(Unidad, pk=maquinaria_id, activo=True)
    if request.method == 'POST':
        nuevo_estado = request.POST.get('estado')
        if nuevo_estado:
            unidad.estado = nuevo_estado
            unidad.save()
            messages.success(request, f"El estado cambió a: {nuevo_estado}")
            
    next_url = request.POST.get('next') or 'maquinaria_lista'
    return redirect(next_url)


@login_required
def maquinaria_dar_de_baja(request, maquinaria_id):
    if not permisos_panel(request.user)["puede_registrar_maquinaria"]:
        raise PermissionDenied
        
    unidad = get_object_or_404(Unidad, pk=maquinaria_id, activo=True)
    if request.method == 'POST':
        # Marcamos la unidad como inactiva (baja lógica) manteniendo el registro a salvo
        unidad.activo = False
        unidad.save()
        messages.success(request, "La unidad fue dada de baja correctamente.")
        
    next_url = request.POST.get('next') or 'maquinaria_lista'
    return redirect(next_url)