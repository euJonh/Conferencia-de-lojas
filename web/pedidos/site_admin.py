"""Site de administração restrito a superusuários."""
from django.contrib.admin import AdminSite


class SiteAdmin(AdminSite):
    def has_permission(self, request):
        u = request.user
        return u.is_active and u.is_superuser
