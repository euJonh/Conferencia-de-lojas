"""Validação dos arquivos enviados."""
import io
import zipfile

from conferencia import MSG_PLANILHA_CORROMPIDA, ErroConferencia, decodificar_texto

LIMITE_ARQUIVO = 10 * 1024 * 1024         # bytes por arquivo enviado
LIMITE_TXT = 1024 * 1024                   # bytes do arquivo .txt de lojas
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


def ler_txt_lojas(arquivo) -> str:
    """Confere extensão e tamanho do .txt de lojas e devolve o texto, com quebras de linha \n."""
    nome = arquivo.name
    if not nome.lower().endswith(".txt"):
        raise ErroConferencia("Envie um arquivo .txt.")
    if arquivo.size > LIMITE_TXT:
        raise ErroConferencia(f"O arquivo {nome} passa de 1 MB.")
    return "\n".join(decodificar_texto(arquivo.read()).splitlines())
