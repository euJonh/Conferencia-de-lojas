# Conferência de Lojas

Aplicativo Windows que transforma as planilhas de pedido por loja (`Pedido_MARCA_....xlsx`)
na planilha de importação `PLANILHA DE PEDIDOS`, conferindo as lojas contra a lista
oficial (`lojas.txt`) e preenchendo preço, cliente, mensagem da nota e demais campos.

Para usar sem instalar nada além do programa, baixe e rode
[`instalador/Instalar_ConferenciaLojas_1.1.exe`](instalador/Instalar_ConferenciaLojas_1.1.exe).

## Tecnologias e dependências

| O quê | Para quê | Onde é usado |
|---|---|---|
| [Python](https://www.python.org/) 3.11+ (testado no 3.13) | Linguagem do projeto | todo o código |
| [openpyxl](https://openpyxl.readthedocs.io/) ≥ 3.1 | Ler as planilhas `.xlsx` (pedidos e preços) | `conferencia.py` |
| tkinter (vem com o Python) | Interface gráfica: menu lateral, telas, animações | `interface.py` |
| Biblioteca padrão: `zipfile`, `xml.etree`, `re`, `threading`, `json` | Escrever a planilha de saída editando o XML do modelo, rodar a geração em segundo plano, salvar configurações | `conferencia.py`, `interface.py` |
| [PyInstaller](https://pyinstaller.org/) ≥ 6.0 | Empacotar tudo num único `ConferenciaLojas.exe` | `build.bat` |
| [Inno Setup](https://jrsoftware.org/isinfo.php) 6 | Gerar o instalador `.exe` (assistente em português, atalhos, desinstalador) | `instalador.iss`, `build.bat` |
| [Pillow](https://python-pillow.org/) | Converter a imagem da pena no ícone `icone.ico` (só ao trocar o ícone) | `gerar_icone.py` |

As dependências Python estão em [`requirements.txt`](requirements.txt). O programa
empacotado (`.exe` ou instalador) não precisa de Python nem de nenhuma dessas
bibliotecas no PC de quem usa.

A planilha de saída é escrita direto no XML do `.xlsx` (e não pelo openpyxl) porque o
modelo tem listas suspensas que o openpyxl apagaria ao salvar. Assim a saída fica
idêntica ao modelo, só com a aba **PEDIDO** preenchida.

## Estrutura do projeto

| Arquivo | Conteúdo |
|---|---|
| `conferencia.py` | Regras de negócio: leitura do `lojas.txt`, das planilhas de pedido e de preços, conferência das lojas, geração da planilha (Início e lote). Ponto de entrada do `.exe`. |
| `interface.py` | Interface gráfica (telas Início, Gerar em lote e Configurações). |
| `test_conferencia.py` | Testes automatizados (`unittest`). |
| `lojas.txt` | Lista oficial de lojas, uma por linha. |
| `PLANILHA DE PEDIDOS.xlsx` | Modelo da planilha de saída. |
| `icone.ico`, `icone.png`, `pena_original.png`, `gerar_icone.py` | Ícone do programa e o script que o gera. |
| `build.bat` | Gera o `.exe` e o instalador. |
| `instalador.iss` | Script do Inno Setup. |
| `instalador/` | Instalador pronto para distribuir. |

## Como funciona

Lê uma planilha `.xlsx` com as lojas na linha 1 (cabeçalho) e, abaixo de cada loja, os
valores `0`, `1`, `ME` ou `X` por produto. Pega só os `1` e `ME` (o resto é ignorado) e
gera `PLANILHA DE PEDIDOS - novo.xlsx` na mesma pasta da planilha escolhida.

O arquivo gerado é uma cópia idêntica do modelo `PLANILHA DE PEDIDOS.xlsx` (abas,
formatação, filtros e listas suspensas), com a aba **PEDIDO** preenchida a partir da
linha 2, uma linha por loja × produto:

| Coluna | Campo | Valor |
|---|---|---|
| A | TIPO PEDIDO | `TRANSFERENCIA TESTER 18` se for `1`; `TRANSFERENCIA ME` se for `ME` |
| B | PRODUTO | `COD_PP` se for `1`; `COD_ME` se for `ME` |
| C | QTD.VEN | `1` ou `ME` |
| D | PRC.VEN | `VALOR UNITARIO` da planilha de preços para o código da coluna B, em R$ (vazio se não houver preço ou planilha) |
| G | CLIENTE | `FIL018` |
| N | PED.CLIENTE | código da loja (`NN-NNN`), com sufixo a cada 99 repetições da MSG NOTA (veja abaixo) |
| Q | MSG NOTA | `NN-NNN TESTER SEPHORA MARCA` se for `1`; `NN-NNN TRANSFORMAR TESTER SEPHORA MARCA` se for `ME` |
| X | DESCONTO | `NÃO` |

A marca vem do nome da planilha, que deve seguir o padrão `Pedido_NOME DA MARCA_....xlsx`
(ex.: `Pedido_NARS_2026-09-04..2026-10-03.xlsx` → `NARS`). Ela é usada exatamente como
está escrita no nome. Fora desse padrão, o programa avisa e não gera o arquivo.

**Limite de 99 por MSG NOTA:** dentro de cada arquivo gerado, as linhas com a mesma
MSG NOTA (código + `TESTER SEPHORA`/`TRANSFORMAR TESTER SEPHORA` + marca) são contadas.
Da 1ª à 99ª, o PED.CLIENTE fica só com o código (`20-050`). Da 100ª à 198ª, ganha `1`
(`20-0501`). Da 199ª à 297ª, ganha `2` (`20-0502`), e assim por diante. A MSG NOTA não
muda. Cada MSG NOTA tem a sua contagem: TESTER e TRANSFORMAR TESTER da mesma loja, ou
marcas diferentes, contam separado.

As outras colunas ficam em branco. Ordem: por código de loja, primeiro os `1`, depois os
`ME`. Se o arquivo de saída já existir, ele é substituído. A planilha escolhida e o
modelo não são alterados.

## Como usar

1. Deixe na mesma pasta do `ConferenciaLojas.exe`:
   - `lojas.txt`: uma loja por linha, só o código ou código e nome:
     ```
     20-256
     20-257 LOJA MOOCA (SP)
     ```
   - `PLANILHA DE PEDIDOS.xlsx`: o modelo, com a aba `PEDIDO`.
2. Abra o `ConferenciaLojas.exe`.
3. Na tela **Início**, clique em **Anexar planilha .xlsx** e escolha a planilha.
   Uma animação acompanha a geração.
4. Ao terminar, a tela mostra o resumo da conferência (lojas encontradas, duplicadas,
   faltando, não reconhecidas, totais de 1 e ME) e os botões **Abrir planilha** e
   **Abrir pasta**.

### Gerar em lote

Na tela **Gerar em lote** (menu lateral) dá para anexar várias planilhas de uma vez
(**Adicionar planilhas**, com seleção múltipla) e clicar em **Gerar em lote**.

- Os pedidos de todas as planilhas são juntados e divididos em arquivos de **N lojas**
  (padrão 7, ajustável em Configurações), em ordem numérica de código (ex.: com 7, o
  arquivo 1 tem 20-050, 20-053, 20-054, 20-056, 20-057, 20-058 e 20-059).
- Cada arquivo leva os pedidos dessas lojas vindos de **todas** as planilhas anexadas.
  Dentro do arquivo: por loja, depois na ordem em que as planilhas foram anexadas,
  primeiro os `1` e depois os `ME`. A MSG NOTA usa a marca da planilha de origem.
- Nomes: `PLANILHA DE PEDIDOS - (1).xlsx`, `PLANILHA DE PEDIDOS - (2).xlsx`...
  Arquivos com o mesmo nome são substituídos.
- Só entram lojas que têm pelo menos um `1` ou `ME`.
- Se uma planilha tiver problema (nome fora do padrão, arquivo corrompido), nada é
  gerado e a mensagem diz qual planilha é.

### Configurações

Na tela **Configurações** (menu lateral):

- **Pasta de destino**: onde as planilhas geradas (Início e Gerar em lote) serão
  salvas. Sem escolha, vão para a mesma pasta da planilha anexada (no lote, a da
  primeira planilha da lista).
- **Lojas por arquivo**: quantas lojas ficam juntas em cada arquivo do Gerar em lote
  (botões `−` e `+`, de 1 a 99; padrão 7).
- **Anexar planilha de preços**: a planilha com `CODIGO` (coluna A) e `VALOR UNITARIO`
  (coluna K). O programa guarda uma cópia; para atualizar os preços, anexe a planilha
  nova de novo. **Remover** apaga só essa cópia. Sem planilha de preços, o PRC.VEN fica
  em branco. Produtos sem preço aparecem no resultado da geração.

Tudo fica salvo em `%APPDATA%\ConferenciaLojas\` (`config.json` e `precos.xlsx`).

Regras:
- O código (`20-256`) é o identificador. Ele pode estar em qualquer posição do texto da
  célula (`20-256`, `Loja 20-256 Mooca`...).
- Ordenação numérica: `20-256` vem antes de `20-1000`.
- As colunas `COD_PP` e `COD_ME` da planilha são localizadas pelo nome do cabeçalho.
- Colunas com código no padrão `NN-NNN` que não está no `lojas.txt` não entram no
  pedido; elas só aparecem como **não reconhecidas** no resumo.

## Instalador

`instalador\Instalar_ConferenciaLojas_<versão>.exe` é o arquivo para distribuir. Quem
recebe só precisa rodá-lo (não precisa de Python nem de administrador). Ele:

- instala em `%LOCALAPPDATA%\Programs\ConferenciaLojas` o `ConferenciaLojas.exe`,
  o `lojas.txt`, a `PLANILHA DE PEDIDOS.xlsx` e este README;
- cria o atalho no menu Iniciar e, se marcado, na área de trabalho;
- registra o desinstalador em Configurações > Aplicativos.

Reinstalar uma versão nova substitui o `lojas.txt` e o modelo pelos que vêm no
instalador. As configurações e a planilha de preços anexada ficam em
`%APPDATA%\ConferenciaLojas` e são mantidas.

## Como gerar o .exe e o instalador

Requer Python 3.11+ e [Inno Setup 6](https://jrsoftware.org/isinfo.php) no Windows
(`winget install --id JRSoftware.InnoSetup -e`). Dê dois cliques em `build.bat` ou rode:

```bat
build.bat
```

Saídas: `dist\ConferenciaLojas.exe` (com `lojas.txt` e o modelo ao lado) e o instalador
em `instalador\`. A versão fica em `instalador.iss` (`AppVersao`).

O ícone (`icone.ico`) é gerado a partir da imagem da pena com:

```bat
python gerar_icone.py pena_original.png
```

## Rodar sem gerar o .exe

```bat
python -m pip install -r requirements.txt
python conferencia.py
```

## Testes

```bat
python -m unittest test_conferencia -v
```

## Licença

MIT. Veja [LICENSE](LICENSE).
