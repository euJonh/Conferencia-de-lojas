from django.urls import path

from . import views

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("gerar", views.gerar, name="gerar"),
    path("lote", views.lote, name="lote"),
    path("gerar-lote", views.gerar_lote, name="gerar_lote"),
    path("configuracoes", views.configuracoes, name="configuracoes"),
    path("configuracoes/lojas", views.configuracoes_lojas, name="configuracoes_lojas"),
    path("configuracoes/modelo", views.configuracoes_modelo, name="configuracoes_modelo"),
    path("configuracoes/precos", views.configuracoes_precos, name="configuracoes_precos"),
    path("configuracoes/precos/remover", views.configuracoes_precos_remover,
         name="configuracoes_precos_remover"),
    path("configuracoes/lojas-por-arquivo", views.configuracoes_lojas_por_arquivo,
         name="configuracoes_lojas_por_arquivo"),
    path("entrar", views.entrar, name="entrar"),
    path("sair", views.sair, name="sair"),
    path("saude", views.saude, name="saude"),
]
