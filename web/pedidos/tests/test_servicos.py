"""Testes da configuração compartilhada e do histórico."""
import io

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase
from openpyxl import Workbook

from conferencia import ErroConferencia
from pedidos import servicos
from pedidos.models import Alteracao, Configuracao


def planilha_precos() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(["CODIGO", "B", "C", "D", "E", "F", "G", "H", "I", "J", "VALOR UNITARIO"])
    ws.append(["100", "", "", "", "", "", "", "", "", "", 5.5])
    ws.append(["200", "", "", "", "", "", "", "", "", "", 7])
    saida = io.BytesIO()
    wb.save(saida)
    return saida.getvalue()


def modelo_sem_aba_pedido() -> bytes:
    saida = io.BytesIO()
    Workbook().save(saida)
    return saida.getvalue()


class ServicosTests(TestCase):
    def setUp(self):
        self.u = User.objects.create_user("ana", password="x")

    def test_carga_inicial(self):
        c = Configuracao.atual()
        raiz = settings.RAIZ
        self.assertEqual(c.lojas_texto, (raiz / "lojas.txt").read_text(encoding="utf-8-sig"))
        self.assertEqual(bytes(c.modelo), (raiz / "PLANILHA DE PEDIDOS.xlsx").read_bytes())
        self.assertIsNone(c.precos)
        self.assertEqual(c.lojas_por_arquivo, 7)

    def test_carregar_config_incompleta(self):
        Configuracao.objects.filter(pk=1).update(modelo=b"")
        with self.assertRaises(servicos.ConfigIncompleta):
            servicos.carregar()

    def test_carregar_completo(self):
        lojas, modelo, precos, por_arquivo = servicos.carregar()
        self.assertTrue(lojas)
        self.assertIsInstance(modelo, bytes)
        self.assertIsNone(precos)
        self.assertEqual(por_arquivo, 7)

    def test_salvar_lojas_grava_historico(self):
        self.assertEqual(servicos.salvar_lojas("20-256 X\n20-073", self.u), 2)
        a = Alteracao.objects.first()
        self.assertEqual(a.descricao, "alterou a lista de lojas (2 lojas)")
        self.assertEqual(a.usuario, self.u)
        self.assertEqual(Configuracao.atual().atualizado_por, self.u)

    def test_salvar_lojas_invalida_nao_grava(self):
        antes = Configuracao.atual().lojas_texto
        n = Alteracao.objects.count()
        with self.assertRaises(ErroConferencia):
            servicos.salvar_lojas("nada", self.u)
        self.assertEqual(Configuracao.atual().lojas_texto, antes)
        self.assertEqual(Alteracao.objects.count(), n)

    def test_salvar_modelo_sem_aba_pedido_recusado(self):
        antes = bytes(Configuracao.atual().modelo)
        with self.assertRaises(ErroConferencia):
            servicos.salvar_modelo("x.xlsx", modelo_sem_aba_pedido(), self.u)
        self.assertEqual(bytes(Configuracao.atual().modelo), antes)

    def test_salvar_e_remover_precos(self):
        self.assertEqual(servicos.salvar_precos("p.xlsx", planilha_precos(), self.u), 2)
        c = Configuracao.atual()
        self.assertEqual(c.precos_qtd, 2)
        self.assertEqual(c.precos_nome, "p.xlsx")
        self.assertEqual(servicos.carregar()[2], {"100": 5.5, "200": 7})
        servicos.remover_precos(self.u)
        c = Configuracao.atual()
        self.assertIsNone(c.precos)
        self.assertEqual(c.precos_nome, "")
        self.assertEqual(c.precos_qtd, 0)

    def test_lojas_por_arquivo_minimo_1(self):
        with self.assertRaises(ErroConferencia):
            servicos.salvar_lojas_por_arquivo(0, self.u)
        servicos.salvar_lojas_por_arquivo(3, self.u)
        self.assertEqual(Configuracao.atual().lojas_por_arquivo, 3)
        self.assertEqual(Alteracao.objects.first().descricao, "mudou lojas por arquivo para 3")
