"""Testes da tela Configurações."""
import io
import tempfile
from pathlib import Path

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from openpyxl import Workbook

from pedidos.models import Alteracao, Configuracao
from pedidos.tests.test_servicos import planilha_precos
from test_conferencia import criar_modelo


def xlsx_sem_pedido() -> bytes:
    wb = Workbook()
    wb.active.title = "OUTRA"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def modelo_valido() -> bytes:
    with tempfile.TemporaryDirectory() as pasta:
        caminho = Path(pasta) / "m.xlsx"
        criar_modelo(caminho)
        return caminho.read_bytes()


class ConfiguracoesTests(TestCase):
    def setUp(self):
        self.u = User.objects.create_user("maria", password="x")
        self.client.force_login(self.u)
        self.url = reverse("configuracoes")

    def postar(self, nome, dados, seguir=True):
        return self.client.post(reverse(nome), dados, follow=seguir)

    def textos(self, resp):
        return [str(m) for m in resp.context["messages"]]

    def test_pagina_exige_login(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_salvar_lojas_pelo_texto(self):
        resp = self.postar("configuracoes_lojas", {"lojas_texto": "20-256 SAO\n20-073"})
        self.assertRedirects(resp, self.url)
        self.assertEqual(Configuracao.atual().lojas_texto, "20-256 SAO\n20-073")
        self.assertContains(resp, "2 lojas")

    def test_importar_lojas_txt_latin1_com_bom_e_crlf(self):
        texto = "\ufeff20-256 São\r\n20-073\r\n"
        for dados in (texto.encode("utf-8"), texto.lstrip("\ufeff").encode("latin-1")):
            arq = SimpleUploadedFile("lojas.txt", dados)
            resp = self.postar("configuracoes_lojas", {"lojas_texto": "20-999", "lojas_arquivo": arq})
            cfg = Configuracao.atual()
            self.assertIn("20-256 São", cfg.lojas_texto)
            self.assertNotIn("\r", cfg.lojas_texto)
            self.assertNotIn("\ufeff", cfg.lojas_texto)
            self.assertNotIn("20-999", cfg.lojas_texto)
            self.assertContains(resp, "2 lojas")

    def test_lojas_arquivo_so_txt(self):
        arq = SimpleUploadedFile("lojas.csv", b"20-256")
        resp = self.postar("configuracoes_lojas", {"lojas_arquivo": arq})
        self.assertIn("Envie um arquivo .txt.", self.textos(resp))

    def test_lojas_arquivo_grande(self):
        arq = SimpleUploadedFile("lojas.txt", b"x" * (1024 * 1024 + 1))
        resp = self.postar("configuracoes_lojas", {"lojas_arquivo": arq})
        self.assertIn("O arquivo lojas.txt passa de 1 MB.", self.textos(resp))

    def test_lista_vazia_recusada(self):
        self.postar("configuracoes_lojas", {"lojas_texto": "20-256"})
        resp = self.postar("configuracoes_lojas", {"lojas_texto": ""})
        self.assertTrue(any("Nenhuma loja válida" in t for t in self.textos(resp)))
        self.assertEqual(Configuracao.atual().lojas_texto, "20-256")

    def test_trocar_modelo(self):
        arq = SimpleUploadedFile("modelo novo.xlsx", modelo_valido())
        resp = self.postar("configuracoes_modelo", {"modelo": arq})
        self.assertEqual(Configuracao.atual().modelo_nome, "modelo novo.xlsx")
        self.assertContains(resp, "modelo novo.xlsx")

    def test_modelo_sem_pedido_recusado(self):
        antes = Configuracao.atual().modelo_nome
        arq = SimpleUploadedFile("x.xlsx", xlsx_sem_pedido())
        resp = self.postar("configuracoes_modelo", {"modelo": arq})
        self.assertTrue(any("não tem a aba PEDIDO" in t for t in self.textos(resp)))
        self.assertEqual(Configuracao.atual().modelo_nome, antes)

    def test_modelo_sem_arquivo(self):
        resp = self.postar("configuracoes_modelo", {})
        self.assertIn("Envie um arquivo .xlsx.", self.textos(resp))

    def test_trocar_e_remover_precos(self):
        resp = self.client.get(self.url)
        self.assertContains(resp, "Nenhuma planilha de preços: a coluna D (PRC.VEN) fica vazia.")
        arq = SimpleUploadedFile("p.xlsx", planilha_precos())
        resp = self.postar("configuracoes_precos", {"precos": arq})
        self.assertEqual(Configuracao.atual().precos_qtd, 2)
        self.assertContains(resp, "p.xlsx")
        self.assertContains(resp, "2 produtos")
        resp = self.postar("configuracoes_precos_remover", {})
        self.assertIsNone(Configuracao.atual().precos)
        self.assertContains(resp, "Nenhuma planilha de preços")

    def test_lojas_por_arquivo(self):
        self.postar("configuracoes_lojas_por_arquivo", {"valor": "9"})
        self.assertEqual(Configuracao.atual().lojas_por_arquivo, 9)

    def test_lojas_por_arquivo_zero_recusado(self):
        resp = self.postar("configuracoes_lojas_por_arquivo", {"valor": "0"})
        self.assertIn("O número de lojas por arquivo precisa ser pelo menos 1.", self.textos(resp))
        self.assertEqual(Configuracao.atual().lojas_por_arquivo, 7)

    def test_lojas_por_arquivo_nao_inteiro(self):
        resp = self.postar("configuracoes_lojas_por_arquivo", {"valor": "abc"})
        self.assertIn("Informe um número inteiro.", self.textos(resp))

    def test_historico_mostra_ultimas_20(self):
        for n in range(25):
            Alteracao.objects.create(usuario=self.u, descricao=f"mudança {n:02d}")
        resp = self.client.get(self.url)
        corpo = resp.content.decode()
        self.assertEqual(corpo.count("mudança "), 20)
        self.assertIn("mudança 24", corpo)
        self.assertNotIn("mudança 04", corpo)
        self.assertLess(corpo.index("mudança 24"), corpo.index("mudança 23"))
        self.assertIn(" · maria · mudança 24", corpo)

    def test_get_nao_altera_nada(self):
        for nome in ("configuracoes_lojas", "configuracoes_modelo", "configuracoes_precos",
                     "configuracoes_precos_remover", "configuracoes_lojas_por_arquivo"):
            self.assertEqual(self.client.get(reverse(nome)).status_code, 405, nome)
        self.assertEqual(Alteracao.objects.count(), 0)
