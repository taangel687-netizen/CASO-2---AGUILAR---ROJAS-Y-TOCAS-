from datetime import datetime, time, timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from cuentas.models import EventoAuditoria

from .models import Cita, Medico, Paciente


class ConsultasTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("configurar_roles", stdout=StringIO())
        call_command("cargar_consultas_demo", stdout=StringIO())
        cls.pacientes = list(Paciente.objects.order_by("pk")[:2])
        cls.medico = Medico.objects.order_by("pk").first()

    def test_agenda_valida_conflictos_y_horario(self):
        paciente, otro = self.pacientes
        self.client.force_login(paciente.usuario)
        hoy = timezone.localdate()
        dia = hoy + timedelta(days=16 - hoy.weekday())
        datos = {
            "medico": self.medico.pk, "inicio": datetime.combine(dia, time(10)).isoformat(timespec="minutes"),
            "motivo": "Solicitud ficticia para verificar la agenda.",
        }
        ruta = reverse("consultas:agendar_cita")
        self.assertRedirects(self.client.post(ruta, datos), reverse("consultas:agenda"))
        self.assertContains(self.client.post(ruta, datos), "ya tiene una cita ese día")
        self.client.force_login(otro.usuario)
        self.assertContains(self.client.post(ruta, datos), "ya tiene una cita que cruza")
        datos["inicio"] = datetime.combine(dia, time(23)).isoformat(timespec="minutes")
        self.assertEqual(self.client.post(ruta, datos).status_code, 400)

    def test_historial_propio_y_auditado(self):
        paciente, otro = self.pacientes
        self.client.force_login(paciente.usuario)
        ruta_propia = reverse("consultas:historial")
        self.assertContains(self.client.get(ruta_propia), "Historial de")
        self.assertTrue(EventoAuditoria.objects.filter(
            usuario=paciente.usuario, accion="historial_consultado", recurso=f"historial:{paciente.pk}",
        ).exists())
        ruta_ajena = reverse("consultas:historial-paciente", args=[otro.pk])
        self.assertEqual(self.client.get(ruta_ajena).status_code, 403)

    def test_avisos_y_carga_repetible(self):
        call_command("cargar_consultas_demo", stdout=StringIO())
        self.assertEqual(Paciente.objects.count(), 15)
        self.assertEqual(Medico.objects.count(), 8)
        self.assertEqual(Cita.objects.count(), 30)
        usuario = get_user_model().objects.get(username="demo-medico-01@uncp.edu.pe")
        usuario.set_password("Clave-de-prueba-2026")
        usuario.save(update_fields=["password"])
        respuesta = self.client.post(reverse("ingreso"), {
            "username": usuario.username, "password": "Clave-de-prueba-2026",
        }, follow=True)
        self.assertContains(respuesta, "Tienes citas pendientes")
        self.assertContains(respuesta, "Mi agenda")
