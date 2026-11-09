"""Modelos do app."""
from django.conf import settings
from django.db import models


class TentativaLogin(models.Model):
    """Controle de senhas erradas seguidas por nome de usuário."""

    usuario = models.CharField(max_length=150, unique=True)
    falhas = models.PositiveIntegerField(default=0)
    bloqueado_ate = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.usuario} ({self.falhas} falhas)"


class Configuracao(models.Model):
    """Configuração compartilhada por todos os usuários (uma única linha, pk=1)."""

    lojas_texto = models.TextField(blank=True, default="")
    modelo = models.BinaryField(default=b"")
    modelo_nome = models.CharField(max_length=255, blank=True, default="")
    precos = models.BinaryField(null=True, blank=True)
    precos_nome = models.CharField(max_length=255, blank=True, default="")
    precos_qtd = models.IntegerField(default=0)
    lojas_por_arquivo = models.PositiveIntegerField(default=7)
    atualizado_em = models.DateTimeField(auto_now=True)
    atualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    @classmethod
    def atual(cls) -> "Configuracao":
        return cls.objects.get_or_create(pk=1)[0]

    def __str__(self):
        return "Configuração"


class Alteracao(models.Model):
    """Histórico de mudanças na configuração."""

    quando = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    descricao = models.CharField(max_length=300)

    class Meta:
        ordering = ["-quando", "-id"]

    def __str__(self):
        return self.descricao
