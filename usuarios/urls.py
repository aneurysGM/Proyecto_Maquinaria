from django.urls import path
from django.contrib.auth.views import LoginView, LogoutView
from . import reportes, views

urlpatterns = [
    path('reportes/', reportes.indice, name='reporte_indice'),
    path('reportes/maquinaria/', reportes.reporte, {'tipo': 'maquinaria'}, name='reporte_maquinaria'),
    path('reportes/solicitudes/', reportes.reporte, {'tipo': 'solicitudes'}, name='reporte_solicitudes'),
    path('reportes/entregas/', reportes.reporte, {'tipo': 'entregas'}, name='reporte_entregas'),
    path('reportes/mantenimientos/', reportes.reporte, {'tipo': 'mantenimientos'}, name='reporte_mantenimientos'),
    path('entregas/', views.entrega_lista, name='entrega_lista'),
    path('solicitudes/<int:solicitud_id>/salida/', views.entrega_salida, name='entrega_salida'),
    path('solicitudes/<int:solicitud_id>/retorno/', views.entrega_retorno, name='entrega_retorno'),
    path('solicitudes/', views.solicitud_lista, name='solicitud_lista'),
    path('maquinaria/<int:unidad_id>/solicitar/', views.solicitud_registrar, name='solicitud_registrar'),
    path('solicitudes/<int:solicitud_id>/resolver/', views.solicitud_resolver, name='solicitud_resolver'),
    path('mantenimientos/', views.mantenimiento_lista, name='mantenimiento_lista'),
    path('mantenimientos/registrar/', views.mantenimiento_registrar, name='mantenimiento_registrar'),
    path('unidades/<int:unidad_id>/mantenimientos/', views.mantenimiento_historial, name='mantenimiento_historial'),
    # Muestra el formulario y comprueba las credenciales.
    path(
        'login/',
        LoginView.as_view(template_name='usuarios/login.html'),
        name='login',
    ),

    # Abre el panel; la vista exige una sesión activa.
    path('dashboard/', views.dashboard, name='dashboard'),

    # Consulta y registro de maquinaria almacenada en SQL Server.
    path('maquinaria/', views.maquinaria_lista, name='maquinaria_lista'),
    path(
        'maquinaria/registrar/',
        views.maquinaria_registrar,
        name='maquinaria_registrar',
    ),
    path(
        'maquinaria/<int:maquinaria_id>/',
        views.maquinaria_detalle,
        name='maquinaria_detalle',
    ),

    path(
        'maquinaria/<int:maquinaria_id>/editar/',
        views.maquinaria_editar,
        name='maquinaria_editar',
    ),

    # Cierra la sesión y redirige al login.
    path(
        'logout/',
        LogoutView.as_view(next_page='login'),
        name='logout',
    ),
]
