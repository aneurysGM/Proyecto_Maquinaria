SUPERVISOR = 'Supervisor'
TECNICO = 'Técnico'


def permisos_panel(usuario):
    administrador = usuario.is_active and usuario.is_superuser
    supervisor = usuario.is_active and usuario.groups.filter(name=SUPERVISOR).exists()
    tecnico = usuario.is_active and usuario.groups.filter(name=TECNICO).exists()
    return {
        'nombre_usuario': usuario.get_full_name() or usuario.get_username(),
        'rol_usuario': 'Administrador' if administrador else (
            TECNICO if tecnico else (SUPERVISOR if supervisor else 'Sin rol asignado')
        ),
        'puede_consultar_maquinaria': administrador or supervisor or tecnico,
        'puede_registrar_maquinaria': administrador,
        'puede_editar_maquinaria': administrador,
        'puede_registrar_operador': administrador,
        'puede_consultar_operadores': administrador,
        'puede_registrar_mantenimiento': administrador or tecnico,
        'puede_consultar_mantenimientos': administrador or tecnico,
    }
