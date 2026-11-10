from django.contrib import admin

from .models import TentativaLogin


@admin.register(TentativaLogin)
class TentativaLoginAdmin(admin.ModelAdmin):
    list_display = ("usuario", "falhas", "bloqueado_ate")

from .models import Alteracao


@admin.register(Alteracao)
class AlteracaoAdmin(admin.ModelAdmin):
    list_display = ("quando", "usuario", "descricao")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
