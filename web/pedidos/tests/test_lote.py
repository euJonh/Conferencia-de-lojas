"""Testes da tela Gerar em lote e do endpoint /gerar-lote."""
import io
import json
import tempfile
import zipfile
from pathlib import Path

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from openpyxl import Workbook

from pedidos.models import Configuracao
from test_conferencia import criar_modelo

CODIGOS = ["20-050", "20-053", "20-054", "20-056", "20-057", "20-058", "20-059", "20-070", "20-1000"]
CABECALHO = ["COD_PP", "COD_ME", "20-1000 X", "20-059 X", "20-050 X", "20-070 X",
             "20-053 X", "20-054 X", "20-056 X", "20-057 X", "20-058 X"]


def bytes_planilha(marca: str, valor) -> bytes:
    wb = Workbook()
    wb.active.append(CABECALHO)
    wb.active.append([f"{marca}-PP", f"{marca}-ME"] + [valor] * 9)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


class LoteTests(TestCase):
    def setUp(self):
        self.u = User.objects.create_user("ana", password="x")
        self.client.force_login(self.u)
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "m.xlsx"
            criar_modelo(caminho)
            modelo = caminho.read_bytes()
        cfg = Configuracao.atual()
        cfg.lojas_texto = "\n".join(CODIGOS)
        cfg.modelo = modelo
        cfg.lojas_por_arquivo = 7
        cfg.save()

    def dois(self):
        return [SimpleUploadedFile("Pedido_NARS_a.xlsx", bytes_planilha("NARS", 1)),
                SimpleUploadedFile("Pedido_Shiseido_b.xlsx", bytes_planilha("Shiseido", "ME"))]

    def test_lote_gera_zip(self):
        r = self.client.post("/gerar-lote", {"planilhas": self.dois()})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "application/zip")
        self.assertEqual(r["Content-Disposition"], 'attachment; filename="PLANILHAS DE PEDIDOS.zip"')
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            self.assertEqual(z.namelist(), ["PLANILHA DE PEDIDOS - (1).xlsx",
                                            "PLANILHA DE PEDIDOS - (2).xlsx"])
            self.assertTrue(z.read(z.namelist()[0]).startswith(b"PK"))
        resumo = json.loads(r["X-Resumo"])
        self.assertEqual(resumo["planilhas"], 2)
        self.assertEqual(resumo["arquivos"][0]["lojas"], "20-050 a 20-059")
        self.assertEqual(resumo["arquivos"][1]["lojas"], "20-070 a 20-1000")
        self.assertEqual(resumo["linhas"], sum(a["linhas"] for a in resumo["arquivos"]))
        for chave in ("sem_preco", "tem_precos"):
            self.assertIn(chave, resumo)

    def test_lote_usa_lojas_por_arquivo_da_config(self):
        cfg = Configuracao.atual()
        cfg.lojas_por_arquivo = 1
        cfg.save()
        r = self.client.post("/gerar-lote", {"planilhas": self.dois()})
        self.assertEqual(r.status_code, 200)
        resumo = json.loads(r["X-Resumo"])
        self.assertEqual(len(resumo["arquivos"]), 9)
        self.assertEqual(resumo["arquivos"][0]["lojas"], "20-050")

    def test_lote_vazio(self):
        r = self.client.post("/gerar-lote", {})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["erro"], "Nenhuma planilha anexada.")

    def test_lote_mais_de_30(self):
        arqs = [SimpleUploadedFile(f"Pedido_NARS_{i}.xlsx", bytes_planilha("NARS", 1))
                for i in range(31)]
        r = self.client.post("/gerar-lote", {"planilhas": arqs})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["erro"], "Envie no máximo 30 planilhas por vez.")

    def test_mesmo_arquivo_duas_vezes(self):
        um = self.client.post("/gerar-lote", {"planilhas": self.dois()[:1]})
        dois = self.client.post("/gerar-lote", {"planilhas": [
            SimpleUploadedFile("Pedido_NARS_a.xlsx", bytes_planilha("NARS", 1)),
            SimpleUploadedFile("Pedido_NARS_a.xlsx", bytes_planilha("NARS", 1))]})
        self.assertEqual(dois.status_code, 200)
        self.assertEqual(json.loads(dois["X-Resumo"])["linhas"],
                         2 * json.loads(um["X-Resumo"])["linhas"])

    def test_erro_diz_qual_planilha(self):
        arqs = self.dois() + [SimpleUploadedFile("Pedido_Lancome_c.xlsx", b"abc")]
        r = self.client.post("/gerar-lote", {"planilhas": arqs})
        self.assertEqual(r.status_code, 400)
        self.assertIn("Pedido_Lancome_c.xlsx", r.json()["erro"])

    def test_exige_login_e_post(self):
        self.client.logout()
        self.assertEqual(self.client.post("/gerar-lote").status_code, 401)
        self.client.force_login(self.u)
        self.assertEqual(self.client.get("/gerar-lote").status_code, 405)

    def test_tela_e_config_incompleta(self):
        self.assertContains(self.client.get("/lote"), 'multiple')
        self.assertContains(self.client.get("/"), 'href="/lote"')
        cfg = Configuracao.atual()
        cfg.modelo = b""
        cfg.save()
        r = self.client.get("/lote")
        self.assertContains(r, "/configuracoes")
        self.assertNotContains(r, 'type="file"')
        self.assertEqual(self.client.post("/gerar-lote", {"planilhas": self.dois()}).status_code, 409)
