# Conferência de Lojas na web: plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** publicar no Render um site Django, com login, que gera as mesmas planilhas de pedido do `.exe` 1.2 usando lista de lojas, modelo e preços compartilhados.

**Architecture:** `conferencia.py` ganha funções que trabalham com bytes (as de disco continuam e passam a chamá-las). Um projeto Django em `web/` guarda a configuração compartilhada no PostgreSQL, chama essas funções em `pedidos/servicos.py` e devolve `.xlsx`/`.zip` para download. Páginas HTML geradas no servidor com JavaScript simples (`fetch`).

**Tech Stack:** Python 3.13, Django 5.2 (LTS), openpyxl ≥ 3.1, gunicorn, psycopg[binary] 3, whitenoise, dj-database-url, PostgreSQL (Render), SQLite nos testes.

**Spec:** `docs/superpowers/specs/2026-11-09-conferencia-web-design.md`

## Global Constraints

- Regras de geração idênticas às do `.exe` 1.2; nenhum teste atual de `test_conferencia.py` pode mudar de resultado.
- `interface.py`, `build.bat` e `instalador.iss` continuam funcionando (o `.exe` usa as funções de disco).
- Todo texto visível ao usuário em português (pt-BR); código segue o estilo de `conferencia.py` (nomes em português, docstrings curtas).
- Todas as páginas exigem login; `/admin` só para superusuário.
- Uploads: só `.xlsx` (extensão sem diferenciar maiúsculas); até 10 MB por arquivo; até 30 planilhas por lote; conteúdo descompactado do `.xlsx` até 100 MB.
- Sessão expira após 12 horas sem uso (`SESSION_COOKIE_AGE = 43200`, `SESSION_SAVE_EVERY_REQUEST = True`).
- Bloqueio de 15 minutos após 5 senhas erradas seguidas para o mesmo nome de usuário.
- Planilhas de pedido e arquivos gerados nunca são gravados no servidor.
- `SECRET_KEY`, `DATABASE_URL`, `DEBUG`, `ALLOWED_HOSTS` vêm de variáveis de ambiente; com `DEBUG=False`: `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_HSTS_SECONDS = 31536000`, `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")`.
- Lojas por arquivo: padrão 7, mínimo 1. Histórico: mostrar as últimas 20 alterações.
- Mensagem de erro inesperado, exata: `Erro inesperado ao gerar; tente novamente ou avise o administrador.`
- Comandos de teste: `python -m unittest test_conferencia -v` (raiz) e `python web/manage.py test pedidos -v 2` (raiz).

## Review Focus

- Marca com acento no nome (`Pedido_Lancôme_....xlsx`): o resumo vai no cabeçalho `X-Resumo`, que só aceita latin-1; deve chegar intacto ao navegador → JSON com `ensure_ascii=True` (teste na Task 4).
- `lojas.txt` importado com BOM UTF-8, em latin-1 ou com quebras `\r\n`: deve ser lido como no `.exe` (teste na Task 6).
- Extensão em maiúsculas (`Pedido_NARS_x.XLSX`) e arquivo `.xlsx` que na verdade não é zip: o primeiro é aceito, o segundo recusado com a mensagem de planilha corrompida, nunca erro 500 (testes na Task 4).
- Lote enviado sem nenhum arquivo ou com o mesmo arquivo duas vezes: sem arquivos → `Nenhuma planilha anexada.`; repetido → processado duas vezes, como no `.exe` (testes na Task 5).
- Configuração sem modelo ou sem lojas válidas (ex.: todas as linhas apagadas): Início/Lote mostram o aviso com link para Configurações em vez de erro (teste na Task 4); salvar lista vazia é recusado (teste na Task 6).

---

### Task 0: Registrar as mudanças da versão 1.2 no `main`

As mudanças da coluna A, versão 1.2 e o modelo atualizado pelo usuário estão sem commit no diretório de trabalho (branch `web`).

**Files:**
- Modify (já alterados): `conferencia.py`, `test_conferencia.py`, `README.md`, `interface.py`, `instalador.iss`, `PLANILHA DE PEDIDOS.xlsx`
- Create: `instalador/Instalar_ConferenciaLojas_1.2.exe` (gerado de novo)

