/* Envio de planilhas e área de arrastar e soltar (sem dependências). */
"use strict";

var MSG_ERRO_INESPERADO = "Erro inesperado ao gerar; tente novamente ou avise o administrador.";

/* O cookie é o valor mais novo (a sessão pode ter mudado em outra aba); o campo oculto é o reserva. */
function csrfToken() {
  var m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  if (m) return decodeURIComponent(m[1]);
  var campo = document.querySelector("input[name=csrfmiddlewaretoken]");
  return campo ? campo.value : "";
}

function el(tag, classe, texto) {
  var e = document.createElement(tag);
  if (classe) e.className = classe;
  if (texto !== undefined) e.textContent = texto;
  return e;
}

function painelMostrar(painel, classe, titulo, texto) {
  painel.className = "cartao painel " + classe;
  painel.replaceChildren(el("div", "painel-titulo", titulo));
  if (texto) painel.appendChild(el("div", "painel-texto", texto));
}

/* Baixa um Blob com o nome dado. */
function baixar(blob, nome) {
  var url = URL.createObjectURL(blob);
  var a = document.createElement("a");
  a.href = url;
  a.download = nome;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(function () { URL.revokeObjectURL(url); }, 10000);
}

function nomeDoCabecalho(xhr, padrao) {
  var m = /filename="([^"]+)"/.exec(xhr.getResponseHeader("Content-Disposition") || "");
  return m ? m[1] : padrao;
}

function mostrarErro(painel, mensagem, config, entrar) {
  painelMostrar(painel, "erro-painel", "Não foi possível gerar", mensagem);
  if (config || entrar) {
    var a = el("a", "", entrar ? "Entrar novamente" : "Ir para Configurações");
    a.href = entrar ? "/entrar" : "/configuracoes";
    painel.appendChild(a);
  }
}

/* Só um envio por vez; enquanto pendente, zonas e campos de arquivo ficam desabilitados. */
var envioPendente = false;

function bloquearEnvio(bloquear) {
  envioPendente = bloquear;
  document.querySelectorAll("input[type=file]").forEach(function (i) { i.disabled = bloquear; });
  document.querySelectorAll(".zona").forEach(function (z) { z.classList.toggle("ocupada", bloquear); });
}

/* POST de formData em url. Em 2xx baixa o arquivo e chama
   aoConcluir({blob, nome, resumo}); em erro mostra o painel vermelho. */
function enviar(url, formData, aoConcluir, painel) {
  if (envioPendente) return null;
  painel = painel || document.getElementById("painel");
  bloquearEnvio(true);
  painelMostrar(painel, "gerando", "Gerando...", "Aguarde, isso leva alguns segundos.");
  var xhr = new XMLHttpRequest();
  xhr.open("POST", url);
  xhr.responseType = "blob";
  xhr.setRequestHeader("X-CSRFToken", csrfToken());
  xhr.onload = function () {
    bloquearEnvio(false);
    var cabecalho = xhr.getResponseHeader("X-Resumo");
    if (xhr.status >= 200 && xhr.status < 300 && cabecalho) {
      var resumo;
      try { resumo = JSON.parse(cabecalho); } catch (e) {
        mostrarErro(painel, MSG_ERRO_INESPERADO, false, false);
        return;
      }
      var resultado = {blob: xhr.response, nome: nomeDoCabecalho(xhr, "planilhas.zip"), resumo: resumo};
      baixar(resultado.blob, resultado.nome);
      aoConcluir(resultado);
      return;
    }
    xhr.response.text().then(function (corpo) {
      var dados = {};
      try { dados = JSON.parse(corpo); } catch (e) { /* corpo não é JSON */ }
      var msg = dados.erro || (xhr.status === 403 ? "Sua sessão mudou. Recarregue a página." : MSG_ERRO_INESPERADO);
      mostrarErro(painel, msg, dados.config, xhr.status === 401);
    });
  };
  xhr.onerror = function () {
    bloquearEnvio(false);
    mostrarErro(painel, "Não foi possível conectar ao servidor. Verifique a conexão e tente novamente.", false);
  };
  xhr.send(formData);
  return xhr;
}

