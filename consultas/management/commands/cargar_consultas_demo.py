from datetime import date, datetime, time, timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from consultas.models import Cita, Consulta, HorarioMedico, Medico, Paciente


ESPECIALIDADES = (
    "Medicina general", "Odontología", "Nutrición", "Medicina general",
    "Oftalmología", "Odontología", "Nutrición", "Oftalmología",
)


def cuenta_demo(alias, rol, nombre):
    usuario, creado = get_user_model().objects.get_or_create(
        username=f"{alias}@uncp.edu.pe",
        defaults={"first_name": nombre, "email": f"{alias}@example.test", "is_staff": rol == "admin"},
    )
    if creado:
        usuario.set_unusable_password()
        usuario.save(update_fields=["password"])
    grupo, _ = Group.objects.get_or_create(name=settings.CASO.roles[rol])
    usuario.groups.add(grupo)
    return usuario


class Command(BaseCommand):
    help = "Carga 8 médicos, 15 pacientes y 30 citas ficticias."

    @transaction.atomic
    def handle(self, *args, **options):
        cuenta_demo("demo-centro-admin", "admin", "Dirección de prueba")
        cuenta_demo("demo-centro-recepcion", "recepcionista", "Recepción de prueba")
        medicos = []
        for indice, especialidad in enumerate(ESPECIALIDADES, start=1):
            usuario = cuenta_demo(f"demo-medico-{indice:02d}", "medico", f"Médico de prueba {indice}")
            medico, _ = Medico.objects.get_or_create(usuario=usuario, defaults={
                "cmp": f"90{indice:03d}", "especialidad": especialidad,
                "consultorio": f"Consultorio {indice:02d}",
            })
            for dia in range(6):
                HorarioMedico.objects.get_or_create(
                    medico=medico, dia=dia, inicio=time(8),
                    defaults={"fin": time(13) if dia == 5 else time(18)},
                )
            medicos.append(medico)

        hoy = timezone.localdate()
        lunes = hoy + timedelta(days=7 - hoy.weekday())
        for indice in range(15):
            numero = indice + 1
            alias = f"demo-paciente-{numero:02d}"
            usuario = cuenta_demo(alias, "paciente", f"Paciente de prueba {numero}")
            paciente, _ = Paciente.objects.get_or_create(usuario=usuario, defaults={
                "dni": f"97{numero:06d}", "nombres": f"Paciente {numero}", "apellidos": "Demostración",
                "fecha_nacimiento": date(2002, 1, numero), "tipo": Paciente.Tipo.ESTUDIANTE,
                "codigo_uncp": f"DEMO-{numero:03d}", "email": f"{alias}@uncp.edu.pe",
            })
            medico = medicos[indice % len(medicos)]
            for turno in range(2):
                completada = turno == 0 and numero <= 5
                dia = lunes + timedelta(days=indice // 8 + (turno * 7) - (14 if completada else 0))
                inicio = timezone.make_aware(datetime.combine(dia, time(9)))
                cita, _ = Cita.objects.get_or_create(
                    paciente=paciente, motivo=f"Consulta ficticia de demostración {turno + 1}.",
                    defaults={
                        "medico": medico, "dia": dia, "inicio": inicio, "fin": inicio + timedelta(minutes=30),
                        "estado": Cita.Estado.COMPLETADA if completada else Cita.Estado.PENDIENTE,
                    },
                )
                if cita.estado == Cita.Estado.COMPLETADA:
                    Consulta.objects.get_or_create(cita=cita, defaults={
                        "diagnostico": "Diagnóstico ficticio para demostrar el historial.",
                        "tratamiento": "Registro de prueba sin indicaciones clínicas.",
                    })

        self.stdout.write(self.style.SUCCESS("Datos ficticios de consultas listos."))
