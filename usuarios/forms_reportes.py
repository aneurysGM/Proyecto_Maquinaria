from django import forms
from django.contrib.auth import get_user_model

from .models import Mantenimiento, SolicitudAlquiler, Unidad


class PeriodoReporteForm(forms.Form):
    desde = forms.DateField(
        label='Desde', required=False, input_formats=('%Y-%m-%d',),
        widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
    )
    hasta = forms.DateField(
        label='Hasta', required=False, input_formats=('%Y-%m-%d',),
        widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
    )

    def clean(self):
        datos = super().clean()
        desde, hasta = datos.get('desde'), datos.get('hasta')
        if desde and hasta and hasta < desde:
            raise forms.ValidationError('La fecha Hasta debe ser igual o posterior a Desde.')
        return datos


class MaquinariaReporteForm(forms.Form):
    q = forms.CharField(label='Búsqueda', max_length=200, required=False, help_text='Código, nombre, serie o ubicación.')
    estado = forms.ChoiceField(label='Estado', required=False, choices=[('', 'Todos'), *Unidad.ESTADOS])


class ClienteReporteChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, usuario):
        nombre = usuario.get_full_name()
        return f'{nombre} ({usuario.username})' if nombre else usuario.username


class SolicitudesReporteForm(PeriodoReporteForm):
    estado = forms.ChoiceField(label='Estado', required=False, choices=[('', 'Todos'), *SolicitudAlquiler.ESTADOS])
    cliente = ClienteReporteChoiceField(label='Cliente', required=False, queryset=get_user_model().objects.none(), empty_label='Todos')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Mantener seleccionables clientes históricos aunque cambien de rol o se desactiven.
        self.fields['cliente'].queryset = get_user_model().objects.filter(
            solicitudes_alquiler__isnull=False,
        ).distinct().order_by('username')


class EntregasReporteForm(PeriodoReporteForm):
    situacion = forms.ChoiceField(
        label='Situación', required=False,
        choices=[('', 'Todas'), ('pendiente', 'Pendiente de devolución'), ('devuelta', 'Devuelta')],
    )


class MantenimientosReporteForm(PeriodoReporteForm):
    unidad = forms.ModelChoiceField(label='Unidad', required=False, queryset=Unidad.objects.none(), empty_label='Todas')
    tipo = forms.ChoiceField(label='Tipo', required=False, choices=[('', 'Todos'), *Mantenimiento.TIPOS])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['unidad'].queryset = Unidad.objects.select_related('maquinaria').order_by('maquinaria__codigo', 'numero_serie')