- [ ] **Step 1:** `python -m unittest test_conferencia -v` → 20 testes OK.
- [ ] **Step 2:** Gerar o instalador de novo com o modelo atualizado: PyInstaller e ISCC como em `build.bat` (sem o `pause`), copiando `lojas.txt` e `PLANILHA DE PEDIDOS.xlsx` para `dist/`. Conferir que `dist/PLANILHA DE PEDIDOS.xlsx` tem 12890 bytes.
- [ ] **Step 3:** Commit no `main` e trazer para o `web`:

```bash
git checkout main
git add conferencia.py test_conferencia.py README.md interface.py instalador.iss "PLANILHA DE PEDIDOS.xlsx" instalador/Instalar_ConferenciaLojas_1.2.exe
git commit -m "Coluna A com a inicial da marca e versão 1.2"
git checkout web && git rebase main
```

---

### Task 1: Funções em memória no `conferencia.py`

**Files:**
- Modify: `conferencia.py`
- Test: `test_conferencia.py`

**Interfaces:**
- Produces (todas em `conferencia.py`):
  - `ler_planilha(origem: Path | bytes) -> dict[str, list[tuple]]`
  - `ler_lojas_texto(texto: str) -> dict[tuple[int, int], Loja]` (mesmos erros de formato que `ler_lojas`)
  - `decodificar_texto(dados: bytes) -> str` (utf-8-sig, fallback latin-1; `ler_lojas` passa a usá-la)
  - `ler_precos_bytes(dados: bytes) -> dict[str, float]`
  - `extrair_marca(planilha: Path | str) -> str` (`str` = nome do arquivo)
  - `validar_modelo(modelo: bytes) -> None` (levanta `ErroConferencia` se não for `.xlsx` válido ou não tiver a aba `PEDIDO`)
  - `gerar_planilha_pedidos_bytes(itens, lojas, modelo: bytes, precos: dict[str, float] | None = None) -> bytes`
  - `processar_bytes(nome: str, dados: bytes, lojas, modelo: bytes, precos=None) -> tuple[bytes, Resultado]` (`Resultado.sem_preco` preenchido)
  - `processar_lote_bytes(planilhas: list[tuple[str, bytes]], lojas, modelo: bytes, precos=None, tamanho_grupo: int = TAMANHO_GRUPO) -> ResultadoLote`
  - `ArquivoLote` passa a ser `ArquivoLote(nome: str, lojas: list[Loja], itens: list[ItemPedido], dados: bytes = b"", destino: Path | None = None)`; `ResultadoLote.planilhas` passa a `list[tuple[str, Resultado]]` (nome do arquivo).
  - `processar`, `processar_lote`, `gerar_planilha_pedidos`, `ler_lojas`, `ler_precos` mantêm assinatura e comportamento e passam a delegar às novas.

- [ ] **Step 1: Testes que falham** (em `TesteConferencia`):

