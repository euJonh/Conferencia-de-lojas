"""Testes de limites de envio, saúde, logs, rascunho das lojas e extras de robustez."""
import io
import zipfile
from unittest import mock

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.http import HttpResponse
from django.test import Client, RequestFactory, TestCase, override_settings
from django.test.utils import CaptureQueriesContext

from pedidos import servicos
from pedidos.middleware import LimiteTamanhoMiddleware, LIMITE_ENVIO, LIMITE_LOTE, MSG_ENVIO_GRANDE, MSG_LOTE_GRANDE
from pedidos.models import Configuracao
from pedidos.tests.test_configuracoes import modelo_valido
from pedidos.tests.test_servicos import planilha_precos


class TamanhoEnvioTests(TestCase):
    def setUp(self):
        self.u = User.objects.create_user("ana", password="x")

    def postar(self, url, tamanho, entrar=True):
        if entrar:
            self.client.force_login(self.u)
        return self.client.post(url, {"x": "1"}, CONTENT_LENGTH=str(tamanho))

    def test_lote_acima_de_100mb(self):
        r = self.postar("/gerar-lote", LIMITE_LOTE + 1)
        self.assertEqual(r.status_code, 413)
        self.assertEqual(r.json(), {"erro": MSG_LOTE_GRANDE})
        self.assertIn("100 MB", MSG_LOTE_GRANDE)

    def passa(self, url, tamanho):
        """True se o middleware deixa a requisição seguir (corpo de mentira, não é lido)."""
        req = RequestFactory().post(url, {"x": "1"}, CONTENT_LENGTH=str(tamanho))
        resp = LimiteTamanhoMiddleware(lambda r: HttpResponse("seguiu"))(req)
        return resp.status_code == 200

    def test_lote_no_limite_passa(self):
        self.assertTrue(self.passa("/gerar-lote", LIMITE_LOTE))

    def test_outros_posts_acima_de_12mb(self):
        for url in ("/gerar", "/configuracoes/modelo", "/entrar"):
            r = self.postar(url, LIMITE_ENVIO + 1)
            self.assertEqual(r.status_code, 413, url)
            self.assertEqual(r.json(), {"erro": MSG_ENVIO_GRANDE}, url)

    def test_lote_pode_passar_de_12mb(self):
        self.assertTrue(self.passa("/gerar-lote", LIMITE_ENVIO + 1))
        self.assertTrue(self.passa("/gerar", LIMITE_ENVIO))

    def test_anonimo_tambem_e_barrado_sem_ler_o_corpo(self):
        with mock.patch("django.http.request.HttpRequest._load_post_and_files") as ler:
            r = self.postar("/gerar-lote", LIMITE_LOTE + 1, entrar=False)
        self.assertEqual(r.status_code, 413)
        ler.assert_not_called()

    def test_multipart_sem_tamanho_valido_e_recusado(self):
        self.client.force_login(self.u)
        for valor in ("", "abc", "-5"):
            r = self.client.post("/gerar-lote", {"x": "1"}, CONTENT_LENGTH=valor)
            self.assertEqual(r.status_code, 413, valor)

    def test_get_nao_e_limitado(self):
        self.client.force_login(self.u)
        self.assertEqual(self.client.get("/", CONTENT_LENGTH=str(LIMITE_LOTE * 2)).status_code, 200)

    def test_anonimo_com_31_arquivos_nao_ganha_json_de_lote(self):
        arquivos = [SimpleUploadedFile(f"{n}.xlsx", b"x") for n in range(31)]
        r = self.client.post("/gerar-lote", {"planilhas": arquivos})
        self.assertEqual(r.status_code, 401)
        self.assertNotIn("planilhas por vez", r.content.decode())

    def test_logado_com_31_arquivos_continua_com_json(self):
        self.client.force_login(self.u)
        arquivos = [SimpleUploadedFile(f"{n}.xlsx", b"x") for n in range(31)]
        r = self.client.post("/gerar-lote", {"planilhas": arquivos})
        self.assertEqual(r.status_code, 400)
        self.assertIn("no máximo 30", r.json()["erro"])

    def test_tela_do_lote_informa_limite_para_o_js(self):
        self.client.force_login(self.u)
        cfg = Configuracao.atual()
        cfg.lojas_texto, cfg.modelo = "20-050", modelo_valido()
        cfg.save()
        r = self.client.get("/lote")
        self.assertContains(r, f'data-limite="{LIMITE_LOTE}"')
        self.assertContains(r, "data-msg-limite=")


