ADMINISTRADOR = 'Administrador'


def contexto_panel(request):
    if request.user.is_authenticated:
        return permisos_panel(request.user)
    return {}

def permisos_panel(usuario):
    # Es administrador quien está activo y es superusuario
    # o pertenece al grupo "Administrador".
    administrador = usuario.is_active and (
        usuario.is_superuser
        or usuario.groups.filter(name=ADMINISTRADOR).exists()
    )
    return {
        'nombre_usuario': usuario.get_full_name() or usuario.get_username(),
        'rol_usuario': ADMINISTRADOR if administrador else 'Sin rol asignado',
        'puede_consultar_maquinaria': administrador,
        'puede_registrar_maquinaria': administrador,
        'puede_gestionar_clientes': administrador,
    }
    
    