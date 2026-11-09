"""Middleware que responde em JSON quando o envio do lote tem arquivos demais."""
from django.core.exceptions import TooManyFilesSent
from django.http import JsonResponse
from django.urls import reverse


class LimiteArquivosLoteMiddleware:
    """Vai antes do CsrfViewMiddleware: ele lê request.POST e, com mais arquivos que
    DATA_UPLOAD_MAX_NUMBER_FILES, o Django responderia 400 em HTML. Só vale para /gerar-lote."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == "POST" and request.path == reverse("gerar_lote"):
            try:
                request.POST  # noqa: B018 - força a leitura do corpo (e dos arquivos)
            except TooManyFilesSent:
                from .views import MSG_MUITAS
                return JsonResponse({"erro": MSG_MUITAS}, status=400)
        return self.get_response(request)
