"""Telas do app: login, logout e tela Início."""
import json

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from functools import wraps

from django.core.exceptions import TooManyFilesSent
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from conferencia import NOME_SAIDA, ErroConferencia

from . import servicos
from .autenticacao import MINUTOS_BLOQUEIO, bloqueado
from .forms import checar_xlsx

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
    """Tela Início: anexar uma planilha de pedido e baixar a gerada."""
    try:
        servicos.carregar()
        config_ok = True
    except servicos.ConfigIncompleta:
        config_ok = False
    return render(request, "pedidos/inicio.html", {"config_ok": config_ok})


MAX_PLANILHAS = 30
MSG_MUITAS = f"Envie no máximo {MAX_PLANILHAS} planilhas por vez."
MSG_SESSAO_EXPIRADA = "Sua sessão expirou. Entre novamente."


def login_required_json(visao):
    """Como login_required, mas responde 401 JSON (em vez de redirecionar) para o JavaScript."""
    @wraps(visao)
    def envolvida(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"erro": MSG_SESSAO_EXPIRADA, "entrar": True}, status=401)
        return visao(request, *args, **kwargs)
    return envolvida


@require_POST
@login_required_json
def gerar(request):
    """Recebe `planilha` e devolve o .xlsx gerado, com o resumo em X-Resumo."""
    try:
        arquivo = request.FILES.get("planilha")
        if arquivo is None:
            raise ErroConferencia("Envie um arquivo .xlsx.")
        saida, resumo = servicos.gerar_um(arquivo.name, checar_xlsx(arquivo))
    except Exception as e:
        return servicos.resposta_erro(e)
    resposta = HttpResponse(
        saida, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    resposta["Content-Disposition"] = f'attachment; filename="{NOME_SAIDA}"'
    resposta["X-Resumo"] = json.dumps(resumo, ensure_ascii=True)
    return resposta


@login_required
def lote(request):
    """Tela Gerar em lote: várias planilhas viram um .zip."""
    por_arquivo = 0
    try:
        por_arquivo = servicos.carregar()[3]
        config_ok = True
    except servicos.ConfigIncompleta:
        config_ok = False
    return render(request, "pedidos/lote.html", {
        "config_ok": config_ok, "max_planilhas": MAX_PLANILHAS, "por_arquivo": por_arquivo,
        "plural": por_arquivo > 1})


@require_POST
@login_required_json
def gerar_lote(request):
    """Recebe `planilhas` (várias) e devolve um .zip, com o resumo em X-Resumo."""
    try:
        try:
            arquivos = request.FILES.getlist("planilhas")
        except TooManyFilesSent:
            raise ErroConferencia(MSG_MUITAS) from None
        if not arquivos:
            raise ErroConferencia("Nenhuma planilha anexada.")
        if len(arquivos) > MAX_PLANILHAS:
            raise ErroConferencia(MSG_MUITAS)
        planilhas = []
        for arquivo in arquivos:
            try:
                planilhas.append((arquivo.name, checar_xlsx(arquivo)))
            except ErroConferencia as e:
                if arquivo.name in str(e):
                    raise
                raise ErroConferencia(f"Problema na planilha {arquivo.name}:\n\n{e}") from None
        saida, resumo = servicos.gerar_lote(planilhas)
    except Exception as e:
        return servicos.resposta_erro(e)
    resposta = HttpResponse(saida, content_type="application/zip")
    resposta["Content-Disposition"] = 'attachment; filename="PLANILHAS DE PEDIDOS.zip"'
    resposta["X-Resumo"] = json.dumps(resumo, ensure_ascii=True)
    return resposta
