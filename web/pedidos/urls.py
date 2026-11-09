from django.urls import path

from . import views

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("entrar", views.entrar, name="entrar"),
    path("sair", views.sair, name="sair"),
]