```python
def test_processar_bytes_igual_ao_de_disco(self):
    destino, r_disco = c.processar(self.pedido, self.lojas, self.modelo)
    dados, r_mem = c.processar_bytes(self.pedido.name, self.pedido.read_bytes(),
                                     c.ler_lojas(self.lojas), self.modelo.read_bytes())
    self.assertEqual(dados, destino.read_bytes())
    self.assertEqual(r_mem.pedidos, r_disco.pedidos)
    self.assertEqual(r_mem.marca, "Drunk Elephant")

def test_bytes_com_modelo_real_mantem_listas_suspensas(self):
    dados, _ = c.processar_bytes(self.pedido.name, self.pedido.read_bytes(),
                                 c.ler_lojas(self.lojas), MODELO_REAL.read_bytes())
    with zipfile.ZipFile(io.BytesIO(dados)) as z:
        self.assertIn("x14:dataValidation", z.read("xl/worksheets/sheet1.xml").decode())

def test_lote_bytes(self):
    r = c.processar_lote_bytes([(self.pedido.name, self.pedido.read_bytes())],
                               c.ler_lojas(self.lojas), self.modelo.read_bytes(), tamanho_grupo=1)
    self.assertEqual([a.nome for a in r.arquivos],
                     ["PLANILHA DE PEDIDOS - (1).xlsx", "PLANILHA DE PEDIDOS - (2).xlsx"])
    self.assertTrue(all(a.dados.startswith(b"PK") and a.destino is None for a in r.arquivos))
    self.assertEqual(r.planilhas[0][0], self.pedido.name)

def test_ler_lojas_texto_e_decodificar(self):
    texto = c.decodificar_texto("﻿20-256 LOJA\r\n20-073 São Paulo\r\n".encode("utf-8"))
    self.assertEqual([l.codigo for l in c.ler_lojas_texto(texto).values()], ["20-256", "20-073"])
    self.assertEqual(c.decodificar_texto("20-073 São".encode("latin-1")), "20-073 São")
    with self.assertRaises(c.ErroConferencia):
        c.ler_lojas_texto("sem lojas aqui")

def test_validar_modelo(self):
    c.validar_modelo(MODELO_REAL.read_bytes())
    with self.assertRaises(c.ErroConferencia):
        c.validar_modelo(b"nao e zip")
    sem_pedido = self.pasta / "x.xlsx"
    criar_pedido(sem_pedido)  # aba "Sheet", sem PEDIDO
    with self.assertRaises(c.ErroConferencia):
        c.validar_modelo(sem_pedido.read_bytes())

def test_planilha_bytes_corrompida(self):
    with self.assertRaises(c.ErroConferencia):
        c.processar_bytes("Pedido_NARS_x.xlsx", b"nao e zip", c.ler_lojas(self.lojas), self.modelo.read_bytes())
```

Adicionar `import io` no topo. Testes existentes de lote que usam `a.destino.name` continuam válidos (versão de disco preenche `destino`).

- [ ] **Step 2:** `python -m unittest test_conferencia -v` → os 6 novos falham (`AttributeError`), os 20 antigos passam.
- [ ] **Step 3: Implementar.** `ler_planilha` usa `io.BytesIO` quando recebe `bytes`. `gerar_planilha_pedidos_bytes` contém o miolo atual de `gerar_planilha_pedidos` (ler zip de `BytesIO`, editar XML, escrever zip em `BytesIO`); a versão de disco lê o modelo (mantendo as mensagens atuais de modelo ausente/aberto/corrompido) e grava o resultado (mantendo a mensagem de arquivo aberto no Excel). `processar_lote_bytes` contém a lógica atual de `processar_lote` (ordem, grupos, progresso não é necessário); `processar_lote` chama `processar_lote_bytes` com os bytes lidos (envolvendo erros de leitura com `Problema na planilha {nome}:`), grava cada `ArquivoLote.dados` em `pasta / nome` e preenche `destino`. `interface.py` usa `len(r.planilhas)`, `arq.destino`, `arq.lojas`, `arq.itens` — conferir que continua funcionando.
- [ ] **Step 4:** `python -m unittest test_conferencia -v` → 26 testes OK.
- [ ] **Step 5:** Commit: `git add conferencia.py test_conferencia.py && git commit -m "conferencia: funções em memória para a versão web"`

---

### Task 2: Projeto Django, login e bloqueio

**Files:**
- Create: `requirements-web.txt`, `web/manage.py`, `web/site_conferencia/{__init__,settings,urls,wsgi}.py`, `web/pedidos/{__init__,apps,models,views,urls,admin}.py`, `web/pedidos/templates/pedidos/{base,entrar}.html`, `web/pedidos/static/pedidos/estilo.css`, `web/pedidos/tests/__init__.py`, `web/pedidos/tests/test_acesso.py`
- Modify: `.gitignore` (adicionar `web/staticfiles/`, `*.sqlite3`)

