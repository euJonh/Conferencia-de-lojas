"""Leitura e gravação da configuração compartilhada e geração da planilha."""
import io
import logging
import zipfile

from django.db import transaction
from django.http import JsonResponse

import conferencia as c
from conferencia import ErroConferencia, ler_lojas_texto, ler_precos_bytes, validar_modelo

from .models import Alteracao, Configuracao

logger = logging.getLogger(__name__)

MSG_CONFIG_INCOMPLETA = ("Configuração incompleta: cadastre a lista de lojas e o modelo "
                         "em Configurações.")
MSG_ERRO_INESPERADO = "Erro inesperado ao gerar; tente novamente ou avise o administrador."


class ConfigIncompleta(Exception):
    """Falta o modelo ou a lista de lojas."""


def carregar() -> tuple[dict, bytes, dict | None, int]:
    """(lojas, modelo, preços ou None, lojas por arquivo)."""
    c = Configuracao.atual()
    modelo = bytes(c.modelo or b"")
    if not modelo:
        raise ConfigIncompleta("Falta o modelo da planilha de pedidos.")
    try:
        lojas = ler_lojas_texto(c.lojas_texto)
    except ErroConferencia as e:
        raise ConfigIncompleta("Falta a lista de lojas.") from e
    precos = ler_precos_bytes(bytes(c.precos)) if c.precos else None
    return lojas, modelo, precos, c.lojas_por_arquivo


def _gravar(usuario, descricao: str, **campos) -> None:
    with transaction.atomic():
        c = Configuracao.atual()
        for nome, valor in campos.items():
            setattr(c, nome, valor)
        c.atualizado_por = usuario
        c.save()
        Alteracao.objects.create(usuario=usuario, descricao=descricao[:300])


def salvar_lojas(texto: str, usuario) -> int:
    qtd = len(ler_lojas_texto(texto))
    _gravar(usuario, f"alterou a lista de lojas ({qtd} lojas)", lojas_texto=texto)
    return qtd


def salvar_modelo(nome: str, dados: bytes, usuario) -> None:
    validar_modelo(dados)
    _gravar(usuario, f"trocou o modelo para {nome}", modelo=dados, modelo_nome=nome)


def salvar_precos(nome: str, dados: bytes, usuario) -> int:
    qtd = len(ler_precos_bytes(dados))
    _gravar(usuario, f"trocou a planilha de preços para {nome} ({qtd} produtos)",
            precos=dados, precos_nome=nome, precos_qtd=qtd)
    return qtd


def remover_precos(usuario) -> None:
    _gravar(usuario, "removeu a planilha de preços", precos=None, precos_nome="", precos_qtd=0)


def salvar_lojas_por_arquivo(valor: int, usuario) -> None:
    if valor < 1:
        raise ErroConferencia("O número de lojas por arquivo precisa ser pelo menos 1.")
    _gravar(usuario, f"mudou lojas por arquivo para {valor}", lojas_por_arquivo=valor)


def gerar_um(nome: str, dados: bytes) -> tuple[bytes, dict]:
    """Gera a planilha de pedidos de um arquivo; devolve (xlsx, resumo)."""
    lojas, modelo, precos, _ = carregar()
    saida, r = c.processar_bytes(nome, dados, lojas, modelo, precos)
    com_1 = sum(it.tipo == "1" for it in r.pedidos)
    resumo = {
        "marca": r.marca,
        "linhas": len(r.pedidos),
        "com_1": com_1,
        "com_me": len(r.pedidos) - com_1,
        "encontradas": len(r.encontradas),
        "total_lojas": len(r.lojas),
        "duplicadas": len(r.duplicadas),
        "faltando": [loja.codigo for loja in r.faltando],
        "nao_reconhecidas": len(r.nao_reconhecidas),
        "sem_preco": list(r.sem_preco),
        "tem_precos": precos is not None,
    }
    return saida, resumo


def _faixa(lojas) -> str:
    """"20-050 a 20-059"; com uma loja só, apenas o código."""
    return f"{lojas[0].codigo} a {lojas[-1].codigo}" if len(lojas) > 1 else lojas[0].codigo


def gerar_lote(planilhas: list[tuple[str, bytes]]) -> tuple[bytes, dict]:
    """Junta várias planilhas de pedido e devolve (.zip em memória, resumo)."""
    lojas, modelo, precos, por_arquivo = carregar()
    r = c.processar_lote_bytes(planilhas, lojas, modelo, precos, tamanho_grupo=por_arquivo)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for n, arq in enumerate(r.arquivos, start=1):
            zf.writestr(c.nome_saida_lote(n), arq.dados)
    resumo = {
        "planilhas": len(r.planilhas),
        "linhas": sum(len(a.itens) for a in r.arquivos),
        "arquivos": [{"nome": c.nome_saida_lote(n), "lojas": _faixa(a.lojas), "linhas": len(a.itens)}
                     for n, a in enumerate(r.arquivos, start=1)],
        "sem_preco": list(r.sem_preco),
        "tem_precos": precos is not None,
    }
    return buf.getvalue(), resumo


def resposta_erro(erro: Exception) -> JsonResponse:
    """Converte uma exceção na resposta JSON de erro (400, 409 ou 500)."""
    if isinstance(erro, ErroConferencia):
        return JsonResponse({"erro": str(erro)}, status=400)
    if isinstance(erro, ConfigIncompleta):
        return JsonResponse({"erro": MSG_CONFIG_INCOMPLETA, "config": True}, status=409)
    logger.error("Erro inesperado ao gerar", exc_info=erro)
    return JsonResponse({"erro": MSG_ERRO_INESPERADO}, status=500)
