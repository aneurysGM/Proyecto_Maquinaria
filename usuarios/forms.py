from zoneinfo import ZoneInfo

from django import forms
from django.core.validators import MaxValueValidator
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from .models import Categoria, Mantenimiento, Maquinaria, SolicitudAlquiler, Unidad
from .roles import permisos_panel
from .validators import anio_actual


class MaquinariaForm(forms.Form):
    ESTADOS = Unidad.ESTADOS

    codigo = forms.CharField(
        label='Código de catálogo',
        max_length=20,
        strip=True,
        help_text='Identificador único del modelo o tipo de maquinaria.',
    )
    nombre = forms.CharField(label='Nombre', max_length=120, strip=True)
    categoria = forms.CharField(
        label='Categoría',
        max_length=80,
        strip=True,
        help_text='Se reutiliza la categoría si ya existe.',
    )
    marca = forms.CharField(label='Marca', max_length=60, strip=True, required=False)
    modelo = forms.CharField(label='Modelo', max_length=60, strip=True, required=False)
    costo_adquisicion = forms.DecimalField(
        label='Costo de adquisición',
        max_digits=18,
        decimal_places=2,
        min_value=0,
    )
    tarifa_diaria = forms.DecimalField(
        label='Tarifa diaria',
        max_digits=18,
        decimal_places=2,
        min_value=0.01,
    )
    tarifa_semanal = forms.DecimalField(
        label='Tarifa semanal',
        max_digits=18,
        decimal_places=2,
        min_value=0.01,
    )
    tarifa_mensual = forms.DecimalField(
        label='Tarifa mensual',
        max_digits=18,
        decimal_places=2,
        min_value=0.01,
    )
    deposito_garantia = forms.DecimalField(
        label='Depósito de garantía',
        max_digits=18,
        decimal_places=2,
        min_value=0,
        initial=0,
    )
    numero_serie = forms.CharField(
        label='Número de serie',
        max_length=50,
        strip=True,
        help_text='Identifica de forma única la unidad física.',
    )
    estado = forms.ChoiceField(
        label='Estado',
        choices=ESTADOS,
        initial='Disponible',
    )
    horas_uso = forms.DecimalField(
        label='Horas de uso',
        max_digits=10,
        decimal_places=1,
        min_value=0,
        initial=0,
    )
    fecha_adquisicion = forms.DateField(
        label='Fecha de adquisición',
        required=False,
        input_formats=('%Y-%m-%d',),
        widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
    )
    anio_fabricacion = forms.IntegerField(
        label='Año de fabricación', min_value=1,
        validators=(MaxValueValidator(anio_actual),),
    )
    ubicacion_actual = forms.CharField(
        label='Ubicación actual', max_length=200, strip=True,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['anio_fabricacion'].widget.attrs['max'] = anio_actual()

    def clean_codigo(self):
        codigo = self.cleaned_data['codigo']
        coincidencias = Maquinaria.objects.filter(codigo__iexact=codigo)
        if getattr(self, 'unidad', None) is not None:
            coincidencias = coincidencias.exclude(pk=self.unidad.maquinaria_id)
        if coincidencias.exists():
            raise forms.ValidationError('Ya existe una maquinaria con este código.')
        return codigo

    def clean_numero_serie(self):
        numero_serie = self.cleaned_data['numero_serie']
        coincidencias = Unidad.objects.filter(numero_serie__iexact=numero_serie)
        if getattr(self, 'unidad', None) is not None:
            coincidencias = coincidencias.exclude(pk=self.unidad.pk)
        if coincidencias.exists():
            raise forms.ValidationError(
                'Ya existe una maquinaria con este número de serie.'
            )
        return numero_serie

    @transaction.atomic
    def save(self):
        datos = self.cleaned_data
        categoria = Categoria.objects.filter(
            nombre__iexact=datos['categoria']
        ).first()
        if categoria is None:
            categoria = Categoria.objects.create(nombre=datos['categoria'])
        maquinaria = Maquinaria.objects.create(
            categoria=categoria,
            codigo=datos['codigo'],
            nombre=datos['nombre'],
            marca=datos['marca'] or None,
            modelo=datos['modelo'] or None,
            costo_adquisicion=datos['costo_adquisicion'],
            tarifa_diaria=datos['tarifa_diaria'],
            tarifa_semanal=datos['tarifa_semanal'],
            tarifa_mensual=datos['tarifa_mensual'],
            deposito_garantia=datos['deposito_garantia'],
        )
        return Unidad.objects.create(
            maquinaria=maquinaria,
            numero_serie=datos['numero_serie'],
            estado=datos['estado'],
            horas_uso=datos['horas_uso'],
            fecha_adquisicion=datos['fecha_adquisicion'],
            anio_fabricacion=datos['anio_fabricacion'],
            ubicacion_actual=datos['ubicacion_actual'],
        )


class MaquinariaEdicionForm(MaquinariaForm):
    CAMPOS_CATALOGO = (
        'codigo', 'nombre', 'marca', 'modelo', 'costo_adquisicion',
        'tarifa_diaria', 'tarifa_semanal', 'tarifa_mensual', 'deposito_garantia',
    )
    CAMPOS_UNIDAD = (
        'numero_serie', 'estado', 'horas_uso', 'fecha_adquisicion',
        'anio_fabricacion', 'ubicacion_actual',
    )

    def __init__(self, *args, unidad, **kwargs):
        self.unidad = unidad
        inicial = {
            campo: getattr(unidad.maquinaria, campo)
            for campo in self.CAMPOS_CATALOGO
        }
        inicial.update({
            campo: getattr(unidad, campo) for campo in self.CAMPOS_UNIDAD
        })
        inicial['categoria'] = unidad.maquinaria.categoria.nombre
        kwargs['initial'] = {**inicial, **kwargs.get('initial', {})}
        super().__init__(*args, **kwargs)

    @staticmethod
    def _guardar_cambios(objeto, valores, fecha):
        modificados = []
        for campo, valor in valores.items():
            if getattr(objeto, campo) != valor:
                setattr(objeto, campo, valor)
                modificados.append(campo)
        if modificados:
            objeto.fecha_modificacion = fecha
            objeto.save(update_fields=[*modificados, 'fecha_modificacion'])

    @transaction.atomic
    def save(self):
        # Bloquear catálogo y unidad mantiene ambos cambios en una transacción.
        maquinaria = Maquinaria.objects.select_for_update().get(
            pk=self.unidad.maquinaria_id
        )
        unidad = Unidad.objects.select_for_update().get(pk=self.unidad.pk)
        datos = self.cleaned_data
        if datos['estado'] != 'Alquilado' and unidad.solicitudes_alquiler.filter(
            fecha_salida__isnull=False, fecha_retorno__isnull=True,
        ).exists():
            raise ValidationError('La unidad tiene una entrega pendiente. Registra su retorno para cambiar el estado.')
        categoria = Categoria.objects.filter(
            nombre__iexact=datos['categoria']
        ).first()
        if categoria is None:
            categoria = Categoria.objects.create(nombre=datos['categoria'])
        catalogo = {campo: datos[campo] for campo in self.CAMPOS_CATALOGO}
        catalogo['marca'] = catalogo['marca'] or None
        catalogo['modelo'] = catalogo['modelo'] or None
        catalogo['categoria'] = categoria
        fecha = timezone.now()
        self._guardar_cambios(maquinaria, catalogo, fecha)
        self._guardar_cambios(
            unidad, {campo: datos[campo] for campo in self.CAMPOS_UNIDAD}, fecha
        )
        return unidad


class UnidadMantenimientoChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, unidad):
        return (
            f'{unidad.codigo} · {unidad.nombre} · Serie: {unidad.numero_serie} '
            f'· Unidad #{unidad.pk} · {unidad.get_estado_display()}'
        )


