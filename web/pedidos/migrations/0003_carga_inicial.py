"""Carga inicial: lojas.txt e modelo da raiz do projeto, se existirem."""
from django.conf import settings
from django.db import migrations

from conferencia import decodificar_texto


def carregar(apps, schema_editor):
    Configuracao = apps.get_model("pedidos", "Configuracao")
    if Configuracao.objects.filter(pk=1).exists():
        return
    lojas = settings.RAIZ / "lojas.txt"
    modelo = settings.RAIZ / "PLANILHA DE PEDIDOS.xlsx"
    Configuracao.objects.create(
        pk=1,
        lojas_texto=decodificar_texto(lojas.read_bytes()).replace("
", "
") if lojas.exists() else "",
        modelo=modelo.read_bytes() if modelo.exists() else b"",
        modelo_nome=modelo.name if modelo.exists() else "",
    )


class Migration(migrations.Migration):

    dependencies = [("pedidos", "0002_configuracao_alteracao")]

    operations = [migrations.RunPython(carregar, migrations.RunPython.noop)]