function textoPrecos(r) {
  if (!r.tem_precos) return "planilha de preços não anexada";
  var n = r.sem_preco_qtd;
  if (!n) return "todos os produtos com preço";
  var exemplos = r.sem_preco.slice(0, 3).join(", ") + (n > 3 ? "..." : "");
  return n + " produto" + (n > 1 ? "s" : "") + " sem preço (" + exemplos + ")";
}

/* Painel verde da tela Início, com os mesmos rótulos do app de mesa. */
function mostrarResumoUm(painel, resultado, aoBaixar) {
  var r = resultado.resumo;
  painelMostrar(painel, "sucesso", "Planilha gerada!", resultado.nome);
  var pares = [
    ["Marca", r.marca],
    ["Linhas no pedido", r.linhas + " (" + r.com_1 + " com 1 · " + r.com_me + " com ME)"],
    ["Lojas encontradas", r.encontradas + " de " + r.total_lojas],
    ["Duplicadas", String(r.duplicadas)],
    ["Faltando", r.faltando_qtd ? r.faltando.join(", ") + (r.faltando_qtd > r.faltando.length
      ? " e mais " + (r.faltando_qtd - r.faltando.length) : "") : "0"],
    ["Não reconhecidas", String(r.nao_reconhecidas)],
    ["Preços", textoPrecos(r)]
  ];
  var dl = el("dl", "resumo");
  pares.forEach(function (p) {
    dl.appendChild(el("dt", "", p[0]));
    dl.appendChild(el("dd", "", p[1]));
  });
  painel.appendChild(dl);
  var botao = el("button", "botao", "Baixar novamente");
  botao.type = "button";
  botao.addEventListener("click", aoBaixar);
  painel.appendChild(botao);
}

/* Painel verde da tela Gerar em lote. */
function mostrarResumoLote(painel, resultado, aoBaixar) {
  var r = resultado.resumo;
  var n = r.arquivos.length;
  painelMostrar(painel, "sucesso", "Planilhas geradas!",
    r.planilhas + " planilhas lidas · " + r.linhas + " linhas · " + n + " arquivo" + (n > 1 ? "s" : "") +
    " (nº do arquivo, lojas · linhas)\nPreços: " + textoPrecos(r));
  var dl = el("dl", "resumo");
  r.arquivos.forEach(function (a, i) {
    dl.appendChild(el("dt", "", "(" + (i + 1) + ")"));
    dl.appendChild(el("dd", "", a.lojas + " · " + a.linhas));
  });
  painel.appendChild(dl);
  var botao = el("button", "botao", "Baixar novamente");
  botao.type = "button";
  botao.addEventListener("click", aoBaixar);
  painel.appendChild(botao);
}

/* Área de arrastar e soltar + botão. aoEscolher recebe a lista de arquivos;
   multiplos=true permite vários (usado pelo lote). */
function zonaArrastar(zona, input, aoEscolher, multiplos) {
  input.multiple = !!multiplos;
  input.addEventListener("change", function () {
    if (input.files.length) aoEscolher(Array.prototype.slice.call(input.files));
    input.value = "";
  });
  ["dragenter", "dragover"].forEach(function (nome) {
    zona.addEventListener(nome, function (e) { e.preventDefault(); zona.classList.add("sobre"); });
  });
  ["dragleave", "drop"].forEach(function (nome) {
    zona.addEventListener(nome, function (e) { e.preventDefault(); zona.classList.remove("sobre"); });
  });
  zona.addEventListener("drop", function (e) {
    if (envioPendente) return;
    var arquivos = Array.prototype.slice.call(e.dataTransfer.files);
    if (arquivos.length) aoEscolher(multiplos ? arquivos : arquivos.slice(0, 1));
  });
}
