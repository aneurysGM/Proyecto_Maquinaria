from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from .validators import anio_actual


class Categoria(models.Model):
    id = models.AutoField(primary_key=True, db_column='CategoriaID')
    nombre = models.CharField(max_length=80, unique=True, db_column='Nombre')
    descripcion = models.CharField(
        max_length=200, blank=True, null=True, db_column='Descripcion'
    )

    class Meta:
        db_table = 'Categoria'
        ordering = ('nombre',)

    def __str__(self):
        return self.nombre


class Maquinaria(models.Model):
    id = models.AutoField(primary_key=True, db_column='EquipoID')
    categoria = models.ForeignKey(
        Categoria,
        models.PROTECT,
        db_column='CategoriaID',
        related_name='maquinarias',
    )
    codigo = models.CharField(max_length=20, unique=True, db_column='Codigo')
    nombre = models.CharField(max_length=120, db_column='Nombre')
    marca = models.CharField(max_length=60, blank=True, null=True, db_column='Marca')
    modelo = models.CharField(max_length=60, blank=True, null=True, db_column='Modelo')
    costo_adquisicion = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        validators=(MinValueValidator(0),),
        db_column='CostoAdquisicion',
    )
    tarifa_diaria = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        validators=(MinValueValidator(0.01),),
        db_column='TarifaDiaria',
    )
    tarifa_semanal = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        validators=(MinValueValidator(0.01),),
        db_column='TarifaSemanal',
    )
    tarifa_mensual = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        validators=(MinValueValidator(0.01),),
        db_column='TarifaMensual',
    )
    deposito_garantia = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=0,
        validators=(MinValueValidator(0),),
        db_column='DepositoGarantia',
    )
    activo = models.BooleanField(default=True, db_column='Activo')

    fecha_modificacion = models.DateTimeField(
        blank=True, null=True, editable=False, db_column='FechaModificacion'
    )

    class Meta:
        db_table = 'Maquinaria'
        ordering = ('codigo',)
        constraints = (
            models.CheckConstraint(
                condition=models.Q(costo_adquisicion__gte=0),
                name='CK_Maquinaria_Costo_NoNegativo',
            ),
            models.CheckConstraint(
                condition=models.Q(tarifa_diaria__gt=0),
                name='CK_Maquinaria_TarifaDiaria_Positiva',
            ),
            models.CheckConstraint(
                condition=models.Q(tarifa_semanal__gt=0),
                name='CK_Maquinaria_TarifaSemanal_Positiva',
            ),
            models.CheckConstraint(
                condition=models.Q(tarifa_mensual__gt=0),
                name='CK_Maquinaria_TarifaMensual_Positiva',
            ),
            models.CheckConstraint(
                condition=models.Q(deposito_garantia__gte=0),
                name='CK_Maquinaria_Deposito_NoNegativo',
            ),
        )

    def __str__(self):
        return f'{self.codigo} - {self.nombre}'


class Unidad(models.Model):
    ESTADOS = (
        ('Disponible', 'Disponible'),
        ('Alquilado', 'Alquilado'),
        ('Mantenimiento', 'En mantenimiento'),
        ('Baja', 'Fuera de servicio'),
    )

    id = models.AutoField(primary_key=True, db_column='UnidadID')
    maquinaria = models.ForeignKey(
        Maquinaria,
        models.PROTECT,
        db_column='EquipoID',
        related_name='unidades',
    )
    numero_serie = models.CharField(
        max_length=50, unique=True, db_column='NumeroSerie'
    )
    estado = models.CharField(
        max_length=20, choices=ESTADOS, default='Disponible', db_column='Estado'
    )
    horas_uso = models.DecimalField(
        max_digits=10,
        decimal_places=1,
        default=0,
        validators=(MinValueValidator(0),),
        db_column='HorasUso',
    )
    fecha_adquisicion = models.DateField(
        blank=True, null=True, db_column='FechaAdquisicion'
    )
    activo = models.BooleanField(default=True, db_column='Activo')
    ubicacion_actual = models.CharField(
        max_length=200, blank=True, null=True, db_column='UbicacionActual'
    )
    anio_fabricacion = models.PositiveSmallIntegerField(
        'año de fabricación',
        blank=True,
        null=True,
        db_column='AnioFabricacion',
        validators=(MinValueValidator(1), MaxValueValidator(anio_actual)),
    )
    identificador_legacy = models.UUIDField(
        blank=True, null=True, unique=True, db_column='IdentificadorLegacy'
    )

    fecha_modificacion = models.DateTimeField(
        blank=True, null=True, editable=False, db_column='FechaModificacion'
    )

    class Meta:
        db_table = 'Unidad'
        ordering = ('maquinaria__codigo', 'numero_serie')
        constraints = (
            models.CheckConstraint(
                condition=models.Q(
                    estado__in=['Disponible', 'Alquilado', 'Mantenimiento', 'Baja']
                ),
                name='CK_Unidad_Estado_Valido',
            ),
            models.CheckConstraint(
                condition=models.Q(horas_uso__gte=0),
                name='CK_Unidad_Horas_NoNegativas',
            ),
        )

    def __str__(self):
        return f'{self.maquinaria.codigo} / {self.numero_serie}'

    def clean(self):
        super().clean()
        if self._state.adding and not (self.ubicacion_actual or '').strip():
            raise ValidationError({
                'ubicacion_actual': 'La ubicación actual es obligatoria en registros nuevos.'
            })
        if self.pk and self.estado != 'Alquilado' and self.solicitudes_alquiler.filter(
            fecha_salida__isnull=False, fecha_retorno__isnull=True,
        ).exists():
            raise ValidationError({'estado': 'La unidad tiene una entrega pendiente. Registra su retorno para cambiar el estado.'})

    @property
    def codigo(self):
        return self.maquinaria.codigo

    @property
    def nombre(self):
        return self.maquinaria.nombre

    @property
    def categoria(self):
        return self.maquinaria.categoria.nombre

    @property
    def marca(self):
        return self.maquinaria.marca

    @property
    def modelo(self):
        return self.maquinaria.modelo

    @property
    def costo_adquisicion(self):
        return self.maquinaria.costo_adquisicion

    @property
    def tarifa_diaria(self):
        return self.maquinaria.tarifa_diaria

    @property
    def tarifa_semanal(self):
        return self.maquinaria.tarifa_semanal

    @property
    def tarifa_mensual(self):
        return self.maquinaria.tarifa_mensual

    @property
    def deposito_garantia(self):
        return self.maquinaria.deposito_garantia



