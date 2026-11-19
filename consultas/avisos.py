from cuentas.avisos import citas_pendientes

from .models import Cita


def avisos_ingreso(usuario, ahora):
    pendientes = Cita.objects.filter(
        medico__usuario=usuario, estado=Cita.Estado.PENDIENTE, fin__gte=ahora,
    )
    return citas_pendientes(usuario, pendientes)
