"""Config do admin: só superusuários entram."""
from django.contrib.admin.apps import AdminConfig


class AdminSomenteSuperusuario(AdminConfig):
    """Troca o site de admin padrão por um que só admite superusuários."""

    default_site = "pedidos.site_admin.SiteAdmin"
