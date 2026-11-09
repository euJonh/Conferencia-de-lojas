/* Envio de planilhas e área de arrastar e soltar (sem dependências). */
"use strict";

var MSG_ERRO_INESPERADO = "Erro inesperado ao gerar; tente novamente ou avise o administrador.";

function csrfToken() {
  var campo = document.querySelector("input[name=csrfmiddlewaretoken]");
  if (campo) return campo.value;
  var m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : "";
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

function mostrarErro(painel, mensagem, config) {
  painelMostrar(painel, "erro-painel", "Não foi possível gerar", mensagem);
  if (config) {
    var a = el("a", "", "Ir para Configurações");
    a.href = "/configuracoes";
    painel.appendChild(a);
  }
}

/* POST de formData em url. Em 2xx baixa o arquivo e chama
   aoConcluir({blob, nome, resumo}); em erro mostra o painel vermelho. */
function enviar(url, formData, aoConcluir, painel) {
  painel = painel || document.getElementById("painel");
  painelMostrar(painel, "gerando", "Gerando...", "Aguarde, isso leva alguns segundos.");
  var xhr = new XMLHttpRequest();
  xhr.open("POST", url);
  xhr.responseType = "blob";
  xhr.setRequestHeader("X-CSRFToken", csrfToken());
  xhr.onload = function () {
    if (xhr.status >= 200 && xhr.status < 300) {
      var resumo = {};
      try { resumo = JSON.parse(xhr.getResponseHeader("X-Resumo") || "{}"); } catch (e) { /* sem resumo */ }
      var resultado = {blob: xhr.response, nome: nomeDoCabecalho(xhr, "planilha.xlsx"), resumo: resumo};
      baixar(resultado.blob, resultado.nome);
      aoConcluir(resultado);
      return;
    }
    xhr.response.text().then(function (corpo) {
      var dados = {};
      try { dados = JSON.parse(corpo); } catch (e) { /* corpo não é JSON */ }
      mostrarErro(painel, dados.erro || MSG_ERRO_INESPERADO, dados.config);
    });
  };
  xhr.onerror = function () {
    mostrarErro(painel, "Não foi possível conectar ao servidor. Verifique a conexão e tente novamente.", false);
  };
  xhr.send(formData);
  return xhr;
}

function textoPrecos(r) {
  if (!r.tem_precos) return "planilha de preços não anexada";
  var n = r.sem_preco.length;
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
    ["Faltando", r.faltando.length ? r.faltando.join(", ") : "0"],
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
    var arquivos = Array.prototype.slice.call(e.dataTransfer.files);
    if (arquivos.length) aoEscolher(multiplos ? arquivos : arquivos.slice(0, 1));
  });
}
