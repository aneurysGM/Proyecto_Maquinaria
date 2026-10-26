from django import forms
from django.core.validators import MaxValueValidator
from django.db import transaction
from django.utils import timezone

from .models import Categoria, Maquinaria, Unidad
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
