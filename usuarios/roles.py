ADMINISTRADOR = 'Administrador'
CLIENTE = 'Cliente'
TECNICO = 'Técnico'


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
    tecnico = usuario.is_active and usuario.groups.filter(name=TECNICO).exists()
    cliente = (
        usuario.is_active
        and not administrador
        and not tecnico
        and usuario.groups.filter(name=CLIENTE).exists()
    )

    return {
        'nombre_usuario': usuario.get_full_name() or usuario.get_username(),
        'rol_usuario': ADMINISTRADOR if administrador else (
            TECNICO if tecnico else (CLIENTE if cliente else 'Sin rol asignado')
        ),
        'puede_consultar_maquinaria': administrador or cliente or tecnico,
        'puede_registrar_maquinaria': administrador,
        'puede_editar_maquinaria': administrador,
        'es_cliente': cliente,
        'puede_solicitar_alquiler': cliente,
        'puede_consultar_solicitudes': administrador or cliente,
        'puede_gestionar_solicitudes': administrador,
        'puede_gestionar_entregas': administrador,
        'puede_ver_reportes': administrador,
        'puede_registrar_mantenimiento': administrador or tecnico,
        'puede_consultar_mantenimientos': administrador or tecnico,
        'puede_gestionar_clientes': administrador,
    }