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


class AdminETests(TestCase):
    def test_staff_nao_superusuario_fora_do_admin(self):
        User.objects.create_user("func", password=SENHA, is_staff=True)
        self.client.login(username="func", password=SENHA)
        r = self.client.get("/admin/")
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r["Location"].startswith("/admin/login/"))

    def test_anonimo_fora_do_admin(self):
        r = self.client.get("/admin/")
        self.assertTrue(r["Location"].startswith("/admin/login/"))

    def test_superusuario_entra_no_admin(self):
        User.objects.create_superuser("chefe", password=SENHA)
        self.client.login(username="chefe", password=SENHA)
        self.assertEqual(self.client.get("/admin/").status_code, 200)

    def test_login_do_admin_tambem_bloqueia(self):
        User.objects.create_superuser("chefe", password=SENHA)
        for _ in range(5):
            self.client.post("/admin/login/", {"username": "chefe", "password": "x"})
        r = self.client.post("/admin/login/", {"username": "chefe", "password": SENHA})
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(TentativaLogin.objects.get(usuario="chefe").falhas, 5)


class DebugPadraoTests(TestCase):
    def _settings(self, **env):
        import os
        import subprocess
        import sys
        from pathlib import Path
        web = Path(__file__).resolve().parents[2]
        e = {k: v for k, v in os.environ.items() if k not in ("DEBUG", "SECRET_KEY", "DATABASE_URL")}
        e.update(env, DJANGO_SETTINGS_MODULE="site_conferencia.settings", PYTHONPATH=str(web))
        return subprocess.run(
            [sys.executable, "-c", "from django.conf import settings; print(settings.DEBUG)"],
            env=e, capture_output=True, text=True)

    def test_sem_variavel_debug_e_falso_e_exige_secret_key(self):
        r = self._settings()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("SECRET_KEY", r.stderr)
        r = self._settings(SECRET_KEY="x", ALLOWED_HOSTS="a", DATABASE_URL="sqlite:///x.db")
        self.assertEqual(r.stdout.strip(), "False")

    def test_producao_sem_database_url_nao_cai_no_sqlite(self):
        r = self._settings(SECRET_KEY="x", ALLOWED_HOSTS="a")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("DATABASE_URL", r.stderr)
        r = self._settings(DEBUG="1")  # desenvolvimento continua usando SQLite
        self.assertEqual(r.stdout.strip(), "True")
