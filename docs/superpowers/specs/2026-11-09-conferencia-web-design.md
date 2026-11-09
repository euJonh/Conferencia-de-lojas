# Conferência de Lojas na web: especificação

Data: 2026-11-09 · Status: aguardando revisão

## 1. Objetivo

Levar o Conferência de Lojas (hoje um `.exe` em Python/Tkinter) para um site na nuvem,
usado por várias pessoas que compartilham a mesma lista de lojas, o mesmo modelo
`PLANILHA DE PEDIDOS.xlsx` e a mesma planilha de preços.

**Critério de sucesso:** qualquer pessoa autorizada abre o site, envia as planilhas
`Pedido_MARCA_....xlsx` e baixa o mesmo resultado que o `.exe` 1.2 geraria; quem
atualiza a lista de lojas, o modelo ou os preços atualiza para todos.

### Decisões tomadas

| Tema | Decisão |
|---|---|
| Hospedagem | Render (Web Service + PostgreSQL), publicação automática a cada `git push` |
| Framework | Django, páginas HTML geradas no servidor + JavaScript simples |
| Login | Usuário e senha próprios do site |
| Gerência de usuários | Só o administrador, pelo `/admin` do Django |
| Alterar lojas, modelo, preços, lojas por arquivo | Qualquer pessoa logada, com histórico de quem alterou |
| Regras de geração | Exatamente as do `.exe` 1.2 (coluna A com a inicial da marca, N só com o código, sufixo a cada 99 MSG NOTA, lote em grupos, preço pela planilha de preços) |
| App desktop | Continua no repositório e funcionando durante a transição |

## 2. Arquitetura

```
conferencia.py          regras de negócio (já existe); passa a aceitar arquivos em memória
interface.py, build.bat, instalador.iss   app desktop, sem mudanças funcionais
web/
  manage.py
  site_conferencia/     settings, urls, wsgi
  pedidos/
    models.py           configuração compartilhada e histórico
    servicos.py         ponte entre Django e conferencia.py
    views.py            telas e downloads
    forms.py            validação de uploads e da lista de lojas
    templates/pedidos/  base, entrar, inicio, lote, configuracoes
    static/pedidos/     CSS e JavaScript
    migrations/         inclui a carga inicial de lojas.txt e do modelo
    tests/
requirements-web.txt    Django, gunicorn, psycopg, whitenoise, dj-database-url, openpyxl
render.yaml             Web Service + PostgreSQL
```

### Responsabilidades

| Unidade | Faz | Depende de |
|---|---|---|
| `conferencia.py` | Regras puras: recebe bytes + nomes de arquivo, devolve resultado e bytes do `.xlsx`. Não conhece web nem banco. | `openpyxl` |
| `pedidos/models.py` | Guarda a configuração compartilhada e o histórico no banco. | Django |
| `pedidos/servicos.py` | Lê a configuração do banco, chama `conferencia.py`, monta o `.xlsx` ou o `.zip` e o resumo. | `models.py`, `conferencia.py` |
| `pedidos/views.py` + templates | Telas, uploads e downloads; todas exigem login. | `servicos.py`, `forms.py` |
| `/admin` do Django | Criar, desativar e redefinir senha de usuários (só superusuário). | Django |

## 3. Mudanças em `conferencia.py`

Objetivo: as funções de leitura e geração passam a trabalhar com bytes, sem mudar
nenhuma regra. As funções atuais baseadas em `Path` continuam existindo (o `.exe`
usa) e passam a chamar as novas.

- `ler_planilha(origem)` aceita `Path` ou `bytes` (`openpyxl` lê `BytesIO`).
- Nova `ler_lojas_texto(texto: str)`; `ler_lojas(caminho)` lê o arquivo e chama ela.
- Nova `ler_precos_bytes(dados: bytes)`; `ler_precos(caminho)` checa o arquivo e chama ela.
- `extrair_marca` passa a aceitar o nome do arquivo (`str`), além de `Path`.
- Nova `gerar_planilha_pedidos_bytes(itens, lojas, modelo: bytes, precos) -> bytes`;
  `gerar_planilha_pedidos(..., modelo: Path, destino: Path, ...)` chama ela e grava.
- Novas `processar_bytes(nome, dados, lojas, modelo, precos)` e
  `processar_lote_bytes([(nome, dados), ...], lojas, modelo, precos, tamanho_grupo)`,
  que devolvem os resultados e os arquivos em memória (`[(nome do arquivo, bytes)]`).
  `processar` e `processar_lote` passam a usá-las e só gravam em disco.
- Mensagens específicas de desktop (arquivo aberto no Excel, pasta inexistente) ficam
  nas funções de disco; as funções em memória não as produzem.

## 4. Dados (banco)

**Usuários:** tabela padrão do Django (`auth.User`). Administrador = superusuário.

**`Configuracao`** (uma única linha):

| Campo | Tipo | Observação |
|---|---|---|
| `lojas_texto` | texto | Conteúdo no formato do `lojas.txt` |
| `modelo` | binário | `PLANILHA DE PEDIDOS.xlsx` |
| `modelo_nome` | texto | Nome original do arquivo |
| `precos` | binário, opcional | Planilha de preços; vazio = coluna D sem preço |
| `precos_nome` | texto | Nome original |
| `precos_qtd` | inteiro | Quantidade de produtos lidos |
| `lojas_por_arquivo` | inteiro | Padrão 7, mínimo 1 |
| `atualizado_em`, `atualizado_por` | data/hora, usuário | Última alteração |

Arquivos ficam no banco porque o disco do Render é apagado a cada publicação.