**Interfaces:**
- Produces:
  - `settings.py` coloca a raiz do repositório em `sys.path` (`BASE_DIR = Path(__file__).resolve().parent.parent`; `RAIZ = BASE_DIR.parent`), para `import conferencia` funcionar; `LOGIN_URL = "entrar"`, `LANGUAGE_CODE = "pt-br"`, `TIME_ZONE = "America/Sao_Paulo"`; banco por `dj_database_url.config(default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}")`; `DATA_UPLOAD_MAX_MEMORY_SIZE` e `FILE_UPLOAD_MAX_MEMORY_SIZE` = 10 MB; `DATA_UPLOAD_MAX_NUMBER_FILES = 30`; whitenoise; constantes do Global Constraints.
  - Modelo `TentativaLogin(usuario: CharField(150, unique), falhas: int = 0, bloqueado_ate: DateTimeField | None)`.
  - View `entrar` (URL `/entrar`, name `"entrar"`), view `sair` (POST `/sair`, name `"sair"`).
  - Template `base.html` com menu lateral (links `inicio`, `lote`, `configuracoes` — URLs criadas nas Tasks 4-6; até lá, os links podem apontar para `#`), nome do usuário e botão Sair; bloco `conteudo`.
  - Mixin/decorator: todas as views do app usam `login_required`.

- [ ] **Step 1: Testes que falham** (`test_acesso.py`, `django.test.TestCase`):
  - `test_sem_login_redireciona_para_entrar`: `GET /` → 302 para `/entrar?next=/`.
  - `test_entrar_com_senha_certa`: usuário criado com `User.objects.create_user("maria", password="senha-forte-123")`; POST `/entrar` → 302 para `/`; sessão autenticada.
  - `test_senha_errada_mostra_mensagem`: POST com senha errada → 200 e contém `Usuário ou senha incorretos.`
  - `test_bloqueio_apos_5_erros`: 5 POSTs errados; o 6º com a senha **certa** → 200 contendo `Muitas tentativas. Tente novamente em 15 minutos.`; com `bloqueado_ate` no passado, a senha certa entra e `falhas` volta a 0.
  - `test_usuario_comum_nao_entra_no_admin`: logado como usuário comum, `GET /admin/` → 302 para o login do admin.
  - `test_sair`: POST `/sair` → 302 para `/entrar`, sessão encerrada.
- [ ] **Step 2:** `python web/manage.py test pedidos -v 2` → falham.
- [ ] **Step 3: Implementar** o projeto, `requirements-web.txt` (`Django>=5.2,<5.3`, `openpyxl>=3.1`, `gunicorn`, `psycopg[binary]>=3.2`, `whitenoise>=6.7`, `dj-database-url>=2.2`), a view `entrar` (usa `authenticate`; consulta/atualiza `TentativaLogin` antes e depois) e a migração `0001`. Rota provisória `/` (name `"inicio"`) com página vazia "Em construção" dentro de `base.html`, substituída na Task 4. Visual: cores do `COR` de `interface.py` (menu lateral escuro, cartões brancos, botão de destaque).
- [ ] **Step 4:** `pip install -r requirements-web.txt`, `python web/manage.py test pedidos -v 2` → OK; `python -m unittest test_conferencia` → OK.
- [ ] **Step 5:** Commit: `git add requirements-web.txt web .gitignore && git commit -m "web: projeto Django com login e bloqueio por tentativas"`

---

### Task 3: Configuração compartilhada, histórico e carga inicial

**Files:**
- Modify: `web/pedidos/models.py`, `web/pedidos/admin.py`
- Create: `web/pedidos/migrations/0002_configuracao_alteracao.py`, `web/pedidos/migrations/0003_carga_inicial.py`, `web/pedidos/servicos.py`, `web/pedidos/tests/test_servicos.py`

