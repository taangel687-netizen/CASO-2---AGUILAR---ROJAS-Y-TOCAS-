# Caso 2 · Consultas médicas

Práctica grupal de Desarrollo de Aplicaciones Web. La aplicación usa la base de cuentas de Ángel, Django 5.2 y SQLite.

## Ejecutar en PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py configurar_roles
.\.venv\Scripts\python.exe manage.py cargar_consultas_demo
.\.venv\Scripts\python.exe manage.py changepassword demo-paciente-01@uncp.edu.pe
.\.venv\Scripts\python.exe manage.py runserver
```

El catálogo de cuentas se carga con 8 médicos, 15 pacientes y 30 citas ficticias. Usa `changepassword` para habilitar las cuentas que vayas a probar. También están disponibles `demo-medico-01@uncp.edu.pe`, `demo-centro-recepcion@uncp.edu.pe` y `demo-centro-admin@uncp.edu.pe`.

Desde el portal en `http://127.0.0.1:8000/`, entra con una cuenta y abre la agenda. Las citas duran 30 minutos. El formulario usa la hora de Lima, comprueba el turno del médico y evita una segunda cita el mismo día o un cruce de horarios. El inicio de sesión y la inactividad usan el perfil médico de 20 minutos.

| Rol | Acceso |
| --- | --- |
| Paciente | Agenda, cancelación e historial propios. |
| Recepción | Registro de pacientes, agenda y cancelación de citas. |
| Médico | Agenda propia, registro de atenciones, notas y lectura auditada de historiales. |
| Administrador | Agenda operativa, estadísticas y acciones en Django Admin. |

El historial registra quién accedió y el identificador del paciente. El registro de una consulta queda fijo y las ampliaciones se guardan como notas.

```powershell
.\.venv\Scripts\python.exe manage.py test
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
```
