"""Interface gráfica (tkinter) da Conferência de Lojas.

Menu lateral com três telas:
- Início: botão para anexar a planilha, animação enquanto o novo .xlsx é gerado
  e o resultado com atalhos para abrir o arquivo ou a pasta.
- Gerar em lote: várias planilhas de uma vez, divididas em arquivos de 7 lojas.
- Configurações: pasta onde os .xlsx são gerados, lojas por arquivo no lote e a
  planilha de preços (tudo salvo em %APPDATA%/ConferenciaLojas).
"""

from __future__ import annotations

import json
import math
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog

import conferencia as c

TITULO_APP = "Conferência de Lojas"
FONTE = "Segoe UI"

COR = {
    "lateral": "#111827",
    "lateral_hover": "#1F2937",
    "lateral_texto": "#9CA3AF",
    "lateral_ativo": "#FFFFFF",
    "fundo": "#F3F4F6",
    "cartao": "#FFFFFF",
    "borda": "#E5E7EB",
    "texto": "#111827",
    "suave": "#6B7280",
    "destaque": "#4F46E5",
    "destaque_hover": "#4338CA",
    "trilho": "#E0E7FF",
    "ok": "#16A34A",
    "erro": "#DC2626",
    "secundario": "#EEF2FF",
    "secundario_hover": "#E0E7FF",
}

# A animação fica na tela pelo menos este tempo, mesmo que a geração seja instantânea.
TEMPO_MINIMO_ANIMACAO = 1.2
ETAPAS = 5  # quantidade de chamadas de progresso em conferencia.processar
MIN_LOJAS_POR_ARQUIVO, MAX_LOJAS_POR_ARQUIVO = 1, 99

# Fator da escala do Windows (1.0 = 100%, 1.5 = 150%...). As fontes já escalam
# sozinhas; medidas em pixels passam por px() para acompanhar.
ESCALA = 1.0


def px(valor: float) -> int:
    return int(round(valor * ESCALA))


# ---------------------------------------------------------------------------
# Configuração persistente
# ---------------------------------------------------------------------------

def arquivo_config() -> Path:
    base = Path(os.environ.get("APPDATA") or Path.home())
    return base / "ConferenciaLojas" / "config.json"


def arquivo_precos() -> Path:
    """Cópia da planilha de preços anexada em Configurações."""
    return arquivo_config().parent / "precos.xlsx"


def carregar_config() -> dict:
    try:
        dados = json.loads(arquivo_config().read_text(encoding="utf-8"))
        return dados if isinstance(dados, dict) else {}
    except (OSError, ValueError):
        return {}


def salvar_config(config: dict) -> None:
    caminho = arquivo_config()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Componentes
# ---------------------------------------------------------------------------

class Botao(tk.Label):
    """Botão plano com efeito de hover."""

    def __init__(self, pai, texto, comando, cor="destaque", cor_hover="destaque_hover",
                 cor_texto="#FFFFFF", tamanho=10, padx=18, pady=9, negrito=True):
        super().__init__(pai, text=texto, bg=COR[cor], fg=cor_texto, cursor="hand2",
                         font=(FONTE, tamanho, "bold" if negrito else "normal"), padx=px(padx), pady=px(pady))
        self._cor, self._cor_hover, self._cor_texto = COR[cor], COR[cor_hover], cor_texto
        self._primario = cor == "destaque"
        self._comando = comando
        self._ativo = True
        self.bind("<Enter>", lambda _e: self._ativo and self.config(bg=self._cor_hover))
        self.bind("<Leave>", lambda _e: self._ativo and self.config(bg=self._cor))
        self.bind("<Button-1>", lambda _e: self._ativo and self._comando())

    def habilitar(self, ativo: bool) -> None:
        self._ativo = ativo
        if ativo:
            self.config(bg=self._cor, fg=self._cor_texto, cursor="hand2")
        elif self._primario:
            self.config(bg="#A5B4FC", fg="#FFFFFF", cursor="arrow")
        else:
            self.config(bg=COR["fundo"], fg="#9CA3AF", cursor="arrow")


