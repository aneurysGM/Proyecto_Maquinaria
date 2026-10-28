from django.urls import path
from django.contrib.auth.views import LoginView, LogoutView
from . import views

urlpatterns = [
    path('mantenimientos/', views.mantenimiento_lista, name='mantenimiento_lista'),
    path('mantenimientos/registrar/', views.mantenimiento_registrar, name='mantenimiento_registrar'),
    path('unidades/<int:unidad_id>/mantenimientos/', views.mantenimiento_historial, name='mantenimiento_historial'),
    path('operadores/', views.operador_lista, name='operador_lista'),
    path('operadores/registrar/', views.operador_registrar, name='operador_registrar'),
    path('operadores/<int:operador_id>/', views.operador_detalle, name='operador_detalle'),
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
