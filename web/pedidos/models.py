"""Modelos do app."""
from django.db import models


class TentativaLogin(models.Model):
    """Controle de senhas erradas seguidas por nome de usuário."""

    usuario = models.CharField(max_length=150, unique=True)
    falhas = models.PositiveIntegerField(default=0)
    bloqueado_ate = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.usuario} ({self.falhas} falhas)"
