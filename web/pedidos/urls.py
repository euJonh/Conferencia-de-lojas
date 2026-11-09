from django.urls import path

from . import views

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("gerar", views.gerar, name="gerar"),
    path("lote", views.lote, name="lote"),
    path("gerar-lote", views.gerar_lote, name="gerar_lote"),
    path("entrar", views.entrar, name="entrar"),
    path("sair", views.sair, name="sair"),
]
