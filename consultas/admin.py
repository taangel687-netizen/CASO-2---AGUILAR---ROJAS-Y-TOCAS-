from django.contrib import admin
from django.db import transaction
from django.db.models import Count, Max, Q
from django.utils import timezone

from cuentas.auditoria import auditar_operacion

from .models import Cita, HorarioMedico, Medico, Paciente


class HorarioInline(admin.TabularInline):
    model = HorarioMedico
    extra = 1


@admin.register(Medico)
class MedicoAdmin(admin.ModelAdmin):
    list_display = ("__str__", "cmp", "consultorio", "total_citas", "total_consultas")
    list_filter = ("especialidad",)
    search_fields = ("cmp", "usuario__first_name", "usuario__last_name", "especialidad")
    list_select_related = ("usuario",)
    inlines = (HorarioInline,)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            citas_activas=Count("citas", filter=~Q(citas__estado=Cita.Estado.CANCELADA)),
            consultas_registradas=Count("citas__consulta"),
        )

    @admin.display(description="Citas", ordering="citas_activas")
    def total_citas(self, medico):
        return medico.citas_activas

    @admin.display(description="Consultas registradas", ordering="consultas_registradas")
    def total_consultas(self, medico):
        return medico.consultas_registradas


@admin.register(Paciente)
class PacienteAdmin(admin.ModelAdmin):
    exclude = ("alergias",)
    list_display = ("dni", "nombres", "apellidos", "tipo", "edad", "total_citas", "dias_sin_consulta")
    list_filter = ("tipo",)
    search_fields = ("dni", "nombres", "apellidos")

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            citas_activas=Count("citas", filter=~Q(citas__estado=Cita.Estado.CANCELADA)),
            ultima_atencion=Max("citas__consulta__registrada_en"),
        )

    @admin.display(description="Citas", ordering="citas_activas")
    def total_citas(self, paciente):
        return paciente.citas_activas

    @admin.display(description="Días desde la última consulta", empty_value="Sin consultas")
    def dias_sin_consulta(self, paciente):
        if paciente.ultima_atencion:
            return (timezone.localdate() - timezone.localdate(paciente.ultima_atencion)).days
        return None


@admin.register(Cita)
class CitaAdmin(admin.ModelAdmin):
    fields = ("paciente", "medico", "inicio", "fin", "estado")
    list_display = ("inicio", "medico", "paciente", "estado")
    list_select_related = ("medico__usuario", "paciente")
    list_filter = ("dia", "medico", "medico__especialidad", "estado")
    search_fields = ("paciente__dni", "paciente__nombres", "paciente__apellidos")
    date_hierarchy = "dia"
    actions = ("completar_citas",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_completar_permission(self, request):
        return request.user.has_perm("consultas.change_cita")

    @admin.action(description="Marcar citas como completadas", permissions=["completar"])
    @transaction.atomic
    def completar_citas(self, request, queryset):
        pendientes = queryset.filter(estado=Cita.Estado.PENDIENTE)
        completadas = 0
        for cita_id in pendientes.values_list("pk", flat=True):
            if pendientes.filter(pk=cita_id).update(estado=Cita.Estado.COMPLETADA):
                auditar_operacion(request, "cita_completada", "cita", cita_id)
                completadas += 1
        self.message_user(request, f"Citas completadas: {completadas}.")
