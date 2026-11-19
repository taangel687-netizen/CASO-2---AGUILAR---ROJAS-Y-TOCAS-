from functools import wraps

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def roles_usuario(usuario):
    if not usuario.is_authenticated or not usuario.is_active:
        return set()
    nombres = set(usuario.groups.values_list("name", flat=True))
    return {rol for rol, nombre in settings.CASO.roles.items() if nombre in nombres}


def exige_rol(usuario, *roles):
    if roles_usuario(usuario).isdisjoint(roles):
        raise PermissionDenied


def requiere_rol(*roles):
    def decorar(vista):
        @login_required
        @wraps(vista)
        def protegida(request, *args, **kwargs):
            exige_rol(request.user, *roles)
            return vista(request, *args, **kwargs)
        return protegida
    return decorar


def ver_historial_clinico(usuario, paciente_usuario_id):
    roles = roles_usuario(usuario)
    if "medico" not in roles and not ("paciente" in roles and usuario.pk == paciente_usuario_id):
        raise PermissionDenied


def agendar_cita(usuario, paciente_usuario_id):
    roles = roles_usuario(usuario)
    if "recepcionista" not in roles and not ("paciente" in roles and usuario.pk == paciente_usuario_id):
        raise PermissionDenied


def cancelar_cita(usuario, paciente_usuario_id):
    roles = roles_usuario(usuario)
    if not roles.intersection({"recepcionista", "medico"}) and not (
        "paciente" in roles and usuario.pk == paciente_usuario_id
    ):
        raise PermissionDenied


def generar_reportes(usuario):
    exige_rol(usuario, "admin")


def puede_auditar(usuario):
    return usuario.is_superuser or "admin" in roles_usuario(usuario)