**`Alteracao`** (histórico): `quando`, `usuario`, `descricao` (ex.: "trocou a planilha
de preços para precos_nov.xlsx (1.234 produtos)").

**`TentativaLogin`** (bloqueio por senha errada): `usuario` (nome digitado), `falhas`,
`bloqueado_ate`. Zera ao entrar com sucesso.

**Carga inicial:** uma migração cria a `Configuracao` com o `lojas.txt` e o
`PLANILHA DE PEDIDOS.xlsx` do repositório. A planilha de preços é anexada pela tela.

**Planilhas de pedido e arquivos gerados nunca são gravados** no servidor.

## 5. Telas e fluxo

Layout com menu lateral (Início, Gerar em lote, Configurações) e o nome do usuário com
"Sair". Visual inspirado no app atual.

**Entrar (`/entrar`):** usuário e senha. Quem não está logado é redirecionado para cá.
Sem "esqueci a senha" por e-mail: o administrador redefine pelo `/admin`.

**Início (`/`):**
1. Área de arrastar/clicar para escolher um `.xlsx`.
2. O JavaScript envia por `fetch` (POST) e mostra "Gerando...".
3. Sucesso: a resposta é o `.xlsx` (`PLANILHA DE PEDIDOS - novo.xlsx`); o resumo vem
   no cabeçalho `X-Resumo` (JSON). O navegador baixa o arquivo automaticamente e mostra
   o resumo: marca; linhas (com 1 / com ME); lojas encontradas X de Y; duplicadas;
   faltando (códigos); não reconhecidas; códigos sem preço. Botão "Baixar novamente"
   usa o arquivo guardado na memória da página.
4. Erro: resposta JSON `{"erro": "..."}`, mostrada no painel vermelho.

**Gerar em lote (`/lote`):** escolher várias planilhas, ver a lista, remover uma, limpar.
Gerar baixa `PLANILHAS DE PEDIDOS.zip` com `PLANILHA DE PEDIDOS - (1).xlsx`, `(2)`...
Resumo: por arquivo, faixa de lojas e quantidade de linhas; total; códigos sem preço.

**Configurações (`/configuracoes`):**
- Lista de lojas: área de texto editável + "Importar lojas.txt"; valida antes de salvar
  e lista as linhas fora do formato; exige pelo menos uma loja válida.
- Modelo: nome atual + "Trocar modelo"; recusa arquivo sem a aba `PEDIDO`.
- Preços: nome, quantidade de produtos, data + "Trocar" e "Remover"; recusa planilha
  sem preços reconhecíveis (mesma mensagem do `ler_precos`).
- Lojas por arquivo: − / + (mínimo 1).
- Histórico: últimas 20 alterações.
- Cada alteração grava uma linha em `Alteracao`.

**Sem pasta de destino:** o download vai para a pasta padrão do navegador.

## 6. Erros

- `ErroConferencia` → mensagem do próprio erro no painel vermelho (HTTP 400).
- Configuração incompleta (sem lojas ou sem modelo) → aviso em Início e Lote com link
  para Configurações.
- Erro inesperado → "Erro inesperado ao gerar; tente novamente ou avise o
  administrador." (HTTP 500); detalhe técnico só no log.
- Alterações simultâneas: vale a última salva; ambas vão para o histórico. Cada geração
  usa a configuração lida no início do pedido.

## 7. Segurança

- Todas as páginas e downloads exigem login; `/admin` exige superusuário.
- Senhas com o hash padrão do Django e validadores de senha padrão.
- Sessão expira após 12 horas sem uso.
- Bloqueio de 15 minutos após 5 senhas erradas seguidas para o mesmo usuário
  (contagem guardada no banco).
- HTTPS obrigatório (`SECURE_SSL_REDIRECT`, cookies `Secure`, HSTS), CSRF em todos os POST
  (o `fetch` envia o token).
- Uploads: só `.xlsx`; até 10 MB por arquivo; até 30 planilhas por lote; o conteúdo
  descompactado do `.xlsx` não pode passar de 100 MB.
- `SECRET_KEY`, `DATABASE_URL` e `DEBUG=False` vêm de variáveis de ambiente do Render.

## 8. Publicação (Render)

- `render.yaml` com um Web Service Python (`gunicorn site_conferencia.wsgi`) e um
  PostgreSQL.
- Build: instalar `requirements-web.txt`, `collectstatic`; antes de iniciar, `migrate`.
- Arquivos estáticos servidos pelo `whitenoise`.
- Primeiro superusuário criado com `createsuperuser` no shell do Render (passo descrito
  no README).

## 9. Testes

- Os testes atuais de `test_conferencia.py` continuam passando.
- Novos testes de `conferencia.py`: as funções em memória geram bytes idênticos aos das
  funções de disco para a mesma entrada, incluindo as listas suspensas do modelo.
- Testes Django (`web/pedidos/tests/`), com SQLite:
  - página sem login redireciona para `/entrar`;
  - Início: gera o `.xlsx` certo e o `X-Resumo` correto; nome fora do padrão devolve o erro;
  - Lote: `.zip` com os arquivos e linhas certos;
  - uploads inválidos (não `.xlsx`, grande demais, lote com mais de 30) recusados;
  - Configurações: lista de lojas inválida recusada; modelo sem aba PEDIDO recusado;
    cada alteração grava no histórico;
  - usuário comum não acessa `/admin`;
  - bloqueio após 5 senhas erradas.

## 10. Fora do escopo desta versão

- Recuperação de senha por e-mail.
- Versões antigas da planilha de preços.
- Relatório de quem gerou o quê.
- Desativar o `.exe` (passo separado, depois de validar a versão web).
