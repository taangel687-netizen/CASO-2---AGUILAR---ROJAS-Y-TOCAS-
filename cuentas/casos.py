from dataclasses import dataclass


@dataclass(frozen=True)
class Caso:
    titulo: str
    institucion: str
    dominio: str
    minutos: int
    roles: dict


CASO = Caso(
    titulo="Consultas médicas",
    institucion="Centro Médico Universitario · UNCP",
    dominio="uncp.edu.pe",
    minutos=20,
    roles={
        "admin": "Admins",
        "medico": "Médicos",
        "recepcionista": "Recepcionistas",
        "paciente": "Pacientes",
    },
)