class Indicador(tk.Canvas):
    """Spinner animado durante a geração; vira um check (sucesso) ou um X (erro)."""

    def __init__(self, pai, fundo, tamanho=60):
        self.TAM = px(tamanho)
        super().__init__(pai, width=self.TAM, height=self.TAM, bg=fundo, highlightthickness=0)
        self._job = None
        self._inicio = 0.0

    def _parar(self):
        if self._job:
            self.after_cancel(self._job)
            self._job = None
        self.delete("all")

    def girar(self):
        self._parar()
        self._inicio = time.perf_counter()
        m, w = px(7), px(6)
        self.create_oval(m, m, self.TAM - m, self.TAM - m, outline=COR["trilho"], width=w)
        self._arco = self.create_arc(m, m, self.TAM - m, self.TAM - m, start=90, extent=90,
                                     style="arc", outline=COR["destaque"], width=w)
        self._quadro_giro()

    def _quadro_giro(self):
        t = time.perf_counter() - self._inicio
        inicio = (90 - t * 360) % 360                       # uma volta por segundo
        extensao = 60 + 100 * (0.5 + 0.5 * math.sin(t * 4))  # arco "respira"
        self.itemconfig(self._arco, start=inicio, extent=extensao)
        self._job = self.after(16, self._quadro_giro)

    def sucesso(self):
        self._desenhar_simbolo(COR["ok"], [[(0.30, 0.52), (0.44, 0.66), (0.71, 0.37)]])

    def erro(self):
        self._desenhar_simbolo(COR["erro"], [[(0.34, 0.34), (0.66, 0.66)], [(0.66, 0.34), (0.34, 0.66)]])

    def _desenhar_simbolo(self, cor, tracos):
        """Círculo colorido e traços brancos desenhados progressivamente (~0,35 s)."""
        self._parar()
        m = max(1, round(self.TAM * 0.07))
        self.create_oval(m, m, self.TAM - m, self.TAM - m, fill=cor, outline=cor)
        pontos = [[(x * self.TAM, y * self.TAM) for x, y in t] for t in tracos]
        inicio = time.perf_counter()

        def quadro():
            p = min((time.perf_counter() - inicio) / 0.35, 1.0)
            self.delete("traco")
            for traco in pontos:
                comprimentos = [math.dist(a, b) for a, b in zip(traco, traco[1:])]
                falta = sum(comprimentos) * p
                coords = [traco[0]]
                for (a, b), comp in zip(zip(traco, traco[1:]), comprimentos):
                    if falta <= 0:
                        break
                    f = min(falta / comp, 1.0)
                    coords.append((a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f))
                    falta -= comp
                if len(coords) > 1:
                    self.create_line(*[v for xy in coords for v in xy], fill="#FFFFFF", width=max(2, round(self.TAM * 0.085)),
                                     capstyle="round", joinstyle="round", tags="traco")
            self._job = self.after(16, quadro) if p < 1 else None

        quadro()


class BarraProgresso(tk.Canvas):
    """Barra que desliza suavemente até o valor alvo (0 a 1)."""

    def __init__(self, pai, fundo, largura=360, altura=8):
        largura, altura = px(largura), px(altura)
        super().__init__(pai, width=largura, height=altura, bg=fundo, highlightthickness=0)
        self._l, self._a = largura, altura
        self._atual = self._alvo = 0.0
        self.create_rectangle(0, 0, largura, altura, fill=COR["trilho"], outline="")
        self._barra = self.create_rectangle(0, 0, 0, altura, fill=COR["destaque"], outline="")
        self._job = None

    def definir(self, alvo: float, cor: str | None = None, imediato: bool = False):
        self._alvo = max(0.0, min(alvo, 1.0))
        if cor:
            self.itemconfig(self._barra, fill=cor)
        if imediato:
            self._atual = self._alvo
        if not self._job:
            self._quadro()

    def _quadro(self):
        self._atual += (self._alvo - self._atual) * 0.18
        if abs(self._alvo - self._atual) < 0.002:
            self._atual = self._alvo
        self.coords(self._barra, 0, 0, self._l * self._atual, self._a)
        self._job = self.after(16, self._quadro) if self._atual != self._alvo else None


def cartao(pai) -> tk.Frame:
    return tk.Frame(pai, bg=COR["cartao"], highlightthickness=1, highlightbackground=COR["borda"])


def rotulo(pai, texto="", tamanho=10, cor="texto", negrito=False, fundo="cartao", **kw) -> tk.Label:
    return tk.Label(pai, text=texto, bg=COR[fundo], fg=COR[cor],
                    font=(FONTE, tamanho, "bold" if negrito else "normal"), **kw)


