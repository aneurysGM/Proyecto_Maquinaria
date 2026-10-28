from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.functions import Replace
from django.utils import timezone

from .validators import ESPACIOS_CEDULA, anio_actual, validar_cedula


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


def expresion_cedula_normalizada():
    expresion = models.F('cedula')
    for separador in '-' + ESPACIOS_CEDULA:
        expresion = Replace(expresion, models.Value(separador), models.Value(''))
    return expresion


class Operador(models.Model):
    """Registro de operadores en el sistema."""

    id = models.AutoField(primary_key=True, db_column='IdOperador')
    cedula = models.CharField(max_length=20, unique=True, db_column='Cedula', validators=[validar_cedula])
    cedula_normalizada = models.GeneratedField(
        expression=expresion_cedula_normalizada(),
        output_field=models.CharField(max_length=20), db_persist=True,
        unique=True, db_column='CedulaNormalizada',
    )
    nombre = models.CharField(max_length=80, db_column='Nombre')
    apellido = models.CharField(max_length=80, blank=True, default='', db_column='Apellido')
    telefono = models.CharField(max_length=20, blank=True, null=True, db_column='Telefono')
    email = models.EmailField(max_length=100, blank=True, null=True, db_column='Email')
    direccion = models.CharField(max_length=200, blank=True, null=True, db_column='Direccion')
    fecha_nacimiento = models.DateField(blank=True, null=True, db_column='FechaNacimiento')
    fecha_contratacion = models.DateField(blank=True, null=True, db_column='FechaContratacion')
    numero_licencia = models.CharField(max_length=30, blank=True, null=True, db_column='NumeroLicencia')
    tipo_licencia = models.CharField(max_length=10, blank=True, null=True, db_column='CategoriaLicencia')
    fecha_vencimiento = models.DateField(blank=True, null=True, db_column='FechaVencimientoLicencia')
    estado = models.CharField(max_length=20, default='Activo', db_column='Estado')
    fecha_creacion = models.DateTimeField(default=timezone.now, editable=False, db_column='FechaCreacion')

    class Meta:
        db_table = 'Operador'
        ordering = ('nombre', 'apellido', 'id')

    @property
    def nombre_completo(self):
        return f'{self.nombre} {self.apellido}'.strip()

    @property
    def activo(self):
        return self.estado == 'Activo'

    def __str__(self):
        return self.nombre_completo