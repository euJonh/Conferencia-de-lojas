"""Leitura e gravação da configuração compartilhada."""
from django.db import transaction

from conferencia import ErroConferencia, ler_lojas_texto, ler_precos_bytes, validar_modelo

from .models import Alteracao, Configuracao


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
