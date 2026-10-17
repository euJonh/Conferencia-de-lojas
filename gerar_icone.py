"""Gera icone.ico (vários tamanhos) e icone.png a partir da imagem da pena.

Uso: python gerar_icone.py <imagem_da_pena.png>

O fundo cinza-escuro da imagem vira transparente, a pena é recortada, centralizada
num quadrado e ampliada para os tamanhos usados pelo Windows (16 a 256 px).
"""

import sys
from pathlib import Path

from PIL import Image

TAMANHOS = [16, 20, 24, 32, 40, 48, 64, 128, 256]
PASTA = Path(__file__).resolve().parent


def remover_fundo(im: Image.Image, tolerancia: int = 18, suavizar: int = 40) -> Image.Image:
    """Pixels parecidos com a cor do canto viram transparentes; a borda fica suave."""
    im = im.convert("RGBA")
    fundo = im.getpixel((0, 0))[:3]
    pixels = im.load()
    for y in range(im.height):
        for x in range(im.width):
            r, g, b, a = pixels[x, y]
            dist = max(abs(r - fundo[0]), abs(g - fundo[1]), abs(b - fundo[2]))
            if dist <= tolerancia:
                pixels[x, y] = (r, g, b, 0)
            elif dist < tolerancia + suavizar:
                alfa = int(255 * (dist - tolerancia) / suavizar)
                pixels[x, y] = (r, g, b, min(a, alfa))
    return im


def maior_faixa(im: Image.Image) -> Image.Image:
    """Mantém só a maior faixa de linhas com conteúdo (a pena), descartando
    elementos separados por linhas vazias (ex.: a cápsula cinza embaixo)."""
    alfa = im.getchannel("A")
    linhas = [any(alfa.getpixel((x, y)) > 40 for x in range(im.width)) for y in range(im.height)]
    faixas, ini = [], None
    for y, cheia in enumerate(linhas + [False]):
        if cheia and ini is None:
            ini = y
        elif not cheia and ini is not None:
            faixas.append((ini, y))
            ini = None
    topo, base = max(faixas, key=lambda f: f[1] - f[0])
    limpa = Image.new("RGBA", im.size, (0, 0, 0, 0))
    limpa.paste(im.crop((0, topo, im.width, base)), (0, topo))
    return limpa


def quadrado(im: Image.Image, margem: float = 0.04) -> Image.Image:
    caixa = im.getbbox()
    im = im.crop(caixa)
    lado = int(max(im.size) * (1 + 2 * margem))
    tela = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    tela.paste(im, ((lado - im.width) // 2, (lado - im.height) // 2), im)
    return tela


def main():
    origem = Path(sys.argv[1])
    base = quadrado(maior_faixa(remover_fundo(Image.open(origem))))
    grande = base.resize((256, 256), Image.LANCZOS)
    grande.save(PASTA / "icone.png")
    grande.save(PASTA / "icone.ico", sizes=[(t, t) for t in TAMANHOS])
    print("icone.ico e icone.png gerados a partir de", origem.name, base.size)


if __name__ == "__main__":
    main()