class Mantenimiento(models.Model):
    TIPOS = (('Preventivo', 'Preventivo'), ('Correctivo', 'Correctivo'))

    id = models.AutoField(primary_key=True, db_column='MantenimientoID')
    unidad = models.ForeignKey(
        Unidad, models.PROTECT, db_column='UnidadID', related_name='mantenimientos',
    )
    fecha = models.DateField(db_column='FechaInicio')
    # Se conserva la columna legacy, sin implementar un proceso de cierre.
    fecha_fin = models.DateField(null=True, blank=True, editable=False, db_column='FechaFin')
    tipo = models.CharField(max_length=12, choices=TIPOS, db_column='Tipo')
    descripcion = models.CharField(max_length=300, null=True, blank=True, db_column='Descripcion')
    costo = models.DecimalField(
        max_digits=18, decimal_places=2, validators=[MinValueValidator(0)], db_column='Costo',
    )
    tecnico = models.ForeignKey(
        settings.AUTH_USER_MODEL, models.PROTECT, null=True, blank=True, editable=False,
        db_column='TecnicoResponsableID', related_name='mantenimientos_registrados',
    )

    class Meta:
        db_table = 'Mantenimiento'
        ordering = ('-fecha', '-id')
        constraints = (
            models.CheckConstraint(condition=models.Q(costo__gte=0), name='CK_Mantenimiento_Costo_NoNegativo'),
            models.CheckConstraint(
                condition=models.Q(tipo__in=['Preventivo', 'Correctivo']),
                name='CK_Mantenimiento_Tipo_Valido',
            ),
        )

    def clean(self):
        super().clean()
        if self._state.adding:
            errores = {}
            if not (self.descripcion or '').strip():
                errores['descripcion'] = 'La descripción es obligatoria en registros nuevos.'
            if self.tecnico_id is None:
                errores['tecnico'] = 'El técnico responsable es obligatorio en registros nuevos.'
            if errores:
                raise ValidationError(errores)

    def __str__(self):
        return f'{self.unidad} · {self.fecha} · {self.tipo}'


class SolicitudAlquiler(models.Model):
    ESTADOS = [('Pendiente', 'Pendiente'), ('Aprobada', 'Aprobada'), ('Rechazada', 'Rechazada')]
    cliente = models.ForeignKey(settings.AUTH_USER_MODEL, models.PROTECT, related_name='solicitudes_alquiler')
    unidad = models.ForeignKey(Unidad, models.PROTECT, related_name='solicitudes_alquiler')
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    comentario = models.CharField(max_length=500, blank=True)
    estado = models.CharField(max_length=10, choices=ESTADOS, default='Pendiente', editable=False)
    fecha_creacion = models.DateTimeField(default=timezone.now, editable=False)
    revisado_por = models.ForeignKey(settings.AUTH_USER_MODEL, models.PROTECT, null=True, blank=True, related_name='solicitudes_revisadas', editable=False)
    fecha_revision = models.DateTimeField(null=True, blank=True, editable=False)
    fecha_salida = models.DateTimeField(null=True, blank=True, editable=False)
    entregado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, models.PROTECT, null=True, blank=True, editable=False,
        related_name='salidas_registradas',
    )
    fecha_retorno = models.DateTimeField(null=True, blank=True, editable=False)
    recibido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, models.PROTECT, null=True, blank=True, editable=False,
        related_name='retornos_registrados',
    )

    @property
    def estado_entrega(self):
        if self.fecha_retorno is not None:
            return 'Devuelta'
        return 'Pendiente de devolución' if self.fecha_salida is not None else 'Sin entregar'

    class Meta:
        ordering = ('-fecha_creacion', '-id')
        constraints = [
            models.CheckConstraint(condition=models.Q(fecha_fin__gte=models.F('fecha_inicio')), name='CK_Solicitud_Fechas'),
            models.CheckConstraint(condition=models.Q(estado__in=['Pendiente', 'Aprobada', 'Rechazada']), name='CK_Solicitud_Estado'),
            models.CheckConstraint(
                condition=(
                    models.Q(fecha_salida__isnull=True, entregado_por__isnull=True)
                    | models.Q(fecha_salida__isnull=False, entregado_por__isnull=False, estado='Aprobada')
                ), name='CK_Solicitud_Salida',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(fecha_retorno__isnull=True, recibido_por__isnull=True)
                    | models.Q(
                        fecha_retorno__isnull=False, recibido_por__isnull=False,
                        fecha_salida__isnull=False, fecha_retorno__gte=models.F('fecha_salida'),
                    )
                ), name='CK_Solicitud_Retorno',
            ),
            models.UniqueConstraint(
                fields=['unidad'],
                condition=models.Q(fecha_salida__isnull=False, fecha_retorno__isnull=True),
                name='UQ_Entrega_Unidad_Pendiente',
            ),
        ]
