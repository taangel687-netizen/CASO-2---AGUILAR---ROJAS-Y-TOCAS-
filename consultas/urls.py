from django.urls import path

from . import views

app_name = "consultas"
urlpatterns = [
    path("", views.agenda, name="agenda"),
    path("mis-citas/", views.agenda, name="mis_citas"),
    path("agendar/", views.agendar, name="agendar_cita"),
    path("reportes/", views.reportes, name="reportes"),
    path("citas/<int:cita_id>/cancelar/", views.cancelar, name="cancelar"),
    path("citas/<int:cita_id>/consulta/", views.registrar_consulta, name="registrar-consulta"),
    path("pacientes/registrar/", views.registrar_paciente, name="registrar-paciente"),
    path("historial/", views.historial, name="historial"),
    path("pacientes/<int:paciente_id>/historial/", views.historial, name="historial-paciente"),
    path("registros/<int:consulta_id>/nota/", views.agregar_nota, name="agregar-nota"),
]
