from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.db.models import F
from django.utils import timezone

from cuentas.horarios import validar_horario_cita

from .models import Cita, HorarioMedico, Medico, Paciente


DURACION_CITA = timedelta(minutes=30)


def datos_horario(inicio):
    validar_horario_cita(inicio)
    fin = inicio + DURACION_CITA
    # La última fracción de la cita también debe estar dentro del horario.
    validar_horario_cita(fin - timedelta(microseconds=1))
    return timezone.localdate(inicio), fin


def validar_cita(paciente, medico, inicio):
    try:
        dia, fin = datos_horario(inicio)
    except ValidationError as error:
        raise ValidationError({"inicio": error.messages}) from error

    errores = {}
    citas = Cita.objects.exclude(estado=Cita.Estado.CANCELADA)
    if paciente and citas.filter(paciente=paciente, dia=dia).exists():
        errores["inicio"] = "Este paciente ya tiene una cita ese día."

    if medico:
        local = timezone.localtime(inicio)
        if not HorarioMedico.objects.filter(
            medico=medico, dia=local.weekday(),
            inicio__lte=local.time(), fin__gte=timezone.localtime(fin).time(),
        ).exists():
            errores["medico"] = "El médico no atiende en el horario elegido."
        elif citas.filter(medico=medico, inicio__lt=fin, fin__gt=inicio).exists():
            errores["medico"] = "El médico ya tiene una cita que cruza este horario."

    if errores:
        raise ValidationError(errores)
    return dia, fin


@transaction.atomic
def crear_cita(*, paciente, medico, inicio, motivo):
    medicos = Medico.objects.filter(pk=medico.pk)
    if connection.vendor == "sqlite":
        medicos.update(consultorio=F("consultorio"))
    medico = medicos.select_for_update().get()
    Paciente.objects.select_for_update().get(pk=paciente.pk)
    dia, fin = validar_cita(paciente, medico, inicio)
    return Cita.objects.create(
        paciente=paciente, medico=medico, inicio=inicio, fin=fin, dia=dia, motivo=motivo,
    )