class SaudeTests(TestCase):
    def test_saude_sem_login(self):
        r = self.client.get("/saude")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content, b"ok")

    @override_settings(SECURE_SSL_REDIRECT=True)
    def test_saude_nao_redireciona_para_https(self):
        self.assertEqual(self.client.get("/saude").status_code, 200)
        self.assertEqual(self.client.get("/entrar").status_code, 301)


class LogsTests(TestCase):
    def test_configuracao_de_logs(self):
        from django.conf import settings
        self.assertEqual(settings.LOGGING["root"]["level"], "INFO")
        for nome in ("django", "pedidos"):
            self.assertEqual(settings.LOGGING["loggers"][nome]["level"], "INFO")
        self.assertEqual(settings.LOGGING["loggers"]["django.request"]["level"], "ERROR")
        self.assertEqual(settings.LOGGING["handlers"]["console"]["stream"], "ext://sys.stderr")

    def test_erro_inesperado_em_view_vai_para_o_log_com_traceback(self):
        u = User.objects.create_user("ana", password="x")
        c = Client(raise_request_exception=False)
        c.force_login(u)
        with mock.patch("pedidos.views.Configuracao.atual", side_effect=RuntimeError("boom")):
            with self.assertLogs("django.request", "ERROR") as cm:
                r = c.get("/configuracoes")
        self.assertEqual(r.status_code, 500)
        self.assertIsNotNone(cm.records[0].exc_info)
        self.assertIn("boom", str(cm.records[0].exc_info[1]))


class RascunhoLojasTests(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_user("ana", password="x"))
        cfg = Configuracao.atual()
        cfg.lojas_texto = "20-256"
        cfg.save()

    def test_texto_invalido_volta_no_campo(self):
        texto = "20-073\nabc\n20-100"
        r = self.client.post("/configuracoes/lojas", {"lojas_texto": texto}, follow=True)
        self.assertContains(r, "linha 2: abc")
        self.assertIn(">" + texto + "</textarea>", r.content.decode())
        self.assertEqual(Configuracao.atual().lojas_texto, "20-256")
        # só vale uma vez
        r = self.client.get("/configuracoes")
        self.assertIn(">20-256</textarea>", r.content.decode())

    def test_texto_valido_nao_deixa_rascunho(self):
        self.client.post("/configuracoes/lojas", {"lojas_texto": "20-073"}, follow=True)
        self.assertNotIn("lojas_rascunho", self.client.session)


class ResumoLimitadoTests(TestCase):
    def test_resumo_de_um_corta_listas(self):
        faltando = [mock.Mock(codigo=f"20-{n:03d}") for n in range(35)]
        r = mock.Mock(pedidos=[], encontradas=[], lojas=[], duplicadas=[], faltando=faltando,
                      nao_reconhecidas=[], sem_preco=[f"P{n}" for n in range(50)], marca="X")
        with mock.patch.object(servicos, "carregar", return_value=({}, b"m", None, 7)), \
                mock.patch.object(servicos.c, "processar_bytes", return_value=(b"x", r)):
            _, resumo = servicos.gerar_um("a.xlsx", b"")
        self.assertEqual(servicos.MAX_ITENS_RESUMO, 20)
        self.assertEqual(len(resumo["faltando"]), 20)
        self.assertEqual(resumo["faltando_qtd"], 35)
        self.assertEqual(len(resumo["sem_preco"]), 20)
        self.assertEqual(resumo["sem_preco_qtd"], 50)

    def test_resumo_de_lote_corta_sem_preco(self):
        r = mock.Mock(planilhas=[], arquivos=[], sem_preco=[f"P{n}" for n in range(50)])
        with mock.patch.object(servicos, "carregar", return_value=({}, b"m", None, 7)), \
                mock.patch.object(servicos.c, "processar_lote_bytes", return_value=r):
            _, resumo = servicos.gerar_lote([])
        self.assertEqual(len(resumo["sem_preco"]), 20)
        self.assertEqual(resumo["sem_preco_qtd"], 50)


