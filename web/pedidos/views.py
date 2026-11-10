"""Telas do app: login, logout e tela Início."""
import json

from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from functools import wraps

from django.core.exceptions import TooManyFilesSent
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from conferencia import NOME_SAIDA, ErroConferencia, ler_lojas_texto

from . import servicos
from .autenticacao import MINUTOS_BLOQUEIO, bloqueado
from .middleware import LIMITE_LOTE, MSG_LOTE_GRANDE
from .forms import checar_xlsx, ler_txt_lojas
from .models import Alteracao, Configuracao

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


LIMITE_RASCUNHO = 200 * 1024  # bytes do texto das lojas guardado na sessão após um erro


@login_required
def inicio(request):
    """Tela Início: anexar uma planilha de pedido e baixar a gerada."""
    return render(request, "pedidos/inicio.html", {"config_ok": servicos.config_completa()})


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
    por_arquivo = servicos.lojas_por_arquivo()
    return render(request, "pedidos/lote.html", {
        "config_ok": servicos.config_completa(), "max_planilhas": MAX_PLANILHAS,
        "por_arquivo": por_arquivo, "plural": por_arquivo > 1,
        "limite_lote": LIMITE_LOTE, "msg_limite_lote": MSG_LOTE_GRANDE})


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


@login_required
def configuracoes(request):
    """Tela Configurações: lojas, modelo, preços, lojas por arquivo e histórico."""
    cfg = Configuracao.atual()
    try:
        qtd_lojas = len(ler_lojas_texto(cfg.lojas_texto))
    except ErroConferencia:
        qtd_lojas = 0
    rascunho = request.session.pop("lojas_rascunho", None)  # texto recusado na última tentativa
    return render(request, "pedidos/configuracoes.html", {
        "cfg": cfg, "qtd_lojas": qtd_lojas,
        "lojas_texto": cfg.lojas_texto if rascunho is None else rascunho,
        "historico": Alteracao.objects.select_related("usuario")[:20]})


def _acao(visao):
    """Ação de Configurações: só POST, com login; avisa o resultado e volta para a tela."""
    @wraps(visao)
    @require_POST
    @login_required
    def envolvida(request):
        try:
            messages.success(request, visao(request))
        except ErroConferencia as e:
            messages.error(request, str(e))
        return redirect("configuracoes")
    return envolvida


def _arquivo_xlsx(request, campo):
    arquivo = request.FILES.get(campo)
    if arquivo is None:
        raise ErroConferencia("Envie um arquivo .xlsx.")
    return arquivo.name, checar_xlsx(arquivo)


@_acao
def configuracoes_lojas(request):
    arquivo = request.FILES.get("lojas_arquivo")
    if arquivo is not None:
        texto = ler_txt_lojas(arquivo)
    else:
        texto = "\n".join(request.POST.get("lojas_texto", "").splitlines())
    try:
        qtd = servicos.salvar_lojas(texto, request.user)
    except ErroConferencia:
        if len(texto.encode()) <= LIMITE_RASCUNHO:  # a próxima tela devolve o texto ao campo
            request.session["lojas_rascunho"] = texto
        raise
    return f"Lista de lojas salva ({qtd} lojas)."


@_acao
def configuracoes_modelo(request):
    nome, dados = _arquivo_xlsx(request, "modelo")
    servicos.salvar_modelo(nome, dados, request.user)
    return f"Modelo trocado para {nome}."


@_acao
def configuracoes_precos(request):
    nome, dados = _arquivo_xlsx(request, "precos")
    qtd = servicos.salvar_precos(nome, dados, request.user)
    return f"Planilha de preços trocada para {nome} ({qtd} produtos)."


@_acao
def configuracoes_precos_remover(request):
    servicos.remover_precos(request.user)
    return "Planilha de preços removida."


@_acao
def configuracoes_lojas_por_arquivo(request):
    try:
        valor = int(request.POST.get("valor", "").strip())
    except ValueError:
        raise ErroConferencia("Informe um número inteiro.") from None
    servicos.salvar_lojas_por_arquivo(valor, request.user)
    return f"Lojas por arquivo: {valor}."
