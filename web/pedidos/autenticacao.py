"""Bloqueio por tentativas, aplicado a todo login (site e /admin)."""
from datetime import timedelta

from django.contrib.auth.backends import ModelBackend
from django.db.models import F
from django.utils import timezone

from .models import TentativaLogin

MAX_FALHAS = 5
MINUTOS_BLOQUEIO = 15


def bloqueado(nome):
    """Diz se o usuário está com bloqueio ainda em vigor."""
    t = TentativaLogin.objects.filter(usuario=nome[:150]).first()
    return bool(t and t.bloqueado_ate and t.bloqueado_ate > timezone.now())


class BackendComBloqueio(ModelBackend):
    """Autenticação padrão + 15 min de bloqueio após 5 senhas erradas seguidas."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            return None
        agora = timezone.now()
        t, _ = TentativaLogin.objects.get_or_create(usuario=username[:150])
        if t.bloqueado_ate and t.bloqueado_ate > agora:
            return None
        if t.bloqueado_ate:  # bloqueio vencido: recomeça do zero
            t.falhas = 0
            t.bloqueado_ate = None
            t.save(update_fields=["falhas", "bloqueado_ate"])
        usuario = super().authenticate(request, username=username, password=password, **kwargs)
        if usuario is not None:
            t.falhas = 0
            t.bloqueado_ate = None
            t.save(update_fields=["falhas", "bloqueado_ate"])
        else:
            # F() soma no banco: logins em paralelo não perdem tentativas.
            TentativaLogin.objects.filter(pk=t.pk).update(falhas=F("falhas") + 1)
            t.refresh_from_db()
            if t.falhas >= MAX_FALHAS:
                t.bloqueado_ate = agora + timedelta(minutes=MINUTOS_BLOQUEIO)
                t.save(update_fields=["bloqueado_ate"])
        return usuario
