from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST, require_safe

from cuentas.auditoria import auditar_operacion, marcar_acceso_historial
from cuentas.middleware import controla_horario
from cuentas.permisos import agendar_cita, cancelar_cita, generar_reportes, requiere_rol, roles_usuario

from .forms import CitaForm, ConsultaForm, NotaForm, PacienteForm
from .models import Cita, Consulta, Paciente
from .servicios import crear_cita, datos_horario


def validar_horario_request(request):
    if roles_usuario(request.user).isdisjoint({"paciente", "recepcionista"}):
        return
    try:
        inicio = CitaForm.base_fields["inicio"].clean(request.POST.get("inicio"))
    except ValidationError:
        return
    datos_horario(inicio)


@require_safe
@never_cache
@requiere_rol("paciente", "medico", "recepcionista", "admin")
def agenda(request):
    roles = roles_usuario(request.user)
    citas = Cita.objects.select_related("medico__usuario", "paciente", "consulta")
    if not roles & {"recepcionista", "admin"}:
        if "medico" in roles:
            citas = citas.filter(medico__usuario=request.user)
        else:
            citas = citas.filter(paciente__usuario=request.user)
    return render(request, "consultas/agenda.html", {"citas": citas, "roles": roles})


@require_http_methods(["GET", "POST"])
@never_cache
@requiere_rol("paciente", "recepcionista")
@controla_horario(validar_horario_request)
def agendar(request):
    recepcion = "recepcionista" in roles_usuario(request.user)
    paciente = None if recepcion else get_object_or_404(Paciente, usuario=request.user)
    especialidad = request.GET.get("especialidad", "").strip()
    datos = request.POST if request.method == "POST" else None
    form = CitaForm(datos, paciente=paciente, especialidad=especialidad)
    if request.method == "POST" and form.is_valid():
        datos = form.cleaned_data.copy()
        datos.setdefault("paciente", paciente)
        agendar_cita(request.user, datos["paciente"].usuario_id)
        try:
            with transaction.atomic():
                cita = crear_cita(**datos)
                auditar_operacion(request, "cita_agendada", "cita", cita.pk)
        except ValidationError as error:
            for campo, errores in error.error_dict.items():
                form.add_error(campo, errores)
        else:
            messages.success(request, "La cita quedó agendada.")
            return redirect("consultas:agenda")
    return render(request, "consultas/formulario.html", {
        "form": form, "titulo": "Agendar cita", "filtrar": True, "especialidad": especialidad,
    })


@require_POST
@requiere_rol("paciente", "medico", "recepcionista")
def cancelar(request, cita_id):
    cita = get_object_or_404(Cita, pk=cita_id)
    cancelar_cita(request.user, cita.paciente.usuario_id)
    with transaction.atomic():
        cambios = Cita.objects.filter(pk=cita.pk, estado=Cita.Estado.PENDIENTE).update(
            estado=Cita.Estado.CANCELADA,
        )
        if cambios:
            auditar_operacion(request, "cita_cancelada", "cita", cita.pk)
    if cambios:
        messages.success(request, "La cita quedó cancelada.")
    else:
        messages.warning(request, "Solo se pueden cancelar las citas pendientes.")
    return redirect("consultas:agenda")


@require_safe
@never_cache
@requiere_rol("medico", "paciente")
def historial(request, paciente_id=None):
    if paciente_id is None:
        paciente = get_object_or_404(Paciente, usuario=request.user)
    else:
        paciente = get_object_or_404(Paciente, pk=paciente_id)
    marcar_acceso_historial(request, paciente.usuario_id, paciente.pk)
    consultas = Consulta.objects.filter(cita__paciente=paciente).select_related(
        "cita__medico__usuario",
    ).prefetch_related("notas")
    return render(request, "consultas/historial.html", {"paciente": paciente, "consultas": consultas})


@require_http_methods(["GET", "POST"])
@never_cache
@requiere_rol("medico")
def registrar_consulta(request, cita_id):
    cita = get_object_or_404(Cita.objects.select_related("medico", "paciente"), pk=cita_id)
    if cita.medico.usuario_id != request.user.pk:
        raise PermissionDenied
    if cita.estado == Cita.Estado.CANCELADA or hasattr(cita, "consulta"):
        messages.warning(request, "Esta cita ya no admite un nuevo registro de atención.")
        return redirect("consultas:agenda")

    form = ConsultaForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            actualizada = Cita.objects.filter(pk=cita.pk).exclude(
                estado=Cita.Estado.CANCELADA,
            ).update(estado=Cita.Estado.COMPLETADA)
            if actualizada:
                consulta, creada = Consulta.objects.get_or_create(cita=cita, defaults=form.cleaned_data)
                if creada:
                    auditar_operacion(request, "consulta_registrada", "consulta", consulta.pk)
                    messages.success(request, "La consulta quedó registrada.")
        return redirect("consultas:agenda")
    return render(request, "consultas/formulario.html", {"form": form, "titulo": "Registrar consulta"})


@require_http_methods(["GET", "POST"])
@never_cache
@requiere_rol("medico")
def agregar_nota(request, consulta_id):
    consulta = get_object_or_404(Consulta.objects.select_related("cita__medico"), pk=consulta_id)
    if consulta.cita.medico.usuario_id != request.user.pk:
        raise PermissionDenied
    form = NotaForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            nota = form.save(commit=False)
            nota.autor = request.user
            nota.consulta = consulta
            nota.save()
            auditar_operacion(request, "nota_agregada", "consulta", consulta.pk)
        messages.success(request, "La nota quedó registrada.")
        return redirect("consultas:historial-paciente", paciente_id=consulta.cita.paciente_id)
    return render(request, "consultas/formulario.html", {"form": form, "titulo": "Agregar nota"})


@require_http_methods(["GET", "POST"])
@never_cache
@requiere_rol("recepcionista")
def registrar_paciente(request):
    form = PacienteForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            paciente = form.save()
            auditar_operacion(request, "paciente_registrado", "paciente", paciente.pk)
        messages.success(request, "El paciente quedó registrado.")
        return redirect("consultas:agenda")
    return render(request, "consultas/formulario.html", {"form": form, "titulo": "Registrar paciente"})


@require_safe
@requiere_rol("admin")
def reportes(request):
    generar_reportes(request.user)
    citas = Cita.objects.exclude(estado=Cita.Estado.CANCELADA).order_by()
    return render(request, "consultas/reportes.html", {
        "especialidades": citas.values("medico__especialidad").annotate(total=Count("pk")).order_by("-total"),
        "medicos": citas.filter(consulta__isnull=False).values(
            "medico__usuario__first_name", "medico__usuario__last_name",
        ).annotate(total=Count("pk")).order_by("-total")[:10],
        "pacientes": citas.values("paciente__nombres", "paciente__apellidos").annotate(
            total=Count("pk"),
        ).order_by("-total")[:10],
    })