class MantenimientoForm(forms.Form):
    unidad = UnidadMantenimientoChoiceField(
        label='Maquinaria / unidad física', queryset=Unidad.objects.none(),
        help_text='Selecciona la serie de la unidad disponible o en mantenimiento.',
    )
    fecha = forms.DateField(
        label='Fecha', input_formats=('%Y-%m-%d',),
        widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
    )
    tipo = forms.ChoiceField(label='Tipo de mantenimiento', choices=Mantenimiento.TIPOS)
    descripcion = forms.CharField(
        label='Descripción', max_length=300, strip=True, widget=forms.Textarea(attrs={'rows': 4}),
    )
    costo = forms.DecimalField(label='Costo', max_digits=18, decimal_places=2, min_value=0)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['unidad'].queryset = Unidad.objects.select_related('maquinaria').filter(
            activo=True, maquinaria__activo=True, estado__in=('Disponible', 'Mantenimiento'),
        )

    @transaction.atomic
    def save(self, *, tecnico):
        if not permisos_panel(tecnico)['puede_registrar_mantenimiento']:
            raise PermissionDenied
        datos = self.cleaned_data
        # Releer y bloquear evita sobrescribir un estado cambiado después de validar.
        unidad = Unidad.objects.select_for_update().select_related('maquinaria').filter(pk=datos['unidad'].pk).first()
        if unidad is None or not unidad.activo or not unidad.maquinaria.activo or unidad.estado not in ('Disponible', 'Mantenimiento'):
            raise ValidationError('La unidad ya no está disponible para registrar mantenimiento. Selecciona otra unidad.')
        mantenimiento = Mantenimiento(
            unidad=unidad, tecnico=tecnico,
            **{campo: datos[campo] for campo in ('fecha', 'tipo', 'descripcion', 'costo')},
        )
        mantenimiento.full_clean()
        mantenimiento.save()
        unidad.estado = 'Mantenimiento'
        unidad.save(update_fields=['estado'])
        return mantenimiento


