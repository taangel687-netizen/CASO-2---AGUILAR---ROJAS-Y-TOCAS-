from .permisos import roles_usuario


def citas_pendientes(usuario, citas_del_medico):
    """Recibe las citas pendientes ya filtradas por el médico autenticado."""
    if "medico" not in roles_usuario(usuario):
        return ()
    cantidad = citas_del_medico.count()
    if not cantidad:
        return ()
    return (f"Tienes citas pendientes ({cantidad}). Revisa tu agenda.",)