**Interfaces:**
- Consumes: Task 1 (`ler_lojas_texto`, `ler_precos_bytes`, `validar_modelo`).
- Produces:
  - `Configuracao` (campos exatamente como na seção 4 da spec: `lojas_texto: TextField`, `modelo: BinaryField`, `modelo_nome`, `precos: BinaryField(null=True)`, `precos_nome`, `precos_qtd: int = 0`, `lojas_por_arquivo: PositiveIntegerField = 7`, `atualizado_em`, `atualizado_por: FK User null`). `Configuracao.atual() -> Configuracao` (`get_or_create(pk=1)`).
  - `Alteracao(quando: auto_now_add, usuario: FK User null, descricao: CharField(300))`, ordenação `-quando`.
  - Em `servicos.py`:
    - `ConfigIncompleta(Exception)`
    - `carregar() -> tuple[dict, bytes, dict | None, int]` = (lojas, modelo, preços ou None, lojas por arquivo); levanta `ConfigIncompleta` se não houver modelo ou lojas válidas.
    - `salvar_lojas(texto: str, usuario) -> int` (valida com `ler_lojas_texto`, devolve quantidade; registra `Alteracao("alterou a lista de lojas (N lojas)")`)
    - `salvar_modelo(nome: str, dados: bytes, usuario) -> None` (`validar_modelo`; `"trocou o modelo para {nome}"`)
    - `salvar_precos(nome: str, dados: bytes, usuario) -> int` (`ler_precos_bytes`; `"trocou a planilha de preços para {nome} ({qtd} produtos)"`)
    - `remover_precos(usuario) -> None` (`"removeu a planilha de preços"`)
    - `salvar_lojas_por_arquivo(valor: int, usuario) -> None` (mínimo 1, senão `ErroConferencia("O número de lojas por arquivo precisa ser pelo menos 1.")`; `"mudou lojas por arquivo para {valor}"`)
  - Cada `salvar_*`/`remover_precos` atualiza `atualizado_em`/`atualizado_por` e grava a `Alteracao` na mesma transação; em erro de validação nada é gravado.
- `admin.py`: registrar `Alteracao` só leitura (sem add/change/delete). `Configuracao` não aparece no admin (é editada pela tela).

- [ ] **Step 1: Testes que falham** (`test_servicos.py`):
  - `test_carga_inicial`: após as migrações, `Configuracao.atual().lojas_texto == (RAIZ / "lojas.txt").read_text(encoding="utf-8-sig")` e `bytes(modelo) == (RAIZ / "PLANILHA DE PEDIDOS.xlsx").read_bytes()`; `precos is None`; `lojas_por_arquivo == 7`.
  - `test_carregar_config_incompleta`: com `modelo=b""` → `ConfigIncompleta`.
  - `test_salvar_lojas_grava_historico`: `salvar_lojas("20-256 X\n20-073", u) == 2`; última `Alteracao.descricao == "alterou a lista de lojas (2 lojas)"` e `usuario == u`.
  - `test_salvar_lojas_invalida_nao_grava`: `salvar_lojas("nada", u)` levanta `ErroConferencia`; `lojas_texto` e contagem de `Alteracao` inalterados.
  - `test_salvar_modelo_sem_aba_pedido_recusado`.
  - `test_salvar_e_remover_precos`: planilha com colunas `CODIGO`/`VALOR UNITARIO` (2 produtos) → retorna 2, `precos_qtd == 2`; `remover_precos` → `precos is None`, `precos_nome == ""`.
  - `test_lojas_por_arquivo_minimo_1`.
- [ ] **Step 2:** `python web/manage.py test pedidos` → falham.
- [ ] **Step 3: Implementar** modelos, migração de esquema e migração de dados `0003` (lê `settings.RAIZ / "lojas.txt"` com `decodificar_texto` e `settings.RAIZ / "PLANILHA DE PEDIDOS.xlsx"`; só cria se `pk=1` não existir).
- [ ] **Step 4:** testes OK.
- [ ] **Step 5:** Commit: `git commit -m "web: configuração compartilhada, histórico e carga inicial"`

---

### Task 4: Tela Início (uma planilha)

**Files:**
- Create: `web/pedidos/forms.py`, `web/pedidos/templates/pedidos/inicio.html`, `web/pedidos/static/pedidos/app.js`, `web/pedidos/tests/test_inicio.py`
- Modify: `web/pedidos/views.py`, `web/pedidos/urls.py`, `web/pedidos/servicos.py`

