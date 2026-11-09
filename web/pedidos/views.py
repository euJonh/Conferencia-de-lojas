"""Telas do app: login, logout e página inicial provisória."""
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .autenticacao import MINUTOS_BLOQUEIO, bloqueado

MSG_ERRO = "Usuário ou senha incorretos."
MSG_BLOQUEIO = f"Muitas tentativas. Tente novamente em {MINUTOS_BLOQUEIO} minutos."


def _destino(request):
    """Devolve o `next` se for um endereço seguro; senão a página inicial."""
    alvo = request.POST.get("next") or request.GET.get("next") or ""
    if alvo and url_has_allowed_host_and_scheme(
            alvo, allowed_hosts={request.get_host()},
            require_https=request.is_secure()):
        return alvo
    return reverse("inicio")


def entrar(request):
    """Tela de login com bloqueio de 15 min após 5 senhas erradas seguidas."""
    if request.user.is_authenticated:
        return redirect("inicio")
    erro = ""
    if request.method == "POST":
        nome = request.POST.get("username", "").strip()
        senha = request.POST.get("password", "")
        if bloqueado(nome):
            erro = MSG_BLOQUEIO
        else:
            usuario = authenticate(request, username=nome, password=senha)
            if usuario is not None:
                login(request, usuario)
                return redirect(_destino(request))
            erro = MSG_ERRO
    return render(request, "pedidos/entrar.html", {
        "erro": erro, "next": request.GET.get("next", request.POST.get("next", ""))})


@require_POST
def sair(request):
    """Encerra a sessão."""
    logout(request)
    return redirect("entrar")


@login_required
def inicio(request):
    """Página inicial provisória (substituída na Task 4)."""
    return render(request, "pedidos/inicio.html")