class ConfigCompletaTests(TestCase):
    def test_config_completa(self):
        cfg = Configuracao.atual()  # a migração de carga inicial já preenche; começa vazio
        cfg.lojas_texto, cfg.modelo = "", b""
        cfg.save()
        self.assertFalse(servicos.config_completa())
        cfg.lojas_texto = "20-050"
        cfg.save()
        self.assertFalse(servicos.config_completa())  # falta o modelo
        cfg.modelo = modelo_valido()
        cfg.lojas_texto = "ruim"
        cfg.save()
        self.assertFalse(servicos.config_completa())  # lista sem lojas
        cfg.lojas_texto = "20-050"
        cfg.save()
        self.assertTrue(servicos.config_completa())

    def test_paginas_nao_leem_a_planilha_de_precos(self):
        self.client.force_login(User.objects.create_user("ana", password="x"))
        cfg = Configuracao.atual()
        cfg.lojas_texto, cfg.modelo = "20-050", modelo_valido()
        cfg.precos, cfg.precos_nome = planilha_precos(), "p.xlsx"
        cfg.save()
        with mock.patch.object(servicos, "ler_precos_bytes") as ler:
            self.assertEqual(self.client.get("/").status_code, 200)
            self.assertEqual(self.client.get("/lote").status_code, 200)
        ler.assert_not_called()

    def test_nao_carrega_o_blob_de_precos(self):
        cfg = Configuracao.atual()
        cfg.precos = b"X" * 1000
        cfg.save()
        with CaptureQueriesContext(connection) as q:
            servicos.config_completa()
        self.assertFalse(any('"precos"' in s["sql"] for s in q.captured_queries))


class ModeloInutilizavelTests(TestCase):
    def test_modelo_sem_arquivo_da_aba_e_recusado(self):
        entrada = zipfile.ZipFile(io.BytesIO(modelo_valido()))
        saida = io.BytesIO()
        with zipfile.ZipFile(saida, "w") as z:
            for info in entrada.infolist():
                if info.filename.startswith("xl/worksheets/"):
                    continue
                z.writestr(info.filename, entrada.read(info.filename))
        u = User.objects.create_user("ana", password="x")
        antes = Configuracao.atual().modelo_nome
        with self.assertRaises(servicos.ErroConferencia) as cm:
            servicos.salvar_modelo("quebrado.xlsx", saida.getvalue(), u)
        self.assertEqual(str(cm.exception), "O modelo não pôde ser usado para gerar a planilha.")
        self.assertEqual(Configuracao.atual().modelo_nome, antes)


class GravarTests(TestCase):
    def test_grava_so_o_campo_alterado(self):
        u = User.objects.create_user("ana", password="x")
        cfg = Configuracao.atual()
        cfg.lojas_texto = "20-050"
        cfg.save()
        original = Configuracao.save

        def salvar(self, *a, **k):
            # outra sessão muda lojas_texto depois de a linha ser lida e antes do save
            Configuracao.objects.filter(pk=1).update(lojas_texto="20-999")
            return original(self, *a, **k)

        with mock.patch.object(Configuracao, "save", salvar):
            servicos.salvar_lojas_por_arquivo(3, u)
        atual = Configuracao.atual()
        self.assertEqual(atual.lojas_por_arquivo, 3)
        self.assertEqual(atual.lojas_texto, "20-999")
        self.assertEqual(atual.atualizado_por, u)