**Interfaces:**
- Consumes: Task 1 `processar_bytes`; Task 3 `carregar`, `ConfigIncompleta`.
- Produces:
  - `forms.checar_xlsx(arquivo: UploadedFile) -> bytes`: extensão `.xlsx` (case-insensitive) senão `ErroConferencia("Envie um arquivo .xlsx.")`; tamanho > 10 MB → `ErroConferencia("O arquivo {nome} passa de 10 MB.")`; zip inválido → mensagem de planilha corrompida de `conferencia.ler_planilha`; soma de `file_size` dos membros > 100 MB → `ErroConferencia("O arquivo {nome} é grande demais depois de descompactado.")`. Devolve os bytes.
  - `servicos.gerar_um(nome: str, dados: bytes) -> tuple[bytes, dict]`; o dict (resumo) tem as chaves: `marca`, `linhas`, `com_1`, `com_me`, `encontradas`, `total_lojas`, `duplicadas`, `faltando` (lista de códigos), `nao_reconhecidas`, `sem_preco` (lista), `tem_precos` (bool).
  - `servicos.resposta_erro(erro: Exception) -> JsonResponse`: `ErroConferencia` → 400 `{"erro": str(e)}`; `ConfigIncompleta` → 409 `{"erro": "Configuração incompleta: cadastre a lista de lojas e o modelo em Configurações.", "config": true}`; outros → loga com `logger.exception` e 500 com a mensagem exata do Global Constraints.
  - Rotas: `GET /` (name `"inicio"`) página; `POST /gerar` (name `"gerar"`) campo `planilha` → `.xlsx` com `Content-Disposition: attachment; filename="PLANILHA DE PEDIDOS - novo.xlsx"` e cabeçalho `X-Resumo` = `json.dumps(resumo, ensure_ascii=True)`.
  - `app.js`: função `enviar(url, formData, aoConcluir)` (envia `X-CSRFToken`, mostra "Gerando...", em 2xx cria o download via `Blob` + `URL.createObjectURL`, guarda o blob para "Baixar novamente", lê `X-Resumo`; em erro mostra `erro` no painel vermelho e, se `config`, link para Configurações). Área de arrastar e soltar reaproveitável pela Task 5.
- A página `inicio` com config incompleta mostra o aviso com link para Configurações, sem o formulário.

- [ ] **Step 1: Testes que falham** (`test_inicio.py`, logado; planilhas criadas com os helpers de `test_conferencia.py` — importar `criar_pedido` de lá, já que a raiz está no `sys.path`):
  - `test_gerar_baixa_xlsx_e_resumo`: POST `/gerar` com `Pedido_Drunk Elephant_ teste.xlsx` e `lojas_texto` igual a `LOJAS_TXT` → 200, `Content-Disposition` com o nome certo, corpo começa com `PK`; `json.loads(r["X-Resumo"])` tem `marca == "Drunk Elephant"`, `linhas == 5`, `com_1 == 3`, `com_me == 2`; abrindo o `.xlsx`, `PEDIDO!A2 == "TRANSFERENCIA TESTER 18 D"`.
  - `test_resumo_com_acento`: arquivo `Pedido_Lancôme_x.xlsx` → `X-Resumo` é ASCII puro e `json.loads(...)["marca"] == "Lancôme"`.
  - `test_extensao_maiuscula_aceita`: `Pedido_NARS_x.XLSX` → 200.
  - `test_nome_fora_do_padrao`: `planilha.xlsx` → 400 e `erro` contém `Não foi possível identificar a marca`.
  - `test_nao_xlsx_recusado`: `pedido.csv` → 400 `Envie um arquivo .xlsx.`
  - `test_xlsx_falso_recusado`: `Pedido_NARS_x.xlsx` com conteúdo `b"abc"` → 400 contendo `corrompido`.
  - `test_grande_demais`: arquivo de 10 MB + 1 byte → 400 contendo `passa de 10 MB`.
  - `test_config_incompleta`: `Configuracao` com `modelo=b""` → `GET /` mostra link para `configuracoes`; POST `/gerar` → 409.
  - `test_erro_inesperado`: `mock.patch("pedidos.servicos.c.processar_bytes", side_effect=RuntimeError)` → 500 com a mensagem exata.
  - `test_nada_gravado_em_disco`: `MEDIA_ROOT` inexistente/vazio após gerar (não há `FileField`; garantir que nenhum arquivo foi criado em `settings.BASE_DIR`).
- [ ] **Step 2:** falham.
- [ ] **Step 3: Implementar.** Página com o mesmo conteúdo da tela Início do `interface.py` (título "Gerar planilha de pedidos", texto "Anexe a planilha Pedido_MARCA_....xlsx para gerar a PLANILHA DE PEDIDOS - novo.xlsx.") e o painel de resumo com os mesmos rótulos de `_sucesso_inicio` (Marca, Linhas no pedido, Lojas encontradas, Duplicadas, Faltando, Não reconhecidas) mais "Preços" com o texto de `_texto_precos` (ler em `interface.py:656`).
- [ ] **Step 4:** testes OK; abrir `python web/manage.py runserver`, entrar e gerar uma planilha real pelo navegador.
- [ ] **Step 5:** Commit: `git commit -m "web: tela Início gera a planilha de pedidos"`

