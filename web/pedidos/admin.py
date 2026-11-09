from django.contrib import admin

from .models import TentativaLogin


@admin.register(TentativaLogin)
class TentativaLoginAdmin(admin.ModelAdmin):
    list_display = ("usuario", "falhas", "bloqueado_ate")
