from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone


class Paciente(models.Model):
    class Tipo(models.TextChoices):
        ESTUDIANTE = "estudiante", "Estudiante"
        DOCENTE = "docente", "Docente"

    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    dni = models.CharField("DNI", max_length=8, unique=True, validators=[
        RegexValidator(r"^[0-9]{8}$", "El DNI debe tener ocho dígitos."),
    ])
    nombres = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=100)
    fecha_nacimiento = models.DateField("fecha de nacimiento")
    tipo = models.CharField(max_length=10, choices=Tipo)
    codigo_uncp = models.CharField("código UNCP", max_length=18, unique=True)
    email = models.EmailField("correo institucional")
    alergias = models.TextField(blank=True, max_length=500)

    class Meta:
        ordering = ("apellidos", "nombres")

    def __str__(self):
        return f"{self.nombres} {self.apellidos}"

    def clean(self):
        errores = {}
        if self.fecha_nacimiento and self.fecha_nacimiento > timezone.localdate():
            errores["fecha_nacimiento"] = "La fecha de nacimiento no puede ser futura."
        if self.tipo == self.Tipo.ESTUDIANTE and self.email.lower().rpartition("@")[2] != "uncp.edu.pe":
            errores["email"] = "Ingresa un correo @uncp.edu.pe para el estudiante."
        if errores:
            raise ValidationError(errores)

    @property
    def edad(self):
        hoy = timezone.localdate()
        nacimiento = self.fecha_nacimiento
        return hoy.year - nacimiento.year - ((hoy.month, hoy.day) < (nacimiento.month, nacimiento.day))


class Medico(models.Model):
    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    cmp = models.CharField("CMP", max_length=7, unique=True, validators=[
        RegexValidator(r"^[0-9]{5,7}$", "El CMP debe tener de cinco a siete dígitos."),
    ])
    especialidad = models.CharField(max_length=90)
    consultorio = models.CharField(max_length=60)

    class Meta:
        verbose_name = "médico"
        verbose_name_plural = "médicos"
        ordering = ("especialidad", "usuario__last_name", "usuario__first_name")

    def __str__(self):
        return f"{self.usuario.get_full_name() or self.usuario.username} · {self.especialidad}"


class HorarioMedico(models.Model):
    class Dia(models.IntegerChoices):
        LUNES = 0, "Lunes"
        MARTES = 1, "Martes"
        MIERCOLES = 2, "Miércoles"
        JUEVES = 3, "Jueves"
        VIERNES = 4, "Viernes"
        SABADO = 5, "Sábado"

    medico = models.ForeignKey(Medico, on_delete=models.CASCADE, related_name="horarios")
    dia = models.PositiveSmallIntegerField("día", choices=Dia)
    inicio = models.TimeField()
    fin = models.TimeField()

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(fin__gt=models.F("inicio")), name="horario_en_orden"),
            models.UniqueConstraint(fields=("medico", "dia", "inicio"), name="horario_inicio_unico"),
        ]


class Cita(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        COMPLETADA = "completada", "Completada"
        CANCELADA = "cancelada", "Cancelada"

    paciente = models.ForeignKey(Paciente, on_delete=models.PROTECT, related_name="citas")
    medico = models.ForeignKey(Medico, on_delete=models.PROTECT, related_name="citas")
    inicio = models.DateTimeField("fecha y hora de cita")
    fin = models.DateTimeField()
    dia = models.DateField("día local")
    motivo = models.TextField(max_length=1000)
    estado = models.CharField(max_length=10, choices=Estado, default=Estado.PENDIENTE)

    class Meta:
        ordering = ("inicio",)
        constraints = [
            models.CheckConstraint(condition=models.Q(fin__gt=models.F("inicio")), name="cita_en_orden"),
            models.UniqueConstraint(
                fields=("paciente", "dia"), condition=~models.Q(estado="cancelada"),
                name="cita_unica_paciente_dia",
            ),
            models.UniqueConstraint(
                fields=("medico", "inicio"), condition=~models.Q(estado="cancelada"),
                name="cita_unica_medico_inicio",
            ),
        ]
        permissions = [
            ("agendar_cita", "Puede agendar citas"),
            ("cancelar_cita", "Puede cancelar citas"),
            ("generar_reportes", "Puede generar reportes de consultas"),
        ]

    def __str__(self):
        return f"{self.paciente} · {timezone.localtime(self.inicio):%d/%m/%Y %H:%M}"


class Consulta(models.Model):
    cita = models.OneToOneField(Cita, on_delete=models.PROTECT, related_name="consulta")
    diagnostico = models.TextField("diagnóstico", max_length=2000)
    tratamiento = models.TextField(max_length=2000)
    medicamentos = models.TextField(max_length=2000, blank=True)
    fecha_control = models.DateField("próximo control", blank=True, null=True)
    adjuntos_simulados = models.TextField("referencia de recetas o exámenes", max_length=800, blank=True)
    registrada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        permissions = [("ver_historial_clinico", "Puede ver el historial clínico")]
        ordering = ("-registrada_en",)


class NotaConsulta(models.Model):
    consulta = models.ForeignKey(Consulta, on_delete=models.PROTECT, related_name="notas")
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    texto = models.TextField(max_length=2000)
    registrada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("registrada_en",)
