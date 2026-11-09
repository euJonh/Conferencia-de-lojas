"""Testes da tela Início (uma planilha) e do endpoint /gerar."""
import io
import json
import tempfile
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from openpyxl import load_workbook

from pedidos.models import Configuracao
from test_conferencia import LOJAS_TXT, criar_modelo, criar_pedido

NOME_SAIDA = "PLANILHA DE PEDIDOS - novo.xlsx"


def bytes_pedido() -> bytes:
    with tempfile.TemporaryDirectory() as pasta:
        caminho = Path(pasta) / "p.xlsx"
        criar_pedido(caminho)
        return caminho.read_bytes()


def listar(raiz: Path) -> set[Path]:
    return {p for p in raiz.rglob("*")
            if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".sqlite3"}


class InicioTests(TestCase):
    def setUp(self):
        self.u = User.objects.create_user("ana", password="x")
        self.client.force_login(self.u)
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "m.xlsx"
            criar_modelo(caminho)
            modelo = caminho.read_bytes()
        cfg = Configuracao.atual()
        cfg.lojas_texto = LOJAS_TXT
        cfg.modelo = modelo
        cfg.save()

    def gerar(self, nome="Pedido_Drunk Elephant_ teste.xlsx", dados=None):
        dados = bytes_pedido() if dados is None else dados
        return self.client.post("/gerar", {"planilha": SimpleUploadedFile(nome, dados)})

    def test_gerar_baixa_xlsx_e_resumo(self):
        r = self.gerar()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Disposition"], f'attachment; filename="{NOME_SAIDA}"')
        corpo = b"".join(r.streaming_content) if r.streaming else r.content
        self.assertTrue(corpo.startswith(b"PK"))
        resumo = json.loads(r["X-Resumo"])
        self.assertEqual(resumo["marca"], "Drunk Elephant")
        self.assertEqual(resumo["linhas"], 5)
        self.assertEqual(resumo["com_1"], 3)
        self.assertEqual(resumo["com_me"], 2)
        for chave in ("encontradas", "total_lojas", "duplicadas", "faltando",
                      "nao_reconhecidas", "sem_preco", "tem_precos"):
            self.assertIn(chave, resumo)
        wb = load_workbook(io.BytesIO(corpo))
        self.assertEqual(wb["PEDIDO"]["A2"].value, "TRANSFERENCIA TESTER 18 D")

    def test_resumo_com_acento(self):
        r = self.gerar("Pedido_Lancôme_x.xlsx")
        self.assertEqual(r.status_code, 200)
        r["X-Resumo"].encode("ascii")
        self.assertEqual(json.loads(r["X-Resumo"])["marca"], "Lancôme")

    def test_extensao_maiuscula_aceita(self):
        self.assertEqual(self.gerar("Pedido_NARS_x.XLSX").status_code, 200)

    def test_nome_fora_do_padrao(self):
        r = self.gerar("planilha.xlsx")
        self.assertEqual(r.status_code, 400)
        self.assertIn("Não foi possível identificar a marca", r.json()["erro"])

    def test_nao_xlsx_recusado(self):
        r = self.gerar("pedido.csv", b"a,b")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["erro"], "Envie um arquivo .xlsx.")

    def test_xlsx_falso_recusado(self):
        r = self.gerar("Pedido_NARS_x.xlsx", b"abc")
        self.assertEqual(r.status_code, 400)
        self.assertIn("corrompido", r.json()["erro"])

    def test_grande_demais(self):
        r = self.gerar("Pedido_NARS_x.xlsx", b"0" * (10 * 1024 * 1024 + 1))
        self.assertEqual(r.status_code, 400)
        self.assertIn("passa de 10 MB", r.json()["erro"])

    def test_descompactado_grande_demais(self):
        from pedidos import forms
        arq = SimpleUploadedFile("Pedido_NARS_x.xlsx", bytes_pedido())
        with mock.patch.object(forms, "LIMITE_DESCOMPACTADO", 10):
            r = self.client.post("/gerar", {"planilha": arq})
        self.assertEqual(r.status_code, 400)
        self.assertIn("grande demais depois de descompactado", r.json()["erro"])

    def test_sem_arquivo(self):
        r = self.client.post("/gerar", {})
        self.assertEqual(r.status_code, 400)

    def test_config_incompleta(self):
        cfg = Configuracao.atual()
        cfg.modelo = b""
        cfg.save()
        r = self.client.get("/")
        self.assertContains(r, "/configuracoes")
        self.assertNotContains(r, 'type="file"')
        r = self.gerar()
        self.assertEqual(r.status_code, 409)
        self.assertTrue(r.json()["config"])

    def test_erro_inesperado(self):
        with mock.patch("pedidos.servicos.c.processar_bytes", side_effect=RuntimeError):
            with self.assertLogs("pedidos.servicos", level="ERROR"):
                r = self.gerar()
        self.assertEqual(r.status_code, 500)
        self.assertEqual(r.json()["erro"],
                         "Erro inesperado ao gerar; tente novamente ou avise o administrador.")

    def test_nada_gravado_em_disco(self):
        antes = listar(settings.BASE_DIR)
        self.assertEqual(self.gerar().status_code, 200)
        self.assertEqual(listar(settings.BASE_DIR) - antes, set())

    def test_exige_login_e_post(self):
        self.client.logout()
        self.assertEqual(self.client.post("/gerar").status_code, 302)
        self.client.force_login(self.u)
        self.assertEqual(self.client.get("/gerar").status_code, 405)
