"""Validação dos arquivos enviados."""
import io
import zipfile

from conferencia import MSG_PLANILHA_CORROMPIDA, ErroConferencia

LIMITE_ARQUIVO = 10 * 1024 * 1024         # bytes por arquivo enviado
LIMITE_DESCOMPACTADO = 100 * 1024 * 1024  # bytes do conteúdo descompactado do .xlsx


def checar_xlsx(arquivo) -> bytes:
    """Confere extensão, tamanho e conteúdo do upload e devolve os bytes."""
    nome = arquivo.name
    if not nome.lower().endswith(".xlsx"):
        raise ErroConferencia("Envie um arquivo .xlsx.")
    if arquivo.size > LIMITE_ARQUIVO:
        raise ErroConferencia(f"O arquivo {nome} passa de 10 MB.")
    dados = arquivo.read()
    try:
        with zipfile.ZipFile(io.BytesIO(dados)) as zf:
            total = sum(info.file_size for info in zf.infolist())
    except zipfile.BadZipFile:
        raise ErroConferencia(MSG_PLANILHA_CORROMPIDA) from None
    if total > LIMITE_DESCOMPACTADO:
        raise ErroConferencia(f"O arquivo {nome} é grande demais depois de descompactado.")
    return dados