class PainelStatus(tk.Frame):
    """Cartão que mostra o estado da geração: ocioso, gerando, sucesso ou erro."""

    def __init__(self, pai):
        super().__init__(pai, bg=COR["cartao"], highlightthickness=1, highlightbackground=COR["borda"])
        corpo = tk.Frame(self, bg=COR["cartao"])
        corpo.place(relx=0.5, rely=0.5, anchor="center")
        self.indicador = Indicador(corpo, COR["cartao"])
        # Linha do título; no modo compacto leva um check pequeno ao lado.
        self.linha_titulo = tk.Frame(corpo, bg=COR["cartao"])
        self.linha_titulo.pack()
        self.indicador_mini = Indicador(self.linha_titulo, COR["cartao"], tamanho=30)
        self.lbl_titulo = rotulo(self.linha_titulo, "", 14, negrito=True)
        self.lbl_titulo.pack(side="left")
        self.lbl_texto = rotulo(corpo, "", 9, "suave", justify="center", wraplength=px(560))
        self.lbl_texto.pack(pady=(6, 0))
        self.barra = BarraProgresso(corpo, COR["cartao"])
        self.detalhes = tk.Frame(corpo, bg=COR["cartao"])
        self.acoes = tk.Frame(corpo, bg=COR["cartao"])

    def _limpar(self):
        self.indicador_mini.pack_forget()
        for w in (self.barra, self.detalhes, self.acoes):
            w.pack_forget()
        for quadro in (self.detalhes, self.acoes):
            for w in quadro.winfo_children():
                w.destroy()

    def ocioso(self, titulo: str, texto: str):
        self._limpar()
        self.indicador.delete("all")
        self.indicador.pack_forget()
        self.lbl_titulo.config(text=titulo, fg=COR["texto"])
        self.lbl_texto.config(text=texto)

    def gerando(self, texto: str):
        self._limpar()
        self.indicador.pack(pady=(0, px(10)), before=self.linha_titulo)
        self.indicador.girar()
        self.lbl_titulo.config(text="Gerando...", fg=COR["texto"])
        self.lbl_texto.config(text=texto)
        self.barra.pack(pady=(px(16), 0))
        self.barra.definir(0.0, COR["destaque"], imediato=True)
        self.barra.definir(0.05)

    def etapa(self, texto: str, fracao: float):
        self.lbl_texto.config(text=f"{texto}...")
        self.barra.definir(0.05 + 0.85 * fracao)

    def concluir_barra(self):
        self.barra.definir(1.0, COR["ok"])

    def sucesso(self, titulo: str, texto: str, pares: list[tuple[str, str]], botoes, largura_valor=230,
                colunas=2, compacto=False):
        """`pares` vira uma grade de `colunas` colunas; `botoes` = [(texto, comando, primario)].
        `compacto` troca o check grande por um pequeno ao lado do título, para caber mais conteúdo."""
        self._limpar()
        if compacto:
            self.indicador.delete("all")
            self.indicador.pack_forget()
            self.indicador_mini.pack(side="left", padx=(0, px(10)), before=self.lbl_titulo)
            self.indicador_mini.sucesso()
        else:
            self.indicador.pack(pady=(0, px(10)), before=self.linha_titulo)
            self.indicador.sucesso()
        self.lbl_titulo.config(text=titulo, fg=COR["ok"])
        self.lbl_texto.config(text=texto)
        for i, (nome, valor) in enumerate(pares):
            lin, col = i // colunas, (i % colunas) * 2  # pares nome/valor lado a lado
            rotulo(self.detalhes, nome, 9, "suave").grid(row=lin, column=col, sticky="w", padx=(0, px(8)), pady=1)
            rotulo(self.detalhes, valor, 9, negrito=True, wraplength=px(largura_valor), justify="left").grid(
                row=lin, column=col + 1, sticky="w", padx=(0, px(24)), pady=1)
        self.detalhes.pack(pady=(px(12), 0))
        for texto_botao, comando, primario in botoes:
            if primario:
                Botao(self.acoes, texto_botao, comando).pack(side="left", padx=px(5))
            else:
                Botao(self.acoes, texto_botao, comando, cor="secundario", cor_hover="secundario_hover",
                      cor_texto=COR["destaque"]).pack(side="left", padx=px(5))
        self.acoes.pack(pady=(px(16), 0))

    def erro(self, mensagem: str):
        self._limpar()
        self.indicador.pack(pady=(0, px(10)), before=self.linha_titulo)
        self.indicador.erro()
        self.lbl_titulo.config(text="Não foi possível gerar a planilha", fg=COR["erro"])
        self.lbl_texto.config(text=mensagem)


def cabecalho_tela(tela, titulo: str, subtitulo: str) -> tk.Label:
    rotulo(tela, titulo, 20, negrito=True, fundo="fundo").pack(anchor="w")
    sub = rotulo(tela, subtitulo, 10, "suave", fundo="fundo", wraplength=px(640), justify="left")
    sub.pack(anchor="w", pady=(4, px(16)))
    return sub


def abrir_na_pasta(arquivo: Path):
    subprocess.run(["explorer", "/select,", str(arquivo)])


# ---------------------------------------------------------------------------
# Aplicação
# ---------------------------------------------------------------------------