class SolicitudAlquilerForm(forms.Form):
    fecha_inicio = forms.DateField(label='Fecha de inicio', widget=forms.DateInput(attrs={'type': 'date'}))
    fecha_fin = forms.DateField(label='Fecha de fin', widget=forms.DateInput(attrs={'type': 'date'}))
    comentario = forms.CharField(label='Comentario', max_length=500, required=False, widget=forms.Textarea(attrs={'rows': 3}))

    def clean(self):
        datos = super().clean()
        inicio, fin = datos.get('fecha_inicio'), datos.get('fecha_fin')
        if inicio and inicio < timezone.localdate():
            self.add_error('fecha_inicio', 'La fecha de inicio no puede estar en el pasado.')
        if inicio and fin and fin < inicio:
            self.add_error('fecha_fin', 'La fecha de fin debe ser igual o posterior al inicio.')
        return datos

    @transaction.atomic
    def save(self, *, cliente, unidad):
        if not permisos_panel(cliente)['puede_solicitar_alquiler']:
            raise PermissionDenied
        unidad = Unidad.objects.select_for_update().select_related('maquinaria').get(pk=unidad.pk)
        if not unidad.activo or not unidad.maquinaria.activo or unidad.estado != 'Disponible':
            raise ValidationError('Esta unidad ya no está disponible para solicitar alquiler.')
        datos = self.cleaned_data
        if SolicitudAlquiler.objects.filter(unidad=unidad, estado='Aprobada', fecha_inicio__lte=datos['fecha_fin'], fecha_fin__gte=datos['fecha_inicio']).exists():
            raise ValidationError('La unidad ya tiene una solicitud aprobada para esas fechas.')
        if SolicitudAlquiler.objects.filter(unidad=unidad, cliente=cliente, estado='Pendiente', fecha_inicio=datos['fecha_inicio'], fecha_fin=datos['fecha_fin']).exists():
            raise ValidationError('Ya tienes una solicitud pendiente para esta unidad y estas fechas.')
        solicitud = SolicitudAlquiler(cliente=cliente, unidad=unidad, **datos)
        solicitud.full_clean()
        solicitud.save()
        return solicitud


class FechaMovimientoField(forms.DateTimeField):
    """datetime-local usa la zona del negocio sin cambiar la configuración global."""
    zona = ZoneInfo('America/Santo_Domingo')

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', forms.DateTimeInput(
            format='%Y-%m-%dT%H:%M', attrs={'type': 'datetime-local'},
        ))
        kwargs.setdefault('input_formats', ('%Y-%m-%dT%H:%M', '%Y-%m-%dT%H:%M:%S'))
        super().__init__(*args, **kwargs)

    def to_python(self, value):
        with timezone.override(self.zona):
            return super().to_python(value)

    def prepare_value(self, value):
        with timezone.override(self.zona):
            return super().prepare_value(value)


class SalidaMaquinariaForm(forms.Form):
    fecha_salida = FechaMovimientoField(label='Fecha y hora de salida (Santo Domingo)', initial=timezone.now)


class RetornoMaquinariaForm(forms.Form):
    fecha_retorno = FechaMovimientoField(label='Fecha y hora de retorno (Santo Domingo)', initial=timezone.now)
