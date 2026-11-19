from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.http import HttpResponse
from django.test import Client, TestCase, override_settings
from django.urls import path, reverse
from django.utils import timezone

from config.urls import urlpatterns as portal

from .auditoria import marcar_acceso_historial
from .horarios import validar_horario_cita
from .middleware import controla_horario
from .models import EventoAuditoria
from .permisos import (
    agendar_cita, cancelar_cita, generar_reportes, ver_historial_clinico,
)

CLAVE = "Clave-local-para-pruebas-81"
LIMA = ZoneInfo("America/Lima")


def cuenta(rol):
    correo = f"{rol}@{settings.CASO.dominio}"
    usuario = get_user_model().objects.create_user(correo, password=CLAVE)
    usuario.groups.add(Group.objects.get(name=settings.CASO.roles[rol]))
    return usuario


def aviso_prueba(usuario, ahora):
    return ("Tienes citas pendientes (2).",)


def validar_prueba(request):
    apertura = datetime(2026, 11, 21, 8, tzinfo=LIMA)
    horas = int(request.POST.get("horas", "0"))
    validar_horario_cita(apertura + timedelta(hours=horas))


@controla_horario(validar_prueba)
def operacion(request):
    return HttpResponse("Guardado")


def historial(request):
    titular = request.user.pk + int(request.GET.get("otro", "0"))
    marcar_acceso_historial(request, titular, 81)
    return HttpResponse("Historial de prueba")


urlpatterns = [*portal, path("prueba/horario/", operacion), path("prueba/historial/", historial)]


@override_settings(ROOT_URLCONF=__name__)
class PortalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("configurar_roles", verbosity=0)
        cls.usuario = cuenta("paciente")

    def ingresar(self, **extras):
        return self.client.post(reverse("ingreso"), {
            "username": self.usuario.username.upper(),
            "password": CLAVE,
            **extras,
        })

    def test_cookie_y_salida(self):
        respuesta = self.ingresar(next="https://otro.invalid/")
        self.assertRedirects(respuesta, reverse("panel"))
        cookie = respuesta.cookies[settings.SESSION_COOKIE_NAME]
        self.assertEqual(int(cookie["max-age"]), 1200)
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "Lax")
        self.assertEqual(self.client.get(reverse("salida")).status_code, 405)
        self.assertRedirects(self.client.post(reverse("salida")), reverse("inicio"))
        self.assertRedirects(self.client.get(reverse("panel")), "/ingresar/?next=/mi-cuenta/")

    def test_csrf_y_dominio(self):
        self.assertEqual(Client(enforce_csrf_checks=True).post(reverse("ingreso")).status_code, 403)
        self.assertContains(self.ingresar(username="usuario@otro.invalid"), "@uncp.edu.pe")

    def test_acceso_denegado_visible_en_bitacora(self):
        self.ingresar()
        self.assertEqual(self.client.get(reverse("auditoria")).status_code, 403)
        self.assertTrue(EventoAuditoria.objects.filter(
            accion="acceso_denegado", usuario=self.usuario, recurso="auditoria",
        ).exists())
        self.client.force_login(cuenta("admin"))
        self.assertContains(self.client.get(reverse("auditoria")), "acceso_denegado")

    def test_inactividad_y_bloqueo(self):
        self.ingresar()
        futuro = timezone.now() + timedelta(minutes=20)
        with patch("cuentas.middleware.timezone.now", return_value=futuro):
            self.assertRedirects(self.client.get(reverse("panel")), "/ingresar/?next=/mi-cuenta/")
        self.ingresar()
        get_user_model().objects.filter(pk=self.usuario.pk).update(is_active=False)
        self.assertRedirects(self.client.get(reverse("panel")), "/ingresar/?next=/mi-cuenta/")
        self.assertTrue(EventoAuditoria.objects.filter(
            accion="cuenta_desactivada", usuario=self.usuario,
        ).exists())

    @override_settings(AVISOS_INGRESO="cuentas.tests.aviso_prueba")
    def test_aviso_de_ingreso_una_vez(self):
        self.ingresar()
        self.assertContains(self.client.get(reverse("panel")), "Tienes citas pendientes (2).")
        self.assertNotContains(self.client.get(reverse("panel")), "Tienes citas pendientes (2).")

    def test_middleware_rechaza_post_fuera_de_horario(self):
        self.client.force_login(self.usuario)
        self.assertEqual(self.client.post("/prueba/horario/", {"horas": "0"}).status_code, 200)
        self.assertEqual(self.client.post("/prueba/horario/", {"horas": "5"}).status_code, 400)

    def test_paciente_solo_actua_sobre_su_ficha(self):
        for politica in (agendar_cita, cancelar_cita, ver_historial_clinico):
            politica(self.usuario, self.usuario.pk)
            with self.assertRaises(PermissionDenied):
                politica(self.usuario, self.usuario.pk + 1)

    def test_matriz_de_roles(self):
        medico = cuenta("medico")
        recepcion = cuenta("recepcionista")
        admin = cuenta("admin")
        ver_historial_clinico(medico, self.usuario.pk)
        cancelar_cita(medico, self.usuario.pk)
        agendar_cita(recepcion, self.usuario.pk)
        cancelar_cita(recepcion, self.usuario.pk)
        generar_reportes(admin)
        for politica, usuario in (
            (agendar_cita, medico), (ver_historial_clinico, recepcion),
            (ver_historial_clinico, admin),
        ):
            with self.assertRaises(PermissionDenied):
                politica(usuario, self.usuario.pk)
        with self.assertRaises(PermissionDenied):
            generar_reportes(medico)

    def test_historial_propio_auditado_una_vez(self):
        self.client.force_login(self.usuario)
        self.assertEqual(self.client.get("/prueba/historial/").status_code, 200)
        self.assertEqual(self.client.get("/prueba/historial/?otro=1").status_code, 403)
        eventos = EventoAuditoria.objects.filter(accion="historial_consultado")
        self.assertEqual(eventos.count(), 1)
        self.assertEqual(eventos.get().recurso, "historial:81")