class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.config = carregar_config()
        self.pasta_programa = c.pasta_do_programa()
        self.fila: queue.Queue = queue.Queue()
        self.processando = False
        self.lote_arquivos: list[Path] = []

        global ESCALA
        ESCALA = max(root.winfo_fpixels("1i") / 96, 1.0)

        root.title(TITULO_APP)
        root.configure(bg=COR["fundo"])
        tela_l, tela_a = root.winfo_screenwidth(), root.winfo_screenheight()
        largura, altura = min(px(920), int(tela_l * 0.92)), min(px(640), int(tela_a * 0.82))
        root.minsize(min(px(780), largura), min(px(600), altura))
        x, y = (tela_l - largura) // 2, (tela_a - altura) // 4
        root.geometry(f"{largura}x{altura}+{max(x, 0)}+{max(y, 0)}")

        self._montar_lateral()
        self.conteudo = tk.Frame(root, bg=COR["fundo"])
        self.conteudo.pack(side="left", fill="both", expand=True)
        self.telas = {"inicio": self._tela_inicio(), "lote": self._tela_lote(), "config": self._tela_config()}
        self._atualizar_destino()
        self.mostrar("inicio")

    # --- menu lateral -------------------------------------------------------

    def _montar_lateral(self):
        lateral = tk.Frame(self.root, bg=COR["lateral"], width=px(210))
        lateral.pack(side="left", fill="y")
        lateral.pack_propagate(False)

        tk.Label(lateral, text="Conferência\nde Lojas", justify="left", bg=COR["lateral"], fg="#FFFFFF",
                 font=(FONTE, 15, "bold")).pack(anchor="w", padx=px(22), pady=(px(26), 4))
        tk.Label(lateral, text="Gerador de pedidos", bg=COR["lateral"], fg=COR["lateral_texto"],
                 font=(FONTE, 9)).pack(anchor="w", padx=px(22), pady=(0, px(26)))

        self.itens_menu = {}
        for chave, texto in (("inicio", "Início"), ("lote", "Gerar em lote"), ("config", "Configurações")):
            item = tk.Frame(lateral, bg=COR["lateral"], cursor="hand2")
            item.pack(fill="x", pady=1)
            marca = tk.Frame(item, bg=COR["lateral"], width=px(4))
            marca.pack(side="left", fill="y")
            lbl = tk.Label(item, text=texto, anchor="w", bg=COR["lateral"], fg=COR["lateral_texto"],
                           font=(FONTE, 11), padx=px(18), pady=px(10), cursor="hand2")
            lbl.pack(side="left", fill="x", expand=True)
            for w in (item, lbl):
                w.bind("<Button-1>", lambda _e, k=chave: self.mostrar(k))
                w.bind("<Enter>", lambda _e, k=chave: self._hover_menu(k, True))
                w.bind("<Leave>", lambda _e, k=chave: self._hover_menu(k, False))
            self.itens_menu[chave] = (item, marca, lbl)

        tk.Label(lateral, text="v1.1", bg=COR["lateral"], fg="#4B5563",
                 font=(FONTE, 8)).pack(side="bottom", anchor="w", padx=px(22), pady=px(14))

    def _hover_menu(self, chave, dentro):
        if chave == self.tela_atual:
            return
        cor = COR["lateral_hover"] if dentro else COR["lateral"]
        item, marca, lbl = self.itens_menu[chave]
        for w in (item, marca, lbl):
            w.config(bg=cor)

    def mostrar(self, nome: str):
        self.tela_atual = nome
        for chave, (item, marca, lbl) in self.itens_menu.items():
            ativo = chave == nome
            fundo = COR["lateral_hover"] if ativo else COR["lateral"]
            item.config(bg=fundo)
            lbl.config(bg=fundo, fg=COR["lateral_ativo"] if ativo else COR["lateral_texto"],
                       font=(FONTE, 11, "bold" if ativo else "normal"))
            marca.config(bg=COR["destaque"] if ativo else fundo)
        for tela in self.telas.values():
            tela.pack_forget()
        self.telas[nome].pack(fill="both", expand=True, padx=px(32), pady=px(26))
        if nome == "config":
            self._atualizar_config()

    def _atualizar_destino(self):
        pasta = self.pasta_saida()
        for lbl, padrao in ((self.lbl_destino_inicio, "mesma pasta da planilha anexada"),
                            (self.lbl_destino_lote, "mesma pasta da primeira planilha da lista")):
            lbl.config(text=f"Destino: {pasta if pasta else padrao}   (altere em Configurações)")

    # --- tela Início --------------------------------------------------------

    def _tela_inicio(self) -> tk.Frame:
        tela = tk.Frame(self.conteudo, bg=COR["fundo"])
        cabecalho_tela(tela, "Gerar planilha de pedidos",
                       f"Anexe a planilha Pedido_MARCA_....xlsx para gerar a {c.NOME_SAIDA}.")

        anexo = cartao(tela)
        anexo.pack(fill="x")
        interno = tk.Frame(anexo, bg=COR["cartao"])
        interno.pack(fill="x", padx=px(24), pady=px(20))
        # O botão é empacotado primeiro para nunca ser espremido pelo texto.
        self.btn_anexar = Botao(interno, "Anexar planilha .xlsx", self.anexar, tamanho=11, padx=22, pady=11)
        self.btn_anexar.pack(side="right", padx=(px(16), 0))
        textos = tk.Frame(interno, bg=COR["cartao"])
        textos.pack(side="left", fill="x", expand=True)
        rotulo(textos, "Planilha do pedido", 12, negrito=True).pack(anchor="w")
        self.lbl_destino_inicio = rotulo(textos, "", 9, "suave", justify="left", anchor="w", wraplength=px(400))
        self.lbl_destino_inicio.pack(anchor="w", pady=(4, 0))

        self.status_inicio = PainelStatus(tela)
        self.status_inicio.pack(fill="both", expand=True, pady=(px(16), 0))
        self.status_inicio.ocioso("Nenhuma planilha anexada", "Clique em \"Anexar planilha .xlsx\" para começar.")
        return tela

    def anexar(self):
        if self.processando:
            return
        escolhido = filedialog.askopenfilename(
            title="Selecione a planilha do pedido",
            filetypes=[("Planilhas Excel", "*.xlsx *.xlsm"), ("Todos os arquivos", "*.*")],
        )
        if not escolhido:
            return
        arquivo = Path(escolhido)
        etapas = [0]

        def tarefa(avisar):
            def progresso(texto):
                etapas[0] += 1
                avisar(texto, etapas[0] / ETAPAS)
            return c.processar(arquivo, self.pasta_programa / c.NOME_LOJAS_TXT,
                               self.pasta_programa / c.NOME_MODELO,
                               pasta_saida=self.pasta_saida(), progresso=progresso,
                               planilha_precos=self.planilha_precos())

        self._executar(self.status_inicio, arquivo.name, tarefa, self._sucesso_inicio)

    def _sucesso_inicio(self, dados):
        destino, r = dados
        qtd_1 = sum(it.tipo == "1" for it in r.pedidos)
        pares = [
            ("Marca", r.marca),
            ("Linhas no pedido", f"{len(r.pedidos)} ({qtd_1} com 1 · {len(r.pedidos) - qtd_1} com ME)"),
            ("Lojas encontradas", f"{len(r.encontradas)} de {len(r.lojas)}"),
            ("Duplicadas", str(len(r.duplicadas))),
            ("Faltando", ", ".join(l.codigo for l in r.faltando) or "0"),
            ("Não reconhecidas", str(len(r.nao_reconhecidas))),
        ]
        texto = f"{destino}\nPreços: {self._texto_precos(r.sem_preco)}"
        self.status_inicio.sucesso("Planilha gerada!", texto, pares, [
            ("Abrir planilha", lambda: self._abrir_arquivo(destino, self.status_inicio), True),
            ("Abrir pasta", lambda: abrir_na_pasta(destino), False),
        ])

    # --- tela Gerar em lote ---------------------------------------------------

    def _tela_lote(self) -> tk.Frame:
        tela = tk.Frame(self.conteudo, bg=COR["fundo"])
        self.lbl_sub_lote = cabecalho_tela(tela, "Gerar em lote", "")

        bloco = cartao(tela)
        bloco.pack(fill="x")
        interno = tk.Frame(bloco, bg=COR["cartao"])
        interno.pack(fill="x", padx=px(24), pady=px(18))

        topo = tk.Frame(interno, bg=COR["cartao"])
        topo.pack(fill="x")
        self.btn_limpar = Botao(topo, "Limpar", self._limpar_lote, cor="secundario", cor_hover="secundario_hover",
                                cor_texto=COR["destaque"], padx=14, pady=7)
        self.btn_limpar.pack(side="right")
        self.btn_remover = Botao(topo, "Remover selecionada", self._remover_lote, cor="secundario",
                                 cor_hover="secundario_hover", cor_texto=COR["destaque"], padx=14, pady=7)
        self.btn_remover.pack(side="right", padx=(0, px(8)))
        self.btn_adicionar = Botao(topo, "Adicionar planilhas", self._adicionar_lote, padx=14, pady=7)
        self.btn_adicionar.pack(side="right", padx=(0, px(8)))
        self.lbl_qtd_lote = rotulo(topo, "", 12, negrito=True)
        self.lbl_qtd_lote.pack(side="left")

        lista = tk.Frame(interno, bg=COR["cartao"])
        lista.pack(fill="x", pady=(px(12), 0))
        self.lista_lote = tk.Listbox(
            lista, height=3, font=(FONTE, 10), bg=COR["fundo"], fg=COR["texto"], relief="flat",
            highlightthickness=1, highlightbackground=COR["borda"], highlightcolor=COR["destaque"],
            selectbackground=COR["destaque"], selectforeground="#FFFFFF", activestyle="none",
            selectmode="extended", borderwidth=0,
        )
        rolagem = tk.Scrollbar(lista, orient="vertical", command=self.lista_lote.yview)
        self.lista_lote.config(yscrollcommand=rolagem.set)
        rolagem.pack(side="right", fill="y")
        self.lista_lote.pack(side="left", fill="x", expand=True)

        rodape = tk.Frame(interno, bg=COR["cartao"])
        rodape.pack(fill="x", pady=(px(14), 0))
        self.btn_gerar_lote = Botao(rodape, "Gerar em lote", self.gerar_lote, tamanho=11, padx=22, pady=10)
        self.btn_gerar_lote.pack(side="right", padx=(px(16), 0))
        self.lbl_destino_lote = rotulo(rodape, "", 9, "suave", justify="left", anchor="w", wraplength=px(420))
        self.lbl_destino_lote.pack(side="left", fill="x", expand=True)

        self.status_lote = PainelStatus(tela)
        self.status_lote.pack(fill="both", expand=True, pady=(px(16), 0))
        self._atualizar_lista_lote()
        self._atualizar_textos_lote()
        return tela

    def _atualizar_textos_lote(self):
        n = self.tamanho_grupo()
        self.lbl_sub_lote.config(
            text=f"Anexe várias planilhas Pedido_MARCA_....xlsx. Os pedidos são juntados e divididos em "
                 f"arquivos de {n} loja{'s' if n > 1 else ''}, em ordem numérica: "
                 f"{c.nome_saida_lote(1)}, {c.nome_saida_lote(2)}... (altere em Configurações)")

    def _atualizar_lista_lote(self):
        self.lista_lote.delete(0, "end")
        for arquivo in self.lote_arquivos:
            self.lista_lote.insert("end", f"  {arquivo.name}")
        n = len(self.lote_arquivos)
        self.lbl_qtd_lote.config(text=f"Planilhas anexadas ({n})")
        self.btn_gerar_lote.habilitar(n > 0 and not self.processando)
        if not self.processando:
            if n:
                self.status_lote.ocioso(f"{n} planilha{'s' if n > 1 else ''} pronta{'s' if n > 1 else ''}",
                                        "Clique em \"Gerar em lote\" para criar os arquivos.")
            else:
                self.status_lote.ocioso("Nenhuma planilha anexada",
                                        "Clique em \"Adicionar planilhas\" e escolha um ou mais arquivos.")

    def _adicionar_lote(self):
        if self.processando:
            return
        escolhidos = filedialog.askopenfilenames(
            title="Selecione as planilhas do pedido",
            filetypes=[("Planilhas Excel", "*.xlsx *.xlsm"), ("Todos os arquivos", "*.*")],
        )
        ja = {a.resolve() for a in self.lote_arquivos}
        for nome in escolhidos:
            arquivo = Path(nome)
            if arquivo.resolve() not in ja:  # a mesma planilha não entra duas vezes
                self.lote_arquivos.append(arquivo)
                ja.add(arquivo.resolve())
        self._atualizar_lista_lote()

    def _remover_lote(self):
        if self.processando:
            return
        for i in sorted(self.lista_lote.curselection(), reverse=True):
            del self.lote_arquivos[i]
        self._atualizar_lista_lote()

    def _limpar_lote(self):
        if self.processando:
            return
        self.lote_arquivos.clear()
        self._atualizar_lista_lote()

    def gerar_lote(self):
        if self.processando or not self.lote_arquivos:
            return
        arquivos = list(self.lote_arquivos)

        def tarefa(avisar):
            return c.processar_lote(arquivos, self.pasta_programa / c.NOME_LOJAS_TXT,
                                    self.pasta_programa / c.NOME_MODELO,
                                    pasta_saida=self.pasta_saida(), progresso=avisar,
                                    tamanho_grupo=self.tamanho_grupo(),
                                    planilha_precos=self.planilha_precos())

        self._executar(self.status_lote, f"{len(arquivos)} planilhas", tarefa, self._sucesso_lote)

    def _sucesso_lote(self, r: c.ResultadoLote):
        pares = []
        for n, arq in enumerate(r.arquivos, start=1):
            faixa = f"{arq.lojas[0].codigo} a {arq.lojas[-1].codigo}" if len(arq.lojas) > 1 else arq.lojas[0].codigo
            pares.append((f"({n})", f"{faixa} · {len(arq.itens)}"))
        total = sum(len(a.itens) for a in r.arquivos)
        plural = "s" if len(r.arquivos) > 1 else ""
        texto = (f"{len(r.planilhas)} planilhas lidas · {total} linhas · {len(r.arquivos)} arquivo{plural} "
                 f"(nº do arquivo, lojas · linhas)\nPreços: {self._texto_precos(r.sem_preco)}")
        self.status_lote.sucesso("Planilhas geradas!", texto, pares, [
            ("Abrir pasta", lambda: abrir_na_pasta(r.arquivos[0].destino), True),
        ], largura_valor=200, colunas=3, compacto=True)

    # --- geração em segundo plano --------------------------------------------

    def _executar(self, painel: PainelStatus, texto: str, tarefa, ao_concluir):
        """Roda `tarefa(avisar)` numa thread, animando `painel`; no fim chama `ao_concluir(resultado)`."""
        self.processando = True
        self._habilitar_botoes(False)
        painel.gerando(texto)
        inicio = time.perf_counter()

        def trabalhar():
            try:
                resultado = tarefa(lambda t, f: self.fila.put(("etapa", (t, f))))
                self.fila.put(("ok", resultado))
            except c.ErroConferencia as e:
                self.fila.put(("erro", str(e)))
            except Exception as e:  # erro inesperado: mostra em vez de fechar em silêncio
                self.fila.put(("erro", f"Erro inesperado: {type(e).__name__}: {e}"))

        def ler_fila():
            try:
                while True:
                    tipo, dados = self.fila.get_nowait()
                    if tipo == "etapa":
                        painel.etapa(*dados)
                    else:
                        restante = TEMPO_MINIMO_ANIMACAO - (time.perf_counter() - inicio)
                        self.root.after(max(int(restante * 1000), 0), finalizar, tipo, dados)
                        return
            except queue.Empty:
                pass
            self.root.after(50, ler_fila)

        def finalizar(tipo, dados):
            self.processando = False
            self._habilitar_botoes(True)
            if tipo == "ok":
                painel.concluir_barra()
                self.root.after(250, lambda: ao_concluir(dados))
            else:
                painel.erro(dados)

        threading.Thread(target=trabalhar, daemon=True).start()
        self.root.after(50, ler_fila)

    def _habilitar_botoes(self, ativo: bool):
        for botao in (self.btn_anexar, self.btn_adicionar, self.btn_remover, self.btn_limpar):
            botao.habilitar(ativo)
        self.btn_gerar_lote.habilitar(ativo and bool(self.lote_arquivos))

    def _texto_precos(self, sem_preco: list[str]) -> str:
        if not self.planilha_precos():
            return "planilha de preços não anexada"
        if not sem_preco:
            return "todos os produtos com preço"
        exemplos = ", ".join(sem_preco[:3]) + ("..." if len(sem_preco) > 3 else "")
        return f"{len(sem_preco)} produto{'s' if len(sem_preco) > 1 else ''} sem preço ({exemplos})"

    def _abrir_arquivo(self, destino: Path, painel: PainelStatus):
        try:
            os.startfile(destino)
        except OSError as e:
            painel.erro(f"Não foi possível abrir o arquivo:\n{e}")

    # --- tela Configurações ---------------------------------------------------

    def pasta_saida(self) -> Path | None:
        valor = self.config.get("pasta_saida")
        return Path(valor) if valor else None

    def tamanho_grupo(self) -> int:
        try:
            valor = int(self.config.get("lojas_por_arquivo", c.TAMANHO_GRUPO))
        except (TypeError, ValueError):
            valor = c.TAMANHO_GRUPO
        return min(max(valor, MIN_LOJAS_POR_ARQUIVO), MAX_LOJAS_POR_ARQUIVO)

    def planilha_precos(self) -> Path | None:
        """Cópia da planilha de preços anexada (fica em %APPDATA%), ou None se não houver."""
        caminho = arquivo_precos()
        return caminho if self.config.get("precos_nome") and caminho.is_file() else None

    def _salvar_config(self) -> bool:
        try:
            salvar_config(self.config)
            return True
        except OSError as e:
            self._aviso_config(f"Não foi possível salvar a configuração: {e}")
            return False

    def _aviso_config(self, texto: str):
        """Mensagem em vermelho no cartão da pasta; some quando não há aviso."""
        self.lbl_aviso_config.config(text=texto)
        if texto:
            self.lbl_aviso_config.pack(anchor="w", pady=(px(8), 0))
        else:
            self.lbl_aviso_config.pack_forget()

    def _tela_config(self) -> tk.Frame:
        tela = tk.Frame(self.conteudo, bg=COR["fundo"])
        cabecalho_tela(tela, "Configurações", "As escolhas ficam salvas para as próximas vezes.")

        # Pasta de destino
        bloco = cartao(tela)
        bloco.pack(fill="x")
        interno = tk.Frame(bloco, bg=COR["cartao"])
        interno.pack(fill="x", padx=px(24), pady=px(14))
        rotulo(interno, "Pasta de destino", 12, negrito=True).pack(anchor="w")
        rotulo(interno, "Onde as planilhas geradas (Início e Gerar em lote) serão salvas.", 9,
               "suave").pack(anchor="w", pady=(2, px(10)))
        caixa = tk.Frame(interno, bg=COR["fundo"], highlightthickness=1, highlightbackground=COR["borda"])
        caixa.pack(fill="x")
        self.lbl_pasta = rotulo(caixa, "", 10, fundo="fundo", anchor="w", padx=px(12), pady=px(7),
                                wraplength=px(560), justify="left")
        self.lbl_pasta.pack(fill="x")
        botoes = tk.Frame(interno, bg=COR["cartao"])
        botoes.pack(anchor="w", pady=(px(12), 0))
        Botao(botoes, "Escolher pasta...", self._escolher_pasta, padx=16, pady=7).pack(side="left")
        Botao(botoes, "Usar a pasta da planilha anexada", self._pasta_padrao, cor="secundario",
              cor_hover="secundario_hover", cor_texto=COR["destaque"], padx=16, pady=7).pack(
            side="left", padx=(px(10), 0))
        self.lbl_aviso_config = rotulo(interno, "", 9, "erro", justify="left", wraplength=px(560))

        # Lojas por arquivo (Gerar em lote)
        bloco = cartao(tela)
        bloco.pack(fill="x", pady=(px(12), 0))
        interno = tk.Frame(bloco, bg=COR["cartao"])
        interno.pack(fill="x", padx=px(24), pady=px(14))
        seletor = tk.Frame(interno, bg=COR["cartao"])
        seletor.pack(side="right")
        Botao(seletor, "−", lambda: self._mudar_tamanho_grupo(-1), cor="secundario", cor_hover="secundario_hover",
              cor_texto=COR["destaque"], tamanho=12, padx=12, pady=2).pack(side="left")
        self.lbl_tamanho_grupo = rotulo(seletor, "", 14, negrito=True, width=3)
        self.lbl_tamanho_grupo.pack(side="left", padx=px(6))
        Botao(seletor, "+", lambda: self._mudar_tamanho_grupo(+1), cor="secundario", cor_hover="secundario_hover",
              cor_texto=COR["destaque"], tamanho=12, padx=12, pady=2).pack(side="left")
        textos = tk.Frame(interno, bg=COR["cartao"])
        textos.pack(side="left", fill="x", expand=True)
        rotulo(textos, "Lojas por arquivo", 12, negrito=True).pack(anchor="w")
        rotulo(textos, "Quantas lojas ficam juntas em cada arquivo do Gerar em lote.", 9,
               "suave").pack(anchor="w", pady=(2, 0))

        # Arquivos usados na geração
        bloco = cartao(tela)
        bloco.pack(fill="x", pady=(px(12), 0))
        interno = tk.Frame(bloco, bg=COR["cartao"])
        interno.pack(fill="x", padx=px(24), pady=px(14))
        botoes = tk.Frame(interno, bg=COR["cartao"])
        botoes.pack(side="right", anchor="n")
        Botao(botoes, "Anexar planilha de preços", self._anexar_precos, padx=16, pady=7).pack(anchor="e")
        self.btn_remover_precos = Botao(botoes, "Remover", self._remover_precos, cor="secundario",
                                        cor_hover="secundario_hover", cor_texto=COR["destaque"], padx=16, pady=5)
        self.btn_remover_precos.pack(anchor="e", pady=(px(8), 0))
        textos = tk.Frame(interno, bg=COR["cartao"])
        textos.pack(side="left", fill="x", expand=True)
        rotulo(textos, "Arquivos usados na geração", 12, negrito=True).pack(anchor="w")
        rotulo(textos, "lojas.txt e modelo: pasta do programa · preços: anexe aqui", 9, "suave",
               wraplength=px(400), justify="left").pack(anchor="w", pady=(2, px(6)))
        self.lbl_apoio = {}
        for nome in (c.NOME_LOJAS_TXT, c.NOME_MODELO, "precos"):
            self.lbl_apoio[nome] = rotulo(textos, "", 10, anchor="w", justify="left", wraplength=px(400))
            self.lbl_apoio[nome].pack(anchor="w", pady=1)
        return tela

    def _atualizar_config(self):
        pasta = self.pasta_saida()
        self.lbl_pasta.config(text=str(pasta) if pasta else "Mesma pasta da planilha anexada "
                                                            "(no lote, a da primeira planilha da lista)")
        aviso = ""
        if pasta and not pasta.is_dir():
            aviso = "Esta pasta não existe mais. Escolha outra ou use a pasta da planilha."
        self._aviso_config(aviso)
        self.lbl_tamanho_grupo.config(text=str(self.tamanho_grupo()))

        for nome in (c.NOME_LOJAS_TXT, c.NOME_MODELO):
            existe = (self.pasta_programa / nome).is_file()
            self.lbl_apoio[nome].config(
                text=f"{'✓' if existe else '✗'}  {nome}" + ("" if existe else "  (não encontrado)"),
                fg=COR["ok"] if existe else COR["erro"])
        if self.planilha_precos():
            texto = (f"✓  Preços: {self.config['precos_nome']} · {self.config.get('precos_qtd', '?')} produtos"
                     f" · anexada em {self.config.get('precos_data', '?')}")
            self.lbl_apoio["precos"].config(text=texto, fg=COR["ok"])
        else:
            self.lbl_apoio["precos"].config(text="✗  Planilha de preços não anexada (PRC.VEN fica em branco)",
                                            fg=COR["erro"])
        self.btn_remover_precos.habilitar(self.planilha_precos() is not None)

    def _definir_pasta(self, pasta: str | None):
        self.config["pasta_saida"] = pasta
        if self._salvar_config():
            self._atualizar_config()
            self._atualizar_destino()

    def _escolher_pasta(self):
        atual = self.pasta_saida()
        pasta = filedialog.askdirectory(title="Escolha a pasta de destino",
                                        initialdir=str(atual) if atual and atual.is_dir() else None)
        if pasta:
            self._definir_pasta(str(Path(pasta)))

    def _pasta_padrao(self):
        self._definir_pasta(None)

    def _mudar_tamanho_grupo(self, delta: int):
        novo = min(max(self.tamanho_grupo() + delta, MIN_LOJAS_POR_ARQUIVO), MAX_LOJAS_POR_ARQUIVO)
        self.config["lojas_por_arquivo"] = novo
        if self._salvar_config():
            self._atualizar_config()
            self._atualizar_textos_lote()

    def _anexar_precos(self):
        if self.processando:
            return
        escolhido = filedialog.askopenfilename(
            title="Selecione a planilha de preços dos produtos",
            filetypes=[("Planilhas Excel", "*.xlsx *.xlsm"), ("Todos os arquivos", "*.*")],
        )
        if not escolhido:
            return
        origem = Path(escolhido)
        self.root.config(cursor="watch")
        self.root.update_idletasks()
        try:
            precos = c.ler_precos(origem)  # valida antes de guardar
            destino = arquivo_precos()
            destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(origem, destino)
        except c.ErroConferencia as e:
            self._aviso_config(f"Planilha de preços não anexada: {e}")
            return
        except OSError as e:
            self._aviso_config(f"Não foi possível copiar a planilha de preços: {e}")
            return
        finally:
            self.root.config(cursor="")
        self.config.update(precos_nome=origem.name, precos_qtd=len(precos),
                           precos_data=time.strftime("%d/%m/%Y %H:%M"))
        if self._salvar_config():
            self._atualizar_config()

    def _remover_precos(self):
        for chave in ("precos_nome", "precos_qtd", "precos_data"):
            self.config.pop(chave, None)
        try:
            arquivo_precos().unlink(missing_ok=True)  # só a cópia interna; a planilha original fica
        except OSError:
            pass
        if self._salvar_config():
            self._atualizar_config()


def caminho_recurso(nome: str) -> Path:
    """Arquivo embutido no .exe (PyInstaller extrai em sys._MEIPASS) ou ao lado do script."""
    base = getattr(sys, "_MEIPASS", None)
    return Path(base) / nome if base else Path(__file__).resolve().parent / nome


def iniciar() -> None:
    try:  # textos nítidos em telas com escala (125%, 150%...)
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
        # Ícone próprio na barra de tarefas também quando roda pelo Python.
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ConferenciaLojas")
    except Exception:
        pass
    root = tk.Tk()
    icone = caminho_recurso("icone.ico")
    if icone.is_file():
        root.iconbitmap(default=str(icone))
    App(root)
    root.mainloop()


if __name__ == "__main__":
    iniciar()