---

### Task 5: Tela Gerar em lote

**Files:**
- Create: `web/pedidos/templates/pedidos/lote.html`, `web/pedidos/tests/test_lote.py`
- Modify: `views.py`, `urls.py`, `servicos.py`, `static/pedidos/app.js`

**Interfaces:**
- Consumes: Task 1 `processar_lote_bytes`; Task 4 `checar_xlsx`, `resposta_erro`, `enviar`.
- Produces:
  - `servicos.gerar_lote(planilhas: list[tuple[str, bytes]]) -> tuple[bytes, dict]` → zip (`zipfile.ZIP_DEFLATED`, em memória) com `PLANILHA DE PEDIDOS - (n).xlsx`; resumo com `planilhas` (quantidade), `linhas` (total), `arquivos` = lista de `{"nome", "lojas": "20-050 a 20-059", "linhas"}` (faixa com uma loja só = só o código, como em `_sucesso_lote`), `sem_preco`, `tem_precos`.
  - `GET /lote` (name `"lote"`), `POST /gerar-lote` (name `"gerar_lote"`) campo `planilhas` (múltiplo) → `application/zip`, `filename="PLANILHAS DE PEDIDOS.zip"`, `X-Resumo` como na Task 4. Sem arquivos → 400 `Nenhuma planilha anexada.`; mais de 30 → 400 `Envie no máximo 30 planilhas por vez.`
  - A lista de arquivos (adicionar, remover um, limpar) é mantida no JavaScript antes do envio.

- [ ] **Step 1: Testes que falham** (`test_lote.py`):
  - `test_lote_gera_zip`: duas planilhas (`Pedido_NARS_a.xlsx`, `Pedido_Shiseido_b.xlsx`, criadas como em `test_lote_divide_em_grupos_de_7`) com 9 lojas e `lojas_por_arquivo = 7` → zip com `PLANILHA DE PEDIDOS - (1).xlsx` e `(2)`; resumo `arquivos[1]["lojas"] == "20-070 a 20-1000"`.
  - `test_lote_usa_lojas_por_arquivo_da_config`: `lojas_por_arquivo = 1` → um arquivo por loja.
  - `test_lote_vazio`: 400 `Nenhuma planilha anexada.`
  - `test_lote_mais_de_30`: 31 arquivos → 400 (mensagem acima ou o 400 do Django por `DATA_UPLOAD_MAX_NUMBER_FILES`, convertido na view para a mesma mensagem).
  - `test_mesmo_arquivo_duas_vezes`: mesma planilha 2× → 200 e o total de linhas é o dobro de uma.
  - `test_erro_diz_qual_planilha`: uma planilha fora do padrão → 400 contendo o nome dela.
- [ ] **Step 2:** falham.
- [ ] **Step 3: Implementar.** Textos da tela iguais aos da tela de lote do `interface.py` (`_tela_lote`, `_atualizar_textos_lote`), trocando "pasta" por download.
- [ ] **Step 4:** testes OK; teste manual no navegador com 2+ planilhas.
- [ ] **Step 5:** Commit: `git commit -m "web: tela Gerar em lote baixa .zip"`

---

### Task 6: Tela Configurações

**Files:**
- Create: `web/pedidos/templates/pedidos/configuracoes.html`, `web/pedidos/tests/test_configuracoes.py`
- Modify: `views.py`, `urls.py`, `forms.py`

**Interfaces:**
- Consumes: Task 3 `salvar_*`, `remover_precos`, `Alteracao`; Task 1 `decodificar_texto`; Task 4 `checar_xlsx`.
- Produces: `GET /configuracoes` (name `"configuracoes"`) e um POST por ação, todos redirecionando de volta com mensagem (`django.contrib.messages`) de sucesso ou com o texto do `ErroConferencia`:
  - `POST /configuracoes/lojas` campo `lojas_texto` (textarea) **ou** arquivo `lojas_arquivo` (`.txt`, lido com `decodificar_texto`); se vier arquivo, ele vale.
  - `POST /configuracoes/modelo` arquivo `modelo`.
  - `POST /configuracoes/precos` arquivo `precos`; `POST /configuracoes/precos/remover`.
  - `POST /configuracoes/lojas-por-arquivo` campo `valor` (inteiro).
