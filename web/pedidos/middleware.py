"""Middlewares de limite de envio, antes de o Django ler o corpo da requisição."""
from django.core.exceptions import TooManyFilesSent
from django.http import JsonResponse
from django.urls import reverse

MB = 1024 * 1024
LIMITE_LOTE = 100 * MB   # bytes do envio inteiro em /gerar-lote
LIMITE_ENVIO = 12 * MB   # bytes de qualquer outro POST (um arquivo de até 10 MB + formulário)
MSG_LOTE_GRANDE = "O lote passa de 100 MB. Divida as planilhas em mais de um envio."
MSG_ENVIO_GRANDE = "O envio passa do tamanho permitido."


def _tamanho(request) -> int | None:
    """Content-Length da requisição; None se faltar ou for inválido em envio multipart."""
    bruto = request.META.get("CONTENT_LENGTH", "")
    try:
        valor = int(bruto)
        if valor < 0:
            raise ValueError
    except (TypeError, ValueError):
        return None if request.META.get("CONTENT_TYPE", "").startswith("multipart/") else 0
    return valor


class LimiteTamanhoMiddleware:
    """Vai antes do CsrfViewMiddleware (e de tudo que lê request.POST ou request.FILES):
    recusa com 413 em JSON pelo Content-Length, sem ler o corpo. Não pesa na memória do servidor."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == "POST":
            tamanho = _tamanho(request)
            eh_lote = request.path == reverse("gerar_lote")
            limite = LIMITE_LOTE if eh_lote else LIMITE_ENVIO
            if tamanho is None or tamanho > limite:
                msg = MSG_LOTE_GRANDE if eh_lote else MSG_ENVIO_GRANDE
                return JsonResponse({"erro": msg}, status=413)
        return self.get_response(request)


class LimiteArquivosLoteMiddleware:
    """Vai antes do CsrfViewMiddleware: ele lê request.POST e, com mais arquivos que
    DATA_UPLOAD_MAX_NUMBER_FILES, o Django responderia 400 em HTML. Só vale para /gerar-lote
    e só para quem está logado (o anônimo recebe o 401 da própria view, sem ler o corpo)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (request.method == "POST" and request.path == reverse("gerar_lote")
                and "_auth_user_id" in request.session):
            try:
                request.POST  # noqa: B018 - força a leitura do corpo (e dos arquivos)
            except TooManyFilesSent:
                from .views import MSG_MUITAS
                return JsonResponse({"erro": MSG_MUITAS}, status=400)
        return self.get_response(request)
