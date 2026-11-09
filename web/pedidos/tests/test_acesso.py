"""Testes de login, bloqueio por tentativas e acesso."""
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from pedidos.models import TentativaLogin

SENHA = "senha-forte-123"


class AcessoTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user("maria", password=SENHA)

    def test_sem_login_redireciona_para_entrar(self):
        r = self.client.get("/")
        self.assertRedirects(r, "/entrar?next=/", fetch_redirect_response=False)

    def test_entrar_com_senha_certa(self):
        r = self.client.post("/entrar", {"username": "maria", "password": SENHA})
        self.assertRedirects(r, "/", fetch_redirect_response=False)
        self.assertIn("_auth_user_id", self.client.session)

    def test_senha_errada_mostra_mensagem(self):
        r = self.client.post("/entrar", {"username": "maria", "password": "errada"})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Usuário ou senha incorretos.")

    def test_bloqueio_apos_5_erros(self):
        for _ in range(5):
            self.client.post("/entrar", {"username": "maria", "password": "errada"})
        r = self.client.post("/entrar", {"username": "maria", "password": SENHA})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Muitas tentativas. Tente novamente em 15 minutos.")
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(TentativaLogin.objects.get(usuario="maria").falhas, 5)

    def test_bloqueio_expirado_entra_e_zera(self):
        TentativaLogin.objects.create(
            usuario="maria", falhas=5,
            bloqueado_ate=timezone.now() - timedelta(minutes=1))
        r = self.client.post("/entrar", {"username": "maria", "password": SENHA})
        self.assertRedirects(r, "/", fetch_redirect_response=False)
        t = TentativaLogin.objects.get(usuario="maria")
        self.assertEqual(t.falhas, 0)
        self.assertIsNone(t.bloqueado_ate)

    def test_erro_apos_bloqueio_expirado_recomeca_contagem(self):
        TentativaLogin.objects.create(
            usuario="maria", falhas=5,
            bloqueado_ate=timezone.now() - timedelta(minutes=1))
        r = self.client.post("/entrar", {"username": "maria", "password": "errada"})
        self.assertContains(r, "Usuário ou senha incorretos.")
        t = TentativaLogin.objects.get(usuario="maria")
        self.assertEqual(t.falhas, 1)
        self.assertIsNone(t.bloqueado_ate)

    def test_usuario_comum_nao_entra_no_admin(self):
        self.client.login(username="maria", password=SENHA)
        r = self.client.get("/admin/")
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r["Location"].startswith("/admin/login/"))

    def test_sair(self):
        self.client.login(username="maria", password=SENHA)
        r = self.client.post("/sair")
        self.assertRedirects(r, "/entrar", fetch_redirect_response=False)
        self.assertNotIn("_auth_user_id", self.client.session)