- A página mostra: textarea com `lojas_texto` e a quantidade de lojas válidas; nome do modelo; preços (nome, `precos_qtd` produtos, data) ou "Nenhuma planilha de preços: a coluna D (PRC.VEN) fica vazia."; lojas por arquivo com − / +; últimas 20 `Alteracao` ("09/11 16:40 · maria · descrição").

- [ ] **Step 1: Testes que falham**:
  - `test_salvar_lojas_pelo_texto` e `test_importar_lojas_txt_latin1_com_bom_e_crlf` (arquivo `"﻿20-256 São\r\n20-073\r\n"` em UTF-8 e outro em latin-1 → 2 lojas, texto salvo legível).
  - `test_lista_vazia_recusada`: textarea vazia → mensagem `Nenhuma loja válida` e lista anterior mantida.
  - `test_trocar_modelo` / `test_modelo_sem_pedido_recusado` (mensagem contém `não tem a aba PEDIDO`).
  - `test_trocar_e_remover_precos`.
  - `test_lojas_por_arquivo_zero_recusado`.
  - `test_historico_mostra_ultimas_20`: 25 alterações → página lista 20, a mais recente primeiro, com o nome do usuário.
  - `test_get_nao_altera_nada`: GET em URL de ação → 405.
- [ ] **Step 2:** falham.
- [ ] **Step 3: Implementar.**
- [ ] **Step 4:** testes OK; teste manual: trocar preços e gerar no Início, conferindo a coluna D.
- [ ] **Step 5:** Commit: `git commit -m "web: tela Configurações com histórico"`

---

### Task 7: Publicação no Render e documentação

**Files:**
- Create: `render.yaml`, `web/build.sh`
- Modify: `README.md` (nova seção "Versão web"), `web/site_conferencia/settings.py` (se faltar algo do `check --deploy`)

**Interfaces:**
- `render.yaml`: serviço `web` (`runtime: python`, `buildCommand: ./web/build.sh`, `startCommand: cd web && python manage.py migrate --noinput && gunicorn site_conferencia.wsgi --bind 0.0.0.0:$PORT`), env `PYTHON_VERSION=3.13.2`, `SECRET_KEY` (`generateValue: true`), `DEBUG=False`, `ALLOWED_HOSTS` (`.onrender.com`), `DATABASE_URL` vindo do banco `conferencia-db` (plano pago básico; o gratuito do Render expira).
- `build.sh`: `pip install -r requirements-web.txt && python web/manage.py collectstatic --noinput`.

- [ ] **Step 1:** `DEBUG=False SECRET_KEY=<50+ caracteres aleatórios> ALLOWED_HOSTS=localhost python web/manage.py check --deploy` → sem avisos (ou só avisos justificados no README).
- [ ] **Step 2:** Todos os testes: `python -m unittest test_conferencia` e `python web/manage.py test pedidos` → OK.
- [ ] **Step 3:** README: o que é a versão web, rodar localmente (`pip install -r requirements-web.txt`, `python web/manage.py migrate`, `createsuperuser`, `runserver`), publicar no Render (Blueprint pelo `render.yaml`), criar o primeiro administrador no Shell do Render (`cd web && python manage.py createsuperuser`), cadastrar usuários em `/admin`, anexar a planilha de preços em Configurações.
- [ ] **Step 4:** Commit: `git commit -m "web: publicação no Render"` e `git push -u origin web` (pedir confirmação ao usuário antes do push).
- [ ] **Step 5:** Com o usuário: criar o Blueprint no Render apontando para o branch `web`, criar o superusuário, entrar, anexar preços e comparar uma planilha gerada pelo site com a gerada pelo `.exe` 1.2 (mesmo arquivo de pedido, mesma planilha de preços) — as abas `PEDIDO` devem ter os mesmos valores.
