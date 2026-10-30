from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="index"),
    # Muestra el formulario y comprueba las credenciales.
    path(
        "login/",
        LoginView.as_view(template_name="usuarios/login.html"),
        name="login",
    ),
    # Abre el panel; la vista exige una sesión activa.
    path("dashboard/", views.dashboard, name="dashboard"),
    
    # Consulta y registro de maquinaria almacenada en SQL Server.
    path("maquinaria/", views.maquinaria_lista, name="maquinaria_lista"),
    path(
        "maquinaria/registrar/",
        views.maquinaria_registrar,
        name='maquinaria_registrar',
    ),
    path(
        "maquinaria/<int:maquinaria_id>/",
        views.maquinaria_detalle,
        name="maquinaria_detalle",
    ),
    
    # --- RUTAS NUEVAS QUE FALTABAN PARA LAS ACCIONES DE MAQUINARIA ---
    path(
        "maquinaria/<int:maquinaria_id>/editar/",
        views.maquinaria_editar,
        name="maquinaria_editar",
    ),
    path(
        "maquinaria/<int:maquinaria_id>/estado/",
        views.maquinaria_cambiar_estado,
        name="maquinaria_cambiar_estado",
    ),
    path(
        "maquinaria/<int:maquinaria_id>/baja/",
        views.maquinaria_dar_de_baja,
        name="maquinaria_dar_de_baja",
    ),
    # ----------------------------------------------------------------

    # Cierra la sesión y redirige al login.
    path(
        "logout/",
        LogoutView.as_view(next_page="login"),
        name="logout",
    ),
    path("registro/", views.registro, name="registro"),
    # Apartado de clientes registrados
    path("clientes/", views.lista_clientes, name="cliente_lista"),
]