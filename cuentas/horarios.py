from datetime import time

from django.core.exceptions import ValidationError
from django.utils import timezone


def validar_horario_cita(instante):
    if timezone.is_naive(instante):
        raise ValidationError("La fecha y hora debe incluir una zona horaria.")
    local = timezone.localtime(instante)
    dia = local.weekday()
    cierre = time(13) if dia == 5 else time(18)
    if dia == 6 or not time(8) <= local.time() < cierre:
        raise ValidationError(
            "Atendemos de lunes a viernes de 8:00 a 18:00 y sábados de 8:00 a 13:00."
        )
