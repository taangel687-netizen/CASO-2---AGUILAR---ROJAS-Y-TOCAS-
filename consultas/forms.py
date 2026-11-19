from django import forms
from django.core.exceptions import ValidationError
from django.utils.html import strip_tags

from .models import Cita, Consulta, Medico, NotaConsulta, Paciente
from .servicios import validar_cita


class CitaForm(forms.ModelForm):
    inicio = forms.DateTimeField(
        label="Fecha y hora de la cita",
        input_formats=["%Y-%m-%dT%H:%M"],
        widget=forms.DateTimeInput(format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"}),
    )

    class Meta:
        model = Cita
        fields = ("paciente", "medico", "inicio", "motivo")
        widgets = {"motivo": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, paciente=None, especialidad="", **kwargs):
        super().__init__(*args, **kwargs)
        self.paciente = paciente
        if paciente is not None:
            del self.fields["paciente"]
        self.fields["medico"].queryset = Medico.objects.select_related("usuario").filter(
            usuario__is_active=True, especialidad__icontains=especialidad,
        )
        if "paciente" in self.fields:
            self.fields["paciente"].queryset = Paciente.objects.filter(usuario__is_active=True)

    def clean_motivo(self):
        motivo = strip_tags(self.cleaned_data["motivo"]).strip()
        if len(motivo) < 20:
            raise ValidationError("Escribe al menos 20 caracteres en el motivo.")
        return motivo

    def clean(self):
        datos = super().clean()
        if datos.get("inicio"):
            validar_cita(datos.get("paciente", self.paciente), datos.get("medico"), datos["inicio"])
        return datos


class ConsultaForm(forms.ModelForm):
    class Meta:
        model = Consulta
        fields = ("diagnostico", "tratamiento", "medicamentos", "fecha_control", "adjuntos_simulados")
        widgets = {
            "fecha_control": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "diagnostico": forms.Textarea(attrs={"rows": 3}),
            "tratamiento": forms.Textarea(attrs={"rows": 3}),
            "medicamentos": forms.Textarea(attrs={"rows": 3}),
            "adjuntos_simulados": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        datos = super().clean()
        for campo in ("diagnostico", "tratamiento", "medicamentos", "adjuntos_simulados"):
            if campo in datos:
                datos[campo] = strip_tags(datos[campo]).strip()
                if self.fields[campo].required and not datos[campo]:
                    self.add_error(campo, "Escribe un texto para este campo.")
        return datos


class NotaForm(forms.ModelForm):
    class Meta:
        model = NotaConsulta
        fields = ("texto",)
        widgets = {"texto": forms.Textarea(attrs={"rows": 4})}

    def clean_texto(self):
        texto = strip_tags(self.cleaned_data["texto"]).strip()
        if not texto:
            raise ValidationError("Escribe el contenido de la nota.")
        return texto


class PacienteForm(forms.ModelForm):
    class Meta:
        model = Paciente
        fields = ("usuario", "dni", "nombres", "apellidos", "fecha_nacimiento",
                  "tipo", "codigo_uncp", "email", "alergias")
        widgets = {"fecha_nacimiento": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["usuario"].queryset = self.fields["usuario"].queryset.filter(
            is_active=True, groups__name="Pacientes",
        )
