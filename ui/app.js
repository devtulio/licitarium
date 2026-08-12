// Interface do Licitarium: fala com o Python pela ponte pywebview
// (window.pywebview.api), montada em licitarium.py:Api.
"use strict";
const $ = id => document.getElementById(id);
const esc = s => String(s ?? "").replace(/[&<>"']/g,
  c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const brl = new Intl.NumberFormat("pt-BR", {style:"currency", currency:"BRL"});
const dinheiro = v => v == null ? "–" : brl.format(v);
// preço de unidade-base costuma ter centavos de centavo: R$ 0,0466 por folha
const brlFino = new Intl.NumberFormat("pt-BR",
  {style: "currency", currency: "BRL", minimumFractionDigits: 4,
   maximumFractionDigits: 4});
const dinheiroFino = v =>
  v == null ? "–" : (v >= 1 ? brl.format(v) : brlFino.format(v));
const dataBr = s => {
  if (!s) return "–";
  const d = String(s).slice(0, 10).split("-");
  return d.length === 3 ? `${d[2]}/${d[1]}/${d[0]}` : s;
};
const UFS = ["AC","AL","AP","AM","BA","CE","DF","ES","GO","MA","MT","MS","MG",
  "PA","PB","PR","PE","PI","RJ","RN","RS","RO","RR","SC","SP","SE","TO"];

const ESTANDARTE = `
  <line x1="32" y1="57" x2="32" y2="15" stroke="#b08d3e" stroke-width="2.6" stroke-linecap="round"/>
  <ellipse cx="32" cy="10.5" rx="2.3" ry="5" fill="#b08d3e"/>
  <polygon points="12,25.5 5,21 5,37 12,32.5" fill="#ded5c2" stroke="#2b2115" stroke-width="1.6"/>
  <polygon points="52,25.5 59,21 59,37 52,32.5" fill="#ded5c2" stroke="#2b2115" stroke-width="1.6"/>
  <rect x="11" y="19" width="42" height="20" fill="#ded5c2" stroke="#2b2115" stroke-width="1.6"/>
  <text x="32" y="27.5" font-family="Georgia, serif" font-size="5.4" fill="#2b2115"
        text-anchor="middle" textLength="36" lengthAdjust="spacingAndGlyphs">LICITARIVM</text>
  <text x="32" y="34.5" font-family="Georgia, serif" font-size="3.6" fill="#8b2e2e"
        text-anchor="middle" textLength="36" lengthAdjust="spacingAndGlyphs">SVB · HASTA · PVBLICA</text>
  <line x1="20" y1="57.5" x2="44" y2="57.5" stroke="#2b2115" stroke-width="1.6" stroke-linecap="round"/>
  <text x="32" y="62.5" font-family="Georgia, serif" font-size="4.6" letter-spacing="1"
        fill="#2b2115" text-anchor="middle">MMXXVI</text>`;

// selo oficial (design/icone-t1.svg): tabula ansata com L capitular
const SELO = `
  <polygon points="11,25 3,19 3,45 11,39" fill="#8b2e2e"/>
  <polygon points="53,25 61,19 61,45 53,39" fill="#8b2e2e"/>
  <rect x="9" y="17" width="46" height="30" fill="#8b2e2e"/>
  <rect x="12.5" y="20.5" width="39" height="23" fill="none" stroke="#f5efe2"
        stroke-width="1.4" opacity=".7"/>
  <text x="32" y="40.5" font-family="Georgia, 'Times New Roman', serif"
        font-size="21" fill="#f5efe2" text-anchor="middle">L</text>`;

const estado = { tipo:"contratacoes", pagina:1, municipio:null,
                 ord:null, dir:"desc", objetosAlvo:null };
// há município de referência? decide se a aba Preços mostra a origem
let temReferencia = false;
// comparar por conteúdo muda a grade e o resumo inteiros
let porConteudo = false;
// corrigir pelo IPCA: preço de 2022 não se compara com preço de 2026
let corrigirIpca = false;
// pedido do usuário (2026-08-08): a busca abre com tudo desmarcado — marcar
// é ato positivo, sem justificativa. precosIncluidos é a seleção (ids); um
// item que chega a ser marcado e depois é tirado vira precosDescartados,
// aí sim com motivo — item nunca marcado não passa por lá.
// id do item -> { motivo, descricao, valor }. Gravado no banco por termo:
// a pesquisa é peça de processo e precisa poder ser refeita amanhã.
let precosDescartados = new Map();
let precosIncluidos = new Set();
let api = null;

// ── splash ────────────────────────────────────────────────────────────────
// Composição por tema; o tema vem na URL (o Python já o lê do banco para
// abrir a janela), então a splash nasce na cor certa, sem piscar.
const SPLASH_POR_TEMA = {
  portal: () => `<div class="cx">${SELO_SVG(60)}
    <div><div class="mark">LICITARI<b>V</b>M</div>
      <div class="linha2" id="splash-muni">Contratações públicas</div>
      <div class="barra"><i id="splash-barra"></i></div></div></div>`,
  pergaminho: () => `<div class="cx diploma">${ESTANDARTE_SVG(86)}
    <div class="mark">LICITARI<b>V</b>M</div>
    <div class="linha2" id="splash-muni">Contratações públicas</div>
    <div class="barra" style="width:100%"><i id="splash-barra"></i></div></div>`,
  observatorio: () => `<div class="pilha">
    <div class="anel">${SELO_SVG(78)}<div class="giro"></div></div>
    <div class="mark">LICITARI<b>V</b>M</div>
    <div class="divisa">svb hasta pvblica</div>
    <div class="barra" style="width:150px"><i id="splash-barra"></i></div></div>`,
};
const SELO_SVG = t =>
  `<svg viewBox="0 0 64 64" aria-hidden="true" style="width:${t}px;height:${t}px;flex:none">${SELO}</svg>`;
const ESTANDARTE_SVG = t =>
  `<svg viewBox="0 0 64 64" aria-hidden="true" style="width:${t}px;height:${t}px">${ESTANDARTE}</svg>`;

const splashInicio = Date.now();

// o tema fica espelhado no localStorage só para a splash nascer na cor
// certa antes de qualquer consulta; o banco segue sendo a fonte da verdade
function temaSalvo() {
  // 1) tema.js escrito pelo Python (fonte da verdade, chega antes de tudo)
  // 2) parâmetro de URL, só em teste/depuração
  // 3) localStorage, última reserva
  if (window.__TEMA) return window.__TEMA;
  const daUrl = new URLSearchParams(location.search).get("tema");
  if (daUrl) return daUrl;
  try { return localStorage.getItem("tema") || "portal"; }
  catch { return "portal"; }
}

function montarSplash() {
  const tema = temaSalvo();
  document.documentElement.dataset.theme = tema;
  $("splash").innerHTML = (SPLASH_POR_TEMA[tema] || SPLASH_POR_TEMA.portal)();
}

// a barra acompanha as etapas reais do carregamento, não um tempo inventado
function progressoSplash(fracao, texto) {
  const barra = $("splash-barra");
  if (barra) barra.style.width = `${Math.round(fracao * 100)}%`;
  if (texto && $("splash-muni")) $("splash-muni").textContent = texto;
}

function esconderSplash() {
  const splash = $("splash");
  if (!splash) return;
  progressoSplash(1);
  // piso de tempo: sem isso a splash pisca quando o acervo abre rápido
  const espera = Math.max(0, 900 - (Date.now() - splashInicio));
  setTimeout(() => {
    splash.classList.add("saindo");
    setTimeout(() => splash.remove(), 400);
  }, espera);
}
montarSplash();

// Ponte com rede de proteção. O pywebview REJEITA a promise quando o
// Python levanta, e no exe sem console o traceback não vai a lugar nenhum:
// sem isto, uma chamada que falhava deixava os números VELHOS na tela —
// marcar "corrigir pelo IPCA", a chamada falhar, e o resumo seguir
// mostrando os valores não corrigidos com a caixa marcada (auditoria de
// falha silenciosa, 2026-08-09). Um ponto só, em vez de try/catch em ~50
// call sites. Relança: quem já trata (carregarPainel) segue tratando, e
// quem não trata pelo menos aborta em vez de seguir com dado velho.
function comRede(bruta) {
  return new Proxy(bruta, {
    get(alvo, nome) {
      const metodo = alvo[nome];
      // guardas do tipo `if (api.set_config)` precisam continuar valendo
      if (typeof metodo !== "function") return metodo;
      return async (...args) => {
        try {
          return await metodo.apply(alvo, args);
        } catch (e) {
          const aviso = $("sync-msg");
          if (aviso) aviso.textContent =
            `Falha em ${String(nome)}: ${(e && e.message) || e}`;
          throw e;
        }
      };
    },
  });
}

// ── boot ──────────────────────────────────────────────────────────────────
window.addEventListener("pywebviewready", async () => {
  api = comRede(window.pywebview.api);
  document.querySelectorAll("#svg-estandarte-wiz, #svg-estandarte-sobre")
    .forEach(s => s.innerHTML = ESTANDARTE);
  $("svg-selo").innerHTML = SELO;
  progressoSplash(0.35);
  const e = await api.get_estado();
  const temaBanco = e.tema || "portal";
  // só remonta se o tema.js não chegou (fallback): com ele, a splash já
  // nasceu certa e remontar produziria a troca de composição no meio
  if (!window.__TEMA && temaBanco !== temaSalvo() && $("splash")) {
    try { localStorage.setItem("tema", temaBanco); } catch {}
    montarSplash();
  }
  aplicarTema(temaBanco, false);
  aplicarLargura(e.largura || "compacta", false);
  aplicarFonte(e.fonte || "normal", false);
  aplicarDensidade(e.densidade || "confortavel", false);
  try { larguras = JSON.parse(e.colunas || "{}"); } catch { larguras = {}; }
  $("cfg-maximizar").checked = (e.maximizar ?? "1") === "1";
  $("sobre-versao").textContent = e.versao;
  $("rodape-versao").textContent = `PNCP · dados públicos · v${e.versao}`;
  if (!e.ibge) { iniciarWizard(); return; }
  iniciarApp(e);
});

// Aba selecionada: a classe pinta, o aria-selected conta. Sem o segundo, o
// leitor de tela anuncia N abas e nenhuma marcada — achado da auditoria de
// acessibilidade (2026-08-09). Um ponto só para as abas de topo e as
// subabas do Painel, que erravam do mesmo jeito.
function marcarAba(botoes, selecionado) {
  botoes.forEach(b => {
    const ativo = selecionado(b);
    b.classList.toggle("on", ativo);
    b.setAttribute("aria-selected", String(ativo));
  });
}

function aplicarTema(tema, salvar = true) {
  document.documentElement.dataset.theme = tema;
  try { localStorage.setItem("tema", tema); } catch { /* sem storage: ok */ }
  document.querySelectorAll(".tcard").forEach(c =>
    c.classList.toggle("on", c.dataset.tema === tema));
  if (salvar && api) api.set_config("tema", tema);
}
document.querySelectorAll(".tcard").forEach(c =>
  c.addEventListener("click", () => aplicarTema(c.dataset.tema)));

function aplicarLargura(v, salvar = true) {
  document.documentElement.dataset.largura = v;
  $("cfg-largura").value = v;
  if (salvar && api) api.set_config("largura", v);
}
$("cfg-largura").addEventListener("change",
  () => aplicarLargura($("cfg-largura").value));

function aplicarFonte(v, salvar = true) {
  document.documentElement.dataset.fonte = v;
  $("cfg-fonte").value = v;
  if (salvar && api) api.set_config("fonte", v);
}
$("cfg-fonte").addEventListener("change",
  () => aplicarFonte($("cfg-fonte").value));

function aplicarDensidade(v, salvar = true) {
  document.documentElement.dataset.densidade = v;
  $("cfg-densidade").value = v;
  if (salvar && api) api.set_config("densidade", v);
}
$("cfg-densidade").addEventListener("change",
  () => aplicarDensidade($("cfg-densidade").value));
$("btn-restaurar-colunas").addEventListener("click", restaurarLarguras);
$("cfg-maximizar").addEventListener("change", () =>
  api.set_config("maximizar", $("cfg-maximizar").checked ? "1" : "0"));

// ── wizard ────────────────────────────────────────────────────────────────
let wizEscolha = null;
function iniciarWizard() {
  esconderSplash();
  $("wizard").classList.remove("oculto");
  $("app").classList.add("oculto");
  const sel = $("wiz-uf");
  if (sel.options.length === 1)
    UFS.forEach(uf => sel.add(new Option(uf, uf)));
}
$("wiz-busca").addEventListener("input", async () => {
  wizEscolha = null; $("wiz-ok").disabled = true;
  const texto = $("wiz-busca").value.trim();
  const caixa = $("wiz-sugestoes");
  if (texto.length < 2) { caixa.classList.add("oculto"); return; }
  const achados = await api.municipios(texto, $("wiz-uf").value || null);
  caixa.innerHTML = achados.map(m =>
    `<button role="option" data-c="${m.c}" data-n="${esc(m.n)}" data-uf="${m.uf}">
       ${esc(m.n)} — ${m.uf}</button>`).join("") ||
    `<button disabled>nenhum município encontrado</button>`;
  caixa.classList.remove("oculto");
  caixa.querySelectorAll("button[data-c]").forEach(b =>
    b.addEventListener("click", () => {
      wizEscolha = { c:+b.dataset.c, n:b.dataset.n, uf:b.dataset.uf };
      $("wiz-busca").value = `${b.dataset.n} — ${b.dataset.uf}`;
      caixa.classList.add("oculto");
      $("wiz-ok").disabled = false;
    }));
});
$("wiz-ok").addEventListener("click", async () => {
  if (!wizEscolha) return;
  $("wiz-ok").disabled = true;
  $("wiz-ok").textContent = "Preparando…";
  const trocando = !!estado.municipio;
  if (trocando) {
    const r = await api.trocar_municipio(wizEscolha.c, wizEscolha.n, wizEscolha.uf);
    if (!r?.ok) {
      $("wiz-ok").disabled = false;
      $("wiz-ok").textContent = "Confirmar";
      alert(r?.erro || "Não consegui trocar o município.");
      return;
    }
  } else {
    await api.configurar_municipio(wizEscolha.c, wizEscolha.n, wizEscolha.uf);
  }
  iniciarApp(await api.get_estado());
});

// ── app ───────────────────────────────────────────────────────────────────
async function iniciarApp(e) {
  estado.municipio = e.municipio;
  if (api.listar_municipios_referencia)
    temReferencia = (await api.listar_municipios_referencia()).length > 0;
  $("wizard").classList.add("oculto");
  $("app").classList.remove("oculto");
  $("sub-municipio").textContent =
    `Contratações públicas de ${e.municipio} · ${e.uf}`;
  api.set_titulo(`Licitarium — ${e.municipio}/${e.uf}`);
  progressoSplash(0.6, `${e.municipio} · ${e.uf}`);
  mostrarUltimaSync(e.sincronizado_em);
  renderKpis(e.kpis);
  await carregarFiltros();
  progressoSplash(0.85);
  await prepararPainel(e);
  const aba = ["painel", "contratacoes", "contratos", "atas", "pca", "itens"]
    .includes(e.aba) ? e.aba : "painel";
  document.querySelector(`nav.abas button[data-tipo="${aba}"]`).click();
  esconderSplash();
  // o programa consertou algo no banco para conseguir abrir: dizer, senão o
  // usuário só descobre pelo dado que faltou
  if (e.aviso_abertura) alert(`Licitarium\n\n${e.aviso_abertura}`);
  // sync ao abrir: não forçado, então respeita o intervalo mínimo — abrir o
  // programa várias vezes seguidas não repete a coleta inteira
  api.sincronizar(false);
  api.checar_atualizacao().then(at => {
    if (!at) return;
    const alvo = $("rodape-versao");
    const rotulo = at.auto ? `Nova versão ${esc(at.nova)} — clique para atualizar`
                           : `Nova versão ${esc(at.nova)} disponível ↗`;
    alvo.innerHTML = `<a href="#" id="link-atualizacao"
      style="color:var(--accent)">${rotulo}</a>`;
    $("link-atualizacao").addEventListener("click", async ev => {
      ev.preventDefault();
      if (!at.auto) { api.abrir_atualizacao(); return; }
      if (!confirm(`Baixar e instalar a versão ${at.nova}?\n` +
                   `O Licitarium será fechado e reaberto sozinho.`)) return;
      alvo.textContent = "Baixando atualização…";
      const r = await api.instalar_atualizacao();
      if (!r.ok) alvo.textContent = `Falha na atualização: ${r.erro}`;
    });
  });
}

function mostrarUltimaSync(iso) {
  if (!iso) { $("sync-msg").textContent = "nunca sincronizado"; return; }
  const d = new Date(iso);
  const hora = d.toLocaleTimeString("pt-BR", {hour:"2-digit", minute:"2-digit"});
  const hoje = new Date().toDateString() === d.toDateString();
  $("sync-msg").textContent = hoje
    ? `Sincronizado hoje às ${hora}`
    : `Sincronizado em ${d.toLocaleDateString("pt-BR")} às ${hora}`;
}

function renderKpis(k) {
  $("kpi-contratacoes").textContent =
    new Intl.NumberFormat("pt-BR").format(k.contratacoes);
  $("kpi-homologado").textContent = k.homologado_ano >= 1e6
    ? "R$ " + (k.homologado_ano / 1e6).toLocaleString("pt-BR",
        {maximumFractionDigits:1}) + " mi"
    : dinheiro(k.homologado_ano);
  $("kpi-homologado-l").textContent =
    `homologado em ${new Date().getFullYear()}`;
  $("kpi-vigentes").textContent = k.vigentes;
  const alertas = [];
  if (k.vencendo_60_contratos > 0)
    alertas.push(`<button class="chip" id="chip-vencendo-contratos">⚠
      ${k.vencendo_60_contratos} contrato(s) vence(m) nos próximos 60 dias
      </button>`);
  if (k.vencendo_60_atas > 0)
    alertas.push(`<button class="chip" id="chip-vencendo-atas">⚠
      ${k.vencendo_60_atas} ata(s) vence(m) nos próximos 60 dias</button>`);
  if (k.propostas_abertas > 0)
    alertas.push(`<button class="chip info" id="chip-propostas">⏱
      ${k.propostas_abertas} processo(s) com propostas abertas</button>`);
  $("alertas").innerHTML = alertas.join("");
  $("alertas").classList.toggle("oculto", alertas.length === 0);
  $("chip-vencendo-contratos")?.addEventListener("click",
    () => irPara("contratos", {vencendo: true, ord: "vigencia", dir: "asc"}));
  $("chip-vencendo-atas")?.addEventListener("click",
    () => irPara("atas", {vencendo: true, ord: "vigencia", dir: "asc"}));
  $("chip-propostas")?.addEventListener("click",
    () => irPara("contratacoes", {propostas: true}));
}

async function carregarFiltros() {
  const f = await api.filtros_disponiveis();
  const preencher = (sel, itens) => {
    const atual = sel.value;
    sel.length = 1;
    itens.forEach(i => sel.add(typeof i === "object"
      ? new Option(i.nome, i.id) : new Option(i, i)));
    sel.value = atual;
  };
  preencher($("f-ano"), f.anos);
  preencher($("f-modalidade"), f.modalidades);
  preencher($("f-situacao"), f.situacoes);
  preencher($("f-orgao"),
            f.orgaos.map(o => ({nome: o.nome ?? o.cnpj, id: o.cnpj})));
  // a unidade vem agrupada do backend ("CX" e "Caixa" são uma opção só) e
  // ordenada pelo que mais aparece, que é o que se procura primeiro
  preencher($("f-unidade"), (f.unidades ?? []).map(
    u => ({nome: `${u.nome} (${u.n})`, id: u.nome})));
}

function filtrosAtuais() {
  return { ano: $("f-ano").value || null,
           modalidade: $("f-modalidade").value || null,
           situacao: $("f-situacao").value || null,
           orgao: $("f-orgao").value || null,
           propostas: $("f-propostas").checked || null,
           vigentes: $("f-vigentes").checked || null,
           vencendo: $("f-vence60").checked || null,
           parada: $("f-parada").checked || null,
           so_homologados: $("f-homologados").checked || null,
           origem: $("f-so-meu").checked ? "proprio" : null,
           unidade: $("f-unidade").value || null,
           corrigir: corrigirIpca || null,
           busca: $("f-busca").value.trim() || null,
           // vindo de um alerta do Painel: quais objetos, não qual caixa
           objetos: estado.objetosAlvo || null,
           ord: estado.ord, dir: estado.dir };
}

// [rótulo, chave de ordenação na whitelist do backend — null = não ordenável]
const CAMPOS_FILTRO = ["f-ano", "f-modalidade", "f-situacao", "f-orgao",
                       "f-unidade", "f-busca"];
const CAIXAS_FILTRO = ["f-propostas", "f-vigentes", "f-vence60", "f-parada"];
// f-homologados é padrão ligado na aba Preços, não conta como "filtro ativo"

function temFiltroAtivo() {
  return CAMPOS_FILTRO.some(id => $(id).value)
      || CAIXAS_FILTRO.some(id => $(id).checked)
      || !!estado.objetosAlvo;
}

function limparFiltros() {
  CAMPOS_FILTRO.forEach(id => $(id).value = "");
  CAIXAS_FILTRO.forEach(id => $(id).checked = false);
  estado.objetosAlvo = null;
  estado.pagina = 1;
  carregarLista();
}
$("btn-limpar").addEventListener("click", limparFiltros);

const COLUNAS = {
  contratacoes: [["Número","numero"], ["Modalidade","modalidade"],
                 ["Objeto","objeto"], ["Valor","valor"],
                 ["Situação","situacao"]],
  contratos:    [["Contrato","numero"], ["Objeto / Fornecedor","objeto"],
                 ["Vigência","vigencia"], ["Valor","valor"]],
  atas:         [["Ata","numero"], ["Contratação de origem","origem"],
                 ["Objeto","objeto"], ["Vigência","vigencia"]],
  pca:          [["Item","item"], ["Descrição","descricao"],
                 ["Categoria","categoria"], ["Qtde","quantidade"],
                 ["Valor","valor"]],
  itens:        [["",null], ["Descrição","descricao"], ["Unid.","unidade"],
                 ["Qtde","quantidade"], ["Valor unitário","unitario"],
                 ["Fornecedor","fornecedor"], ["Município","municipio"],
                 ["Processo","origem"]],

};

// Sufixo societário não identifica ninguém e come metade da coluna:
// "STARMEDICAL ... LTDA -EPP" vira "STARMEDICAL ...". O nome íntegro fica
// no tooltip, no detalhe e nos relatórios.
const SUFIXO_SOCIETARIO =
  /[\s,.\-–]*\b(LTDA|LIMITADA|ME|EPP|EIRELI|MEI|S\/A|S\.?\s?A\.?|SA|CIA|EI)\b\.?\s*$/i;

function fornecedorCurto(nome) {
  if (!nome) return "–";
  let s = String(nome).trim();
  for (let i = 0; i < 4 && SUFIXO_SOCIETARIO.test(s); i++)
    s = s.replace(SUFIXO_SOCIETARIO, "").trim();
  return s || String(nome).trim();
}

// nº do contrato no padrão numero/ano (PNCP grava "0033/26" — normaliza
// para 33/2026 usando o ano de 4 dígitos)
function numContrato(d) {
  if (!d.numero_contrato) return d.numero_controle;
  const m = String(d.numero_contrato).match(/^0*(\d+)/);
  const n = m ? m[1] : d.numero_contrato;
  return d.ano_contrato ? `${n}/${d.ano_contrato}` : String(n);
}

function badgeSituacao(s) {
  if (!s) return `<span class="badge mut">–</span>`;
  const cl = /homolog/i.test(s) ? "ok" : /divulgad|aberta|andamento/i.test(s)
    ? "warn" : "mut";
  // "Divulgada no PNCP" -> "Divulgada" (o contexto todo é o PNCP)
  const curto = String(s).replace(/\s+no\s+PNCP$/i, "");
  return `<span class="badge ${cl}" title="${esc(s)}">${esc(curto)}</span>`;
}

// Situação da vigência de contratos e atas. O limiar de 60 dias é o mesmo
// do chip de alerta e do KPI do topo — dois números diferentes para "vence
// logo" na mesma tela confundiriam mais do que ajudariam.
const DIAS_VENCENDO = 60;

function hojeISO() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`
    + `-${String(d.getDate()).padStart(2, "0")}`;
}

function statusVigencia(fim) {
  if (!fim) return null;              // registro sem vigência: nada a dizer
  const dia = String(fim).slice(0, 10);
  const hoje = hojeISO();
  // comparação entre datas ISO é textual de propósito: `new Date("2026-01-01")`
  // é lido como meia-noite UTC e, no nosso fuso, cai no dia anterior
  if (dia < hoje) return { cl: "err", txt: "Encerrado" };
  const dias = Math.round(
    (Date.parse(`${dia}T00:00:00Z`) - Date.parse(`${hoje}T00:00:00Z`)) / 864e5);
  if (dias <= DIAS_VENCENDO)
    return { cl: "warn", txt: dias === 0 ? "Vence hoje" : `Vence em ${dias} d` };
  return { cl: "ok", txt: "Vigente" };
}

// a cor sozinha não informa (daltonismo, impressão em preto e branco): o selo
// leva sempre o texto do estado, e a data completa fica no title
function badgeVigencia(d) {
  const s = statusVigencia(d.vigencia_fim);
  if (!s) return "";
  return ` <span class="badge ${s.cl}" title="Vigência até `
    + `${dataBr(d.vigencia_fim)}">${s.txt}</span>`;
}

// valor da contratação: homologado é definitivo, estimado é estimativa —
// exibir os dois igual faria um processo em andamento parecer fechado
function valorContratacao(d) {
  if (d.valor_homologado != null) return dinheiro(d.valor_homologado);
  if (d.valor_estimado != null)
    return `<span class="est" title="Valor estimado — sem homologação
      registrada no PNCP">${dinheiro(d.valor_estimado)} <small>est.</small></span>`;
  return "–";
}

function renderLinha(tipo, d) {
  if (tipo === "contratacoes")
    return `<span class="dim">${d.sequencial ?? "–"}/${d.ano ?? ""}</span>
      <span class="dim">${esc(d.modalidade_nome ?? "–")}</span>
      <span class="obj">${esc(d.objeto ?? "–")}</span>
      <span class="num">${valorContratacao(d)}</span>
      <span style="justify-self:center">${badgeSituacao(d.situacao)}</span>`;
  if (tipo === "contratos")
    return `<span class="dim">${esc(numContrato(d))}</span>
      <span><span class="obj" title="${esc(d.objeto ?? "")}">${
        esc(d.objeto ?? "–")}</span><br>
        <span class="dim" title="${esc(d.fornecedor_nome ?? "")}">${
          esc(d.fornecedor_nome ?? "")}</span></span>
      <span class="dim vig">${dataBr(d.vigencia_inicio)} – ${dataBr(d.vigencia_fim)}${badgeVigencia(d)}</span>
      <span class="num">${dinheiro(d.valor_global)}</span>`;
  if (tipo === "itens") {
    const homologado = d.valor_unitario_homologado != null;
    const unit = homologado
      ? dinheiro(d.valor_unitario_homologado)
      : `<span class="est" title="Sem resultado homologado: valor de referência
          do edital">${dinheiro(d.valor_unitario_estimado)} <small>est.</small></span>`;
    return `<span class="sel"><input type="checkbox" data-item="${esc(d.id)}"
        ${precosIncluidos.has(String(d.id)) ? "checked" : ""}
        aria-label="Usar na pesquisa: ${esc(d.descricao ?? "item")}"></span>
      <span class="obj" role="button" tabindex="0">${
        esc(d.descricao ?? "–")}</span>
      <span class="dim">${esc(d.unidade ?? "–")}</span>
      <span class="dim">${d.quantidade_homologada ?? d.quantidade ?? "–"}</span>
      <span class="num">${unit}</span>
      ${corrigirIpca ? `<span class="num">${
        d.corrigido != null ? dinheiro(d.corrigido)
          : `<span class="dim" title="Sem data de resultado, ou posterior ao
              último índice publicado">–</span>`}</span>` : ""}
      ${porConteudo ? `<span class="num">${
        d.por_conteudo
          ? `${dinheiroFino(d.por_conteudo.valor)}
             <span class="base">/${esc(d.por_conteudo.rotulo)}</span>`
          : `<span class="dim" title="A embalagem não diz quanto vem dentro"
              >–</span>`}</span>` : ""}
      <span class="dim" title="${esc(d.fornecedor_nome ?? "")}"
        >${esc(fornecedorCurto(d.fornecedor_nome))}</span>
      <span class="dim${d.referencia ? " de-fora" : ""}"
        title="${d.referencia ? "Preço de município de referência"
                              : "Preço do seu município"}"
        >${esc(d.municipio_nome ?? "–")}</span>
      <span class="dim">${d.sequencial ?? "–"}/${d.ano ?? ""}</span>`;
  }
  if (tipo === "pca")
    return `<span class="dim">${esc(d.numero_item)}</span>
      <span class="obj">${esc(d.descricao ?? "–")}</span>
      <span class="dim">${esc(d.categoria ?? "–")}</span>
      <span class="num">${d.quantidade ?? "–"}</span>
      <span class="num">${dinheiro(d.valor_total)}</span>`;
  return `<span class="dim">${esc(d.numero_ata ?? "–")}/${esc(d.ano_ata ?? "")}</span>
    <span class="dim">${esc(d.contratacao_controle ?? "–")}</span>
    <span class="obj">${esc(d.objeto ?? "–")}</span>
    <span class="dim vig">${dataBr(d.vigencia_inicio)} – ${dataBr(d.vigencia_fim)}${badgeVigencia(d)}</span>`;
}

// Quanto a série varia em relação à própria média. Acima de 25% o TCU e os
// manuais de pesquisa de preços já tratam a amostra como dispersa demais
// para a média servir de estimativa — daí a leitura vir escrita, e não só
// o número.
function leituraCv(cv) {
  if (cv < 0.15) return "preços homogêneos";
  if (cv < 0.25) return "variação moderada";
  if (cv < 0.50) return "amostra dispersa — prefira a mediana";
  return "amostra muito dispersa — confira se os itens são comparáveis";
}

// Quem fica de fora precisa aparecer: item cuja embalagem não diz o
// conteúdo, ou que está em outra unidade-base (quilo no meio de folhas).
// Documento que atualiza valor tem de dizer com que índice e até quando.
function correcaoHtml(s) {
  if (!s.corrigido) return "";
  const fora = s.sem_indice
    ? ` ${s.sem_indice} ${s.sem_indice === 1 ? "item ficou" : "itens ficaram"}
        de fora, por não ter data de resultado ou ser posterior ao índice.`
    : "";
  // Quando sai parte grande da série, o número que mudou não é só de escala:
  // é outra amostra. Sem este aviso, a mediana maior lê como inflação.
  const aviso = s.amostra_reduzida
    ? `<div class="disp alerta"><b>Atenção:</b> a correção deixou de fora
        ${s.sem_indice} dos ${s.sem_indice + s.n} preços — os mais recentes,
        ainda sem índice publicado. A série ficou com outra composição, então
        a diferença para os valores originais <b>não é só correção
        monetária</b>.</div>`
    : "";
  return `<div class="disp">Valores corrigidos pelo <b>IPCA</b> até
    <b>${esc(s.ipca_ate_extenso ?? "–")}</b>, a partir da data do resultado de
    cada contratação.${fora}</div>${aviso}`;
}

function semConversaoHtml(s) {
  if (!s.por_conteudo || !s.sem_conversao) return "";
  const n = s.sem_conversao;
  return `<div class="disp"><b>${n} ${n === 1 ? "item ficou" : "itens ficaram"}
    de fora desta comparação</b> — ${n === 1 ? "a embalagem dele não diz" :
    "as embalagens não dizem"} quanto vem dentro, ou ${
    n === 1 ? "está" : "estão"} em outra unidade de medida. O resumo acima é
    só do que dá para comparar por ${esc(s.rotulo_base)}.</div>`;
}

// Box-plot de Tukey + escore Z modificado (MAD) via ECharts — antes desta
// versão (2026-08-11) a pesquisa de preços não tinha gráfico nenhum na
// tela, só texto; e o próprio texto não conseguia mostrar as DUAS cercas
// juntas do jeito que um desenho mostra. `renderer:'svg'` porque o app
// pode imprimir a partir do que a tela desenha — canvas pixela, svg não.
// Com `s.itens` (preço por item, 1.24.0): modo "Anotada" — ponto por item,
// jitter em zigue-zague por ORDEM DE VALOR (não de cadastro, achado do
// usuário: dois preços vizinhos nunca caem na mesma altura, senão o
// rótulo gruda). Sem `s.itens`: modo agregado só com a caixa.
function _jitterPorValor(n, passo = 15) {
  const niveis = [0];
  for (let i = 1; i < n; i++) {
    const grupo = Math.ceil(i / 2);
    niveis.push((i % 2 === 1 ? -1 : 1) * grupo * passo);
  }
  return niveis;
}
function desenharBoxplotPreco(el, s) {
  if (!window.echarts || s.q1 == null) {
    // limpa o que sobrou de um desenho anterior — sem isso, um contêiner
    // oculto (o da prévia de impressão, sem tela pra esconder visualmente)
    // capturaria o SVG de outra pesquisa quando esta não tem quartil
    el.innerHTML = "";
    el.classList.add("oculto");
    return;
  }
  el.classList.remove("oculto");
  const s1 = _corTemaEchart("--s1", "#2a78d6"), s2 = _corTemaEchart("--s2", "#eb6834"),
    erro = _corTemaEchart("--erro", "#a6231b"), warn = _corTemaEchart("--warn", "#7a5c0e"),
    muted = _corTemaEchart("--muted", "#5b6066"), border = _corTemaEchart("--border", "#d3d6da");
  const val = s.por_conteudo ? dinheiroFino : dinheiro;
  const fmt = v => val(v);
  const itens = s.itens || [];
  const markLines = [];
  if (s.limite_sup != null)
    markLines.push({ xAxis: s.limite_sup, lineStyle: { color: s1, type: "dashed", width: 1.4 },
      label: { formatter: "Tukey", color: s1, fontSize: 10, position: "insideEndTop" } });
  if (s.limite_sup_robusto != null)
    markLines.push({ xAxis: s.limite_sup_robusto, lineStyle: { color: warn, type: "dotted", width: 1.4 },
      label: { formatter: "MAD", color: warn, fontSize: 10, position: "insideEndBottom" } });

  const boxplotTooltip = d =>
    `mín <b>${fmt(d[1])}</b><br/>Q1 <b>${fmt(d[2])}</b><br/>` +
    `mediana <b>${fmt(d[3])}</b><br/>Q3 <b>${fmt(d[4])}</b><br/>máx <b>${fmt(d[5])}</b>`;

  const series = [
    { type: "boxplot", data: [[s.minimo, s.q1, s.mediana, s.q3, s.maximo]],
      itemStyle: { color: `${s1}2e`, borderColor: s1, borderWidth: 1.6 },
      boxWidth: ["24%", "24%"], markLine: { symbol: "none", animation: false, data: markLines } },
    { type: "scatter", data: [{ value: [s.media, 0] }], symbol: "diamond",
      symbolSize: 11, itemStyle: { color: s2 }, z: 6 }
  ];

  el.style.height = itens.length ? "240px" : "150px";

  if (itens.length) {
    const ordenados = [...itens].sort((a, b) => a.valor - b.valor);
    const niveis = _jitterPorValor(ordenados.length);
    series.push({ type: "scatter", z: 5, symbolSize: 8,
      data: ordenados.map((it, i) => {
        const j = niveis[i];
        const extrema = it.valor > s.limite_sup
          || (s.limite_sup_robusto != null && it.valor > s.limite_sup_robusto);
        return { value: [it.valor, 0], item: it, symbolOffset: [0, j],
          label: { show: true, formatter: fmt(it.valor).replace(/^R\$\s*/, ""),
            fontSize: 10, position: j <= 0 ? "top" : "bottom",
            color: extrema ? erro : muted },
          itemStyle: { color: extrema ? erro : muted } };
      }) });
  }

  // instância presa ao PRÓPRIO elemento, não a uma variável de módulo —
  // a tela (#precos-boxplot) e a prévia oculta de impressão
  // (#grafico-oculto) desenham ao mesmo tempo, em elementos diferentes;
  // uma só variável faria o dispose() de um derrubar o outro
  if (el.__echart) { el.__echart.dispose(); el.__echart = null; }
  const chart = echarts.init(el, null, { renderer: "svg" });
  el.__echart = chart;
  chart.setOption({
    // sem isso, o SVG capturado pra impressão pega o 1º frame da
    // animação (barras crescendo de zero) — gráfico "zerado" no papel
    animation: false,
    grid: { left: 8, right: 16, top: 22, bottom: 22 },
    xAxis: { type: "value", min: 0, axisLine: { lineStyle: { color: border } },
      axisLabel: { color: muted, fontSize: 11 }, splitLine: { lineStyle: { color: border, opacity: .4 } } },
    yAxis: { type: "category", data: [""], axisLine: { show: false }, axisTick: { show: false } },
    tooltip: { trigger: "item", backgroundColor: "#17181a", borderWidth: 0,
      textStyle: { color: "#fff", fontSize: 12 },
      formatter: p => {
        if (p.seriesType === "boxplot") return boxplotTooltip(p.data);
        if (!p.data.item) return `média <b>${fmt(s.media)}</b>`;
        const it = p.data.item;
        const extrema = it.valor > s.limite_sup
          || (s.limite_sup_robusto != null && it.valor > s.limite_sup_robusto);
        return `<b>${esc(it.descricao)}</b><br/>${esc(it.fornecedor || "")}<br/>${fmt(it.valor)}` +
          (extrema ? '<br/><span style="color:#f08a80">fora da faixa esperada</span>' : "");
      } },
    series
  });
}

function _corTemaEchart(nome, fallback) {
  const v = getComputedStyle(document.documentElement).getPropertyValue(nome).trim();
  return v || fallback;
}

// Barra horizontal — mesmo contrato de relatorios.py:_grafico_barras /
// ui/painel.js:grafBarras: rótulo acima, valor (+ sub-rótulo opcional) no
// fim da barra, ordem de entrada preservada (quem ordena é dados_painel).
// Usado nos 4 gráficos de Economia e no "por modalidade" do Executivo —
// achado 2026-08-11: Economia/Executivo nunca tiveram vista na tela, iam
// direto do banco pro papel; ganham motor aqui como Preços já ganhou.
function desenharBarrasEcharts(el, itens, { valor, rotulo, sub }) {
  if (!window.echarts || !itens || !itens.length) { el.innerHTML = ""; return; }
  const s1 = _corTemaEchart("--s1", "#2a78d6"), muted = _corTemaEchart("--muted", "#5b6066");
  if (el.__echart) { el.__echart.dispose(); el.__echart = null; }
  const chart = echarts.init(el, null, { renderer: "svg" });
  el.__echart = chart;
  el.style.height = Math.max(120, itens.length * 36 + 30) + "px";
  chart.setOption({
    animation: false,
    grid: { left: 4, right: 70, top: 8, bottom: 8, containLabel: true },
    xAxis: { type: "value", show: false },
    yAxis: { type: "category", inverse: true, data: itens.map(it => rotulo(it) ?? "–"),
      axisLine: { show: false }, axisTick: { show: false },
      axisLabel: { color: muted, fontSize: 11 } },
    series: [{ type: "bar", barWidth: 17,
      data: itens.map(it => ({ value: valor(it) || 0,
        _rotuloValor: compacto(valor(it)) + (sub ? " · " + sub(it) : ""),
        itemStyle: { color: s1, borderRadius: [0, 4, 4, 0] } })),
      label: { show: true, position: "right", color: muted, fontSize: 11,
        formatter: p => p.data._rotuloValor } }]
  });
}

// Colunas pareadas estimado (claro) × homologado (cheio) por mês — mesmo
// contrato de relatorios.py:_grafico_meses / ui/painel.js:grafMeses.
function desenharColunasEcharts(el, meses, corVar) {
  if (!window.echarts || !meses) { el.innerHTML = ""; return; }
  const s1 = _corTemaEchart(corVar || "--s1", "#2a78d6"),
    muted = _corTemaEchart("--muted", "#5b6066"),
    border = _corTemaEchart("--border", "#d3d6da");
  const hoje = new Date().getMonth() + 1;
  let ultimo = 0;
  meses.forEach((m, i) => { if (m.valor || m.estimado) ultimo = i + 1; });
  const dados = meses.slice(0, Math.max(ultimo, hoje));
  if (el.__echart) { el.__echart.dispose(); el.__echart = null; }
  const chart = echarts.init(el, null, { renderer: "svg" });
  el.__echart = chart;
  el.style.height = "220px";
  chart.setOption({
    animation: false,
    grid: { left: 8, right: 8, top: 10, bottom: 26, containLabel: true },
    xAxis: { type: "category", data: dados.map(m => MES[m.mes - 1]),
      axisLine: { lineStyle: { color: border } },
      axisLabel: { color: muted, fontSize: 11 } },
    yAxis: { type: "value",
      axisLabel: { color: muted, fontSize: 11,
        formatter: v => compacto(v).replace("R$ ", "") },
      splitLine: { lineStyle: { color: border, opacity: .4 } } },
    tooltip: { trigger: "axis", backgroundColor: "#17181a", borderWidth: 0,
      textStyle: { color: "#fff", fontSize: 12 },
      formatter: ps => {
        const m = dados[ps[0].dataIndex];
        return `<b>${MES[m.mes - 1]}</b><br/>Estimado ${compacto(m.estimado)}` +
          `<br/>Homologado ${compacto(m.valor)}`;
      } },
    series: [
      { name: "Estimado", type: "bar", data: dados.map(m => m.estimado || 0),
        itemStyle: { color: s1, opacity: .32, borderRadius: [4, 4, 0, 0] } },
      { name: "Homologado", type: "bar", data: dados.map(m => m.valor || 0),
        itemStyle: { color: s1, borderRadius: [4, 4, 0, 0] } }
    ]
  });
}

function dispersaoHtml(s) {
  if (s.desvio == null) return "";
  const val = s.por_conteudo ? dinheiroFino : dinheiro;
  const quartis = s.q1 != null
    ? `Metade dos preços entre <b>${val(s.q1)}</b> e
       <b>${val(s.q3)}</b>. `
    : "";
  const pct = (s.cv * 100).toLocaleString("pt-BR",
    {maximumFractionDigits: 0});
  const concentracao = (s.alertas_concentracao ?? []).length
    ? `<div class="disp"><b>Concentração:</b>
        ${esc(s.alertas_concentracao.join("; "))} — preços da mesma fonte
        não são evidências independentes.</div>`
    : "";
  const sens = s.sensibilidade;
  const sensibilidade = sens
    ? `<div class="disp"><b>Sensibilidade:</b> sem o preço mais destoante
        (${val(sens.removido)}), a mediana passaria de
        ${val(sens.mediana_antes)} para ${val(sens.mediana_depois)} e a
        média de ${val(sens.media_antes)} para ${val(sens.media_depois)}.
        Não decide sozinho: mostra o efeito de tirar o pior caso.</div>`
    : "";
  return `<div class="disp">${quartis}Desvio padrão
    <b>${val(s.desvio)}</b> · coeficiente de variação <b>${pct}%</b>
    <span class="dim">(${leituraCv(s.cv)})</span>${
      s.q1 == null
        ? ` <span class="dim">— com ${s.n} ${s.n === 1 ? "preço" : "preços"}
            não dá para medir quartis</span>`
        : ""}</div>${concentracao}${sensibilidade}`;
}

// Aponta, não remove: descartar preço de uma pesquisa é decisão de quem
// assina, e o art. 23 exige justificativa para desprezar valor coletado.
// O intervalo mostrado é o de Tukey quando existe (n >= 5); com menos
// preços só o escore Z modificado (sobre o desvio absoluto mediano) entra
// em ação, e a faixa dele é que aparece.
function foraDaCurvaHtml(s) {
  const n = (s.fora_da_curva ?? []).length;
  if (!n) return "";
  const val = s.por_conteudo ? dinheiroFino : dinheiro;
  const temTukey = s.limite_sup != null;
  const inf = temTukey ? s.limite_inf : s.limite_inf_robusto;
  const sup = temTukey ? s.limite_sup : s.limite_sup_robusto;
  const criterio = temTukey ? "critério de Tukey"
    : "escore Z modificado sobre o desvio absoluto mediano";
  const faixa = inf != null
    ? ` (fora de ${val(Math.max(0, inf))} a ${val(sup)}, pelo ${criterio})`
    : "";
  return `<div class="fora">
    <span>${n === 1 ? "1 preço destoa" : `${n} preços destoam`} do
      conjunto${faixa}. Confira se são
      itens comparáveis antes de usar.</span>
    <button class="btn ghost" id="btn-descartar-fora">
      Descartar ${n === 1 ? "o item" : "os itens"}</button></div>`;
}

let ultimoTermoPrecos = null;

// releitura completa do mapa de descartes a partir do banco — usada na troca
// de termo e depois de uma classificação em lote, onde vários itens mudam
// de estado no servidor de uma vez (mesclar no Map local arriscaria sobrar
// entrada de item que acabou de ser restaurado)
async function recarregarDescartes(termo) {
  precosDescartados = new Map();
  if (api.descartes && termo)
    for (const d of await api.descartes(termo))
      precosDescartados.set(String(d.item_id),
        {motivo: d.motivo, descricao: d.descricao, valor: d.valor});
  atualizarSelecaoPrecos();
}

// pedido do usuário (2026-08-08): a seleção é persistida por termo — releitura
// completa (não mescla no Set local) pelo mesmo motivo de recarregarDescartes:
// depois de "Selecionar todos" ou de classificar por unidade, vários itens
// mudam de estado no servidor de uma vez.
async function recarregarSelecao(termo) {
  precosIncluidos = new Set();
  if (api.selecionados && termo)
    for (const id of await api.selecionados(termo))
      precosIncluidos.add(String(id));
}

// pedido do usuário (2026-08-08): além de marcar item a item, dá pra
// selecionar por fornecedor, faixa de valor ou texto contido na descrição —
// os três somam à seleção atual (nunca substituem, mesma regra da unidade).
async function toolbarSelecaoPrecos(termo, ano, origemVal) {
  const fornecedores = api.fornecedores_pesquisa_precos
    ? await api.fornecedores_pesquisa_precos(termo, ano, origemVal) : [];
  const opcoesForn = fornecedores.map(f =>
    `<option value="${esc(f.ni)}">${esc(f.nome ?? f.ni)} (${f.n})</option>`
  ).join("");
  return `<div class="filtros">
    <select id="sel-fornecedor-preco" aria-label="Selecionar por fornecedor">
      <option value="">Selecionar por fornecedor…</option>${opcoesForn}
    </select>
    <input type="number" id="sel-valor-min" placeholder="De R$" step="0.01"
      aria-label="Selecionar valor mínimo" style="width:100px">
    <input type="number" id="sel-valor-max" placeholder="Até R$" step="0.01"
      aria-label="Selecionar valor máximo" style="width:100px">
    <button class="btn ghost" id="btn-selecionar-faixa">Selecionar faixa</button>
    <input type="text" id="sel-texto" placeholder="Texto na descrição…"
      aria-label="Selecionar por texto na descrição" style="flex:1; min-width:170px">
    <button class="btn ghost" id="btn-selecionar-texto">Selecionar</button>
  </div>`;
}

function ligarToolbarSelecaoPrecos(termo, ano, origemVal) {
  $("sel-fornecedor-preco").addEventListener("change", async (e) => {
    const ni = e.target.value;
    if (!ni || !api.selecionar_por_fornecedor) return;
    await api.selecionar_por_fornecedor(termo, ni, ano, origemVal);
    await recarregarDescartes(termo);
    await recarregarSelecao(termo);
    carregarLista();
    mostrarResumoPrecos();
  });
  $("btn-selecionar-faixa").addEventListener("click", async () => {
    const minimo = $("sel-valor-min").value ? +$("sel-valor-min").value : null;
    const maximo = $("sel-valor-max").value ? +$("sel-valor-max").value : null;
    if ((minimo == null && maximo == null) || !api.selecionar_por_faixa) return;
    await api.selecionar_por_faixa(termo, minimo, maximo, ano, origemVal);
    await recarregarDescartes(termo);
    await recarregarSelecao(termo);
    carregarLista();
    mostrarResumoPrecos();
  });
  $("btn-selecionar-texto").addEventListener("click", async () => {
    const texto = $("sel-texto").value.trim();
    if (!texto || !api.selecionar_por_texto) return;
    await api.selecionar_por_texto(termo, texto, ano, origemVal);
    await recarregarDescartes(termo);
    await recarregarSelecao(termo);
    carregarLista();
    mostrarResumoPrecos();
  });
}

async function mostrarResumoPrecos() {
  // carregarLista já garante descartes/seleção carregados antes de chamar
  // esta função (a corrida entre desenhar as linhas e ler o Set de
  // seleção era real — ver comentário lá); aqui só falta ler o termo atual
  const caixa = $("precos-resumo");
  // esta função reescreve a caixa inteira, e os controles de seleção por
  // critério moram dentro dela: sem guardar o foco, quem usa teclado era
  // jogado para o topo da página a cada seleção em lote (auditoria de
  // acessibilidade, 2026-08-09)
  const focado = document.activeElement?.id || null;
  const termo = $("f-busca").value.trim();
  if (estado.tipo !== "itens" || termo.length < 3 || !api.estatisticas_preco) {
    caixa.classList.add("oculto");
    return;
  }
  const ano = $("f-ano").value ? +$("f-ano").value : null;
  const origemVal = $("f-so-meu").checked ? "proprio" : null;
  const s = await api.estatisticas_preco(termo, ano, origemVal,
    null, porConteudo, corrigirIpca, [...precosIncluidos]);
  if (!s) { caixa.classList.add("oculto"); return; }
  // "X de Y selecionados" — Y é a busca inteira, sem olhar seleção nem
  // descarte (pedido do usuário, item 1: contador visível)
  // role="status": é o único retorno das seleções em lote ("Selecionar
  // todos", faixa, texto) — sem ele o leitor de tela não sabe se marcou 0
  // ou 400 (auditoria de acessibilidade, 2026-08-09)
  const contador = s.total != null
    ? `<div class="dim" role="status" style="font-size:12px; margin:-4px 0 8px">${
        s.nada_selecionado ? 0 : s.n} de ${s.total} selecionados</div>` : "";
  if (s.nada_selecionado) {
    caixa.innerHTML = `<h3>Preços pagos para "${esc(termo)}"</h3>
      ${contador}
      <div class="disp">Nenhum item selecionado ainda. Marque os que quer
        comparar na lista abaixo, ou
        <button class="btn ghost" id="btn-selecionar-todos-resumo"
          style="margin-left:4px">Selecionar todos</button></div>
      ${await toolbarSelecaoPrecos(termo, ano, origemVal)}`;
    caixa.classList.remove("oculto");
    $("btn-selecionar-todos-resumo").addEventListener("click", selecionarTodosPrecos);
    ligarToolbarSelecaoPrecos(termo, ano, origemVal);
    if (focado) $(focado)?.focus();
    return;
  }
  if (!s.n) {          // modo ligado e nenhum item com conteúdo legível
    caixa.innerHTML = `<h3>Preços pagos para "${esc(termo)}"</h3>
      <div class="disp">Nenhum dos ${s.sem_conversao} itens desta pesquisa diz
        quanto vem na embalagem, então não há como compará-los por conteúdo.
        Desligue a caixa para ver os preços como foram pagos.</div>`;
    caixa.classList.remove("oculto");
    return;
  }
  const cel = (v, r, destaque) =>
    `<div class="cel${destaque ? " destaque" : ""}">
       <div class="v">${v}</div><div class="r">${r}</div></div>`;
  // no modo por conteúdo tudo é R$ por unidade-base, e o rótulo diz qual
  const val = s.por_conteudo ? dinheiroFino : dinheiro;
  // "mediana por unidade" no modo; fora dele, os rótulos de sempre
  const rot = (curto, longo) => s.por_conteudo
    ? `${curto} por ${esc(s.rotulo_base)}` : longo;
  // quem decide precisa saber quanto do resultado é da própria série
  const origem = s.referencia
    ? ` <small class="dim">— ${s.proprios} do seu município e ${s.referencia} de referência</small>`
    : "";
  caixa.innerHTML = `<h3>Preços pagos para "${esc(termo)}"${origem}</h3>
    ${contador}
    <div class="grade">
      ${cel(val(s.minimo), rot("menor", "menor unitário"))}
      ${cel(val(s.mediana), rot("mediana", "mediana"), true)}
      ${cel(val(s.media), rot("média", "média"))}
      ${cel(val(s.maximo), rot("maior", "maior unitário"))}
      ${cel(s.n, "itens homologados")}
      ${cel(s.fornecedores, "fornecedores")}
      <button class="btn ghost" id="btn-rel-precos" style="align-self:center">
        Relatório de pesquisa de preços</button>
    </div>
    ${correcaoHtml(s)}${semConversaoHtml(s)}
    <div id="precos-boxplot" class="oculto" style="height:150px"></div>
    ${dispersaoHtml(s)}${foraDaCurvaHtml(s)}
    ${await toolbarSelecaoPrecos(termo, ano, origemVal)}`;
  caixa.classList.remove("oculto");
  desenharBoxplotPreco($("precos-boxplot"), s);
  $("btn-rel-precos").addEventListener("click", abrirRelatorioPrecos);
  $("btn-descartar-fora")?.addEventListener("click", async () => {
    for (const id of s.fora_da_curva ?? []) {
      const idStr = String(id);
      precosIncluidos.delete(idStr);
      await api.desselecionar_preco(ultimoTermoPrecos ?? "", idStr);
      await descartar(idStr);
    }
    carregarLista();
    mostrarResumoPrecos();
    atualizarSelecaoPrecos();
  });
  ligarToolbarSelecaoPrecos(termo, ano, origemVal);
  if (focado) $(focado)?.focus();
}

// ── largura das colunas: arrastar ajusta, duplo clique dá autofit ─────────
// A coluna elástica de cada aba (objeto/descrição) absorve a sobra e por
// isso não tem alça: alargar qualquer outra encolhe ela, que é o que se
// espera ao puxar "fornecedor" para ver o nome inteiro.
const COL_FLEX = { contratacoes:2, contratos:1, atas:2, pca:1, itens:1 };
const LARGURA_MIN = 44;
const FLEX_MIN = 170;       // espaço que a coluna elástica nunca cede
let larguras = {};

function larguraAtualPx() {
  const cab = document.querySelector(".lista .cab");
  if (!cab) return [];
  return getComputedStyle(cab).gridTemplateColumns.split(" ").map(parseFloat);
}

// A aba Preços tem dois conjuntos de colunas; o resto tem um só.
function colunasDe(tipo) {
  if (tipo !== "itens") return COLUNAS[tipo];
  const cols = [...COLUNAS.itens];
  // cada modo insere a sua coluna logo depois do valor efetivamente pago
  let i = 5;
  if (corrigirIpca) cols.splice(i++, 0, ["Corrigido", null]);
  if (porConteudo) cols.splice(i, 0, ["Por conteúdo", null]);
  return cols;
}

// A aba Preços muda de número de colunas conforme o modo ("corrigir pelo
// IPCA" e "comparar por conteúdo" acrescentam uma cada). Guardar tudo sob
// a chave "itens" fazia o arrasto no modo de 9 colunas sobrescrever as
// larguras do modo de 8 — e a guarda abaixo só rejeitava mapa FALTANDO
// entrada, nunca sobrando, então o modo base aplicava as 8 primeiras de um
// layout de 9 e desalinhava (auditoria, 2026-08-09). A chave passa a
// incluir a contagem: cada modo tem as suas.
function chaveLarguras(tipo) {
  return tipo === "itens" ? `itens:${colunasDe(tipo).length}` : tipo;
}

function aplicarLarguras(tipo) {
  const lista = $("lista");
  const chave = chaveLarguras(tipo);
  const mapa = larguras[chave];
  if (!mapa) { lista.style.removeProperty("--cols"); return; }
  const flex = COL_FLEX[tipo];
  const n = colunasDe(tipo).length;
  // larguras guardadas antes de a aba ganhar (ou perder) uma coluna não
  // servem: faltando uma, o grid receberia "NaNpx" e quebraria a lista
  for (let i = 0; i < n; i++)
    if (i !== flex && !(mapa[i] > 0)) {
      delete larguras[chave];
      lista.style.removeProperty("--cols");
      return;
    }
  const cols = [];
  for (let i = 0; i < n; i++)
    cols.push(i === flex ? "minmax(0,1fr)" : `${Math.round(mapa[i])}px`);
  lista.style.setProperty("--cols", cols.join(" "));
}

function guardarLarguras(tipo, px) {
  const flex = COL_FLEX[tipo];
  const chave = chaveLarguras(tipo);
  larguras[chave] = {};
  px.forEach((v, i) => { if (i !== flex) larguras[chave][i] = v; });
}

function autofit(tipo, i) {
  const celulas = [...document.querySelectorAll(".lista .linha:not(.cab)")]
    .map(l => l.children[i]).filter(Boolean);
  const desejada = Math.max(...celulas.map(c => c.scrollWidth),
                            LARGURA_MIN) + 26;   // respiro do padding
  const px = larguraAtualPx();
  const flex = COL_FLEX[tipo];
  // não deixar o autofit engolir a coluna elástica: ela guarda um mínimo
  // referência é a soma das colunas atuais (já desconta padding e vãos,
  // que o clientWidth do container incluiria por engano)
  const outras = px.reduce((s, v, j) => (j === i || j === flex) ? s : s + v, 0);
  const teto = px.reduce((s, v) => s + v, 0) - outras - FLEX_MIN;
  px[i] = Math.max(LARGURA_MIN, Math.min(desejada, teto));
  guardarLarguras(tipo, px);
  aplicarLarguras(tipo);
  api.set_config("colunas", JSON.stringify(larguras));
}

function ligarAlcas() {
  const tipo = estado.tipo;
  const flex = COL_FLEX[tipo];
  document.querySelectorAll(".lista .cab > span").forEach((cel, i) => {
    if (i === flex || i === colunasDe(tipo).length - 1) return;  // última não
    const alca = document.createElement("span");
    alca.className = "alca";
    alca.title = "Arraste para ajustar · duplo clique para caber no conteúdo";
    alca.addEventListener("mousedown", e => {
      e.preventDefault(); e.stopPropagation();
      const x0 = e.clientX, px = larguraAtualPx(), inicial = px[i];
      document.body.classList.add("redimensionando");
      const flex = COL_FLEX[tipo];
      const outras = px.reduce(
        (s, v, j) => (j === i || j === flex) ? s : s + v, 0);
      const teto = px.reduce((s, v) => s + v, 0) - outras - FLEX_MIN;
      const mover = ev => {
        px[i] = Math.max(LARGURA_MIN,
                         Math.min(inicial + (ev.clientX - x0), teto));
        guardarLarguras(tipo, px);
        aplicarLarguras(tipo);
      };
      const soltar = () => {
        document.removeEventListener("mousemove", mover);
        document.removeEventListener("mouseup", soltar);
        document.body.classList.remove("redimensionando");
        api.set_config("colunas", JSON.stringify(larguras));
      };
      document.addEventListener("mousemove", mover);
      document.addEventListener("mouseup", soltar);
    });
    // o clique precisa morrer aqui: o cabeçalho ordena, e ordenar
    // re-renderiza a lista no meio do arrasto/duplo clique
    alca.addEventListener("click", e => {
      e.preventDefault(); e.stopPropagation();
    });
    alca.addEventListener("dblclick", e => {
      e.preventDefault(); e.stopPropagation();
      autofit(tipo, i);
    });
    cel.appendChild(alca);
  });
}

function restaurarLarguras() {
  larguras = {};
  aplicarLarguras(estado.tipo);
  if (api) api.set_config("colunas", "{}");
}

async function carregarLista() {
  // a seleção/descartes têm de estar carregados ANTES de desenhar as
  // linhas — senão a caixa nasce lendo o Set vazio e some marcada errado
  // até o próximo redesenho (corrida real, achada rodando os testes)
  if (estado.tipo === "itens") {
    const termo = $("f-busca").value.trim();
    if (termo !== ultimoTermoPrecos) {
      ultimoTermoPrecos = termo;
      await recarregarDescartes(termo);
      await recarregarSelecao(termo);
    }
  }
  mostrarResumoPrecos();
  const r = await api.listar(estado.tipo, filtrosAtuais(), estado.pagina);
  const g = `g-${estado.tipo}`
    + (estado.tipo === "itens" && porConteudo ? " conteudo" : "")
    + (estado.tipo === "itens" && corrigirIpca ? " corrigido" : "");
  const cab = `<div class="linha cab ${g}">` +
    colunasDe(estado.tipo).map(([rotulo, chave]) => {
      const ativa = chave && estado.ord === chave;
      const seta = ativa ? `<span class="seta">${estado.dir === "asc" ? "▲" : "▼"}</span>` : "";
      const sort = chave ? ` data-ord="${chave}" role="button" tabindex="0"
        aria-sort="${ativa ? (estado.dir === "asc" ? "ascending" : "descending") : "none"}"` : "";
      return `<span${sort}>${rotulo} ${seta}</span>`;
    }).join("") + `</div>`;
  const selecionavel = estado.tipo === "itens";
  const linhas = r.itens.map(d => {
    const nc = esc(d.numero_controle ?? d.id);
    // A linha selecionável é um <div> porque precisa aninhar o checkbox —
    // <input> dentro de <button> é HTML inválido. Mas ela também NÃO leva
    // role="button" (auditoria de acessibilidade, 2026-08-09): filho de
    // botão é apresentacional, então o checkbox perdia o estado marcado e
    // seu rótulo virava o nome da linha. Quem carrega o papel de botão é a
    // célula da descrição — o keydown continua sendo tratado aqui em cima,
    // porque o evento borbulha da célula para a linha.
    return selecionavel
      ? `<div class="linha ${g}" data-nc="${nc}">`
        + renderLinha(estado.tipo, d) + `</div>`
      : `<button class="linha ${g}" data-nc="${nc}">`
        + renderLinha(estado.tipo, d) + `</button>`;
  }).join("");
  const comFiltro = temFiltroAtivo();
  $("btn-limpar").classList.toggle("oculto", !comFiltro);
  $("filtro-alerta").classList.toggle("oculto", !estado.objetosAlvo);
  const vazio = comFiltro
    ? `<div class="vazio"><svg viewBox="0 0 64 64" aria-hidden="true">${SELO}</svg>
        <p>Nenhum registro para estes filtros.</p>
        <button class="btn ghost" id="vazio-limpar">✕ Limpar filtros</button></div>`
    : `<div class="vazio"><svg viewBox="0 0 64 64" aria-hidden="true">${SELO}</svg>
        <p>Nada neste acervo ainda.<br>Sincronize para baixar o que o município
        publicou no PNCP.</p>
        <button class="btn" id="vazio-sync">Sincronizar agora</button></div>`;
  $("lista").innerHTML = cab + (linhas || vazio);
  aplicarLarguras(estado.tipo);
  ligarAlcas();
  $("vazio-limpar")?.addEventListener("click", limparFiltros);
  $("vazio-sync")?.addEventListener("click", () => api.sincronizar());
  $("lista").querySelectorAll(".linha[data-nc]").forEach(b => {
    b.addEventListener("click", e => {
      // clicar na caixa de seleção não pode abrir o detalhe
      if (e.target.closest(".sel")) return;
      abrirDetalhe(b.dataset.nc);
    });
    if (b.tagName === "DIV")
      b.addEventListener("keydown", e => {
        if (e.target.closest(".sel")) return;
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault(); abrirDetalhe(b.dataset.nc);
        }
      });
  });
  $("lista").querySelectorAll('.sel input[data-item]').forEach(c =>
    c.addEventListener("change", async () => {
      const id = String(c.dataset.item);
      const marcou = c.checked;
      // A tela mostra o que `precosIncluidos` diz; o documento sai do que
      // a tabela `precos_selecionados` tem. Se a gravação não pega e
      // ninguém lê o retorno, os dois divergem sem sintoma — a mediana da
      // tela deixa de ser a do papel (auditoria de falha silenciosa,
      // 2026-08-09). Sem `?.` também: os métodos existem, e o `?.` só
      // esconderia uma renomeação futura.
      let gravou = false;
      try {
        if (marcou) {
          // marcar é seleção pura, sem motivo — reconsiderar um item que
          // tinha sido tirado (com razão) limpa o descarte dele também
          precosIncluidos.add(id);
          precosDescartados.delete(id);
          gravou = (await api.selecionar_preco(
            ultimoTermoPrecos ?? "", id))?.ok === true;
        } else {
          precosIncluidos.delete(id);
          gravou = (await api.desselecionar_preco(
            ultimoTermoPrecos ?? "", id))?.ok === true;
          if (gravou) await descartar(id, c.closest(".linha"));
        }
      } catch { gravou = false; }     // o Proxy da ponte já avisou na tela
      if (!gravou) {
        // desfaz e relê do banco, que é quem manda: a tela não pode
        // afirmar uma seleção que o documento não vai enxergar
        c.checked = !marcou;
        $("sync-msg").textContent =
          "Não consegui gravar a seleção — a lista foi recarregada.";
        await recarregarSelecao(ultimoTermoPrecos ?? "");
        await recarregarDescartes(ultimoTermoPrecos ?? "");
        carregarLista();
        return;
      }
      mostrarResumoPrecos();          // o resumo reflete só o que ficou
      atualizarSelecaoPrecos();
    }));
  $("lista").querySelectorAll(".cab span[data-ord]").forEach(s => {
    const ordenar = () => {
      const chave = s.dataset.ord;
      if (estado.ord === chave) estado.dir = estado.dir === "asc" ? "desc" : "asc";
      else { estado.ord = chave; estado.dir = "asc"; }
      estado.pagina = 1;
      carregarLista();
    };
    s.addEventListener("click", ordenar);
    s.addEventListener("keydown", e => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); ordenar(); }
    });
  });
  const paginas = Math.max(1, Math.ceil(r.total / 50));
  $("pag-info").textContent = `${estado.pagina}/${paginas} · ${r.total} registros`;
  $("pag-ant").disabled = estado.pagina <= 1;
  $("pag-prox").disabled = estado.pagina >= paginas;
}

// Estado de aba/visibilidade só, sem consultar o banco — quem chama decide
// se busca a lista ou o painel. Existir separado é o que permite ao clique
// num alerta do Painel montar o filtro inteiro ANTES da única consulta, em
// vez de duas chamadas concorrentes disputando qual pinta a tela por último
// (a de trás, sem filtro nenhum, ganhava a corrida às vezes).
function mudarAba(tipo) {
  marcarAba(document.querySelectorAll("nav.abas button"),
            x => x.dataset.tipo === tipo);
  estado.tipo = tipo;
  estado.pagina = 1;
  // o Painel não é uma lista: troca a tela em vez de trocar as colunas
  const ehPainel = tipo === "painel";
  $("painel").classList.toggle("oculto", !ehPainel);
  for (const id of ["filtros-lista", "lista", "rodape-lista", "kpis-topo"])
    $(id)?.classList.toggle("oculto", ehPainel);
  // os alertas do topo pertencem às listas: no painel eles viram chips
  if (ehPainel) $("alertas").classList.add("oculto");
  else if ($("alertas").innerHTML.trim()) $("alertas").classList.remove("oculto");
  if (api.set_config) api.set_config("aba", tipo);
  if (ehPainel) return;
  estado.ord = null; estado.dir = "desc";
  estado.objetosAlvo = null;
  const soContratacoes = tipo === "contratacoes";
  $("f-modalidade").classList.toggle("oculto", !soContratacoes);
  $("f-situacao").classList.toggle("oculto", !soContratacoes);
  $("cx-propostas").classList.toggle("oculto", !soContratacoes);
  $("cx-parada").classList.toggle("oculto", !soContratacoes);
  const ehVigencia = ["contratos", "atas"].includes(tipo);
  $("cx-vigentes").classList.toggle("oculto", !ehVigencia);
  $("cx-vence60").classList.toggle("oculto", !ehVigencia);
  const ehItens = tipo === "itens";
  $("cx-homologados").classList.toggle("oculto", !ehItens);
  $("f-unidade").classList.toggle("oculto", !ehItens);
  if (!ehItens) $("f-unidade").value = "";
  $("cx-conteudo").classList.toggle("oculto", !ehItens);
  $("cx-corrigir").classList.toggle("oculto", !ehItens);
  // o filtro de origem só faz sentido havendo município de referência
  $("cx-so-meu").classList.toggle("oculto", !ehItens || !temReferencia);
  $("btn-selecionar-todos").classList.toggle("oculto", !ehItens);
  $("f-busca").placeholder = ehItens
    ? "Buscar item — ex.: papel A4, óleo, pneu…"
    : "Buscar no objeto…";
  $("f-propostas").checked = false;
  $("f-vigentes").checked = false;
  $("f-vence60").checked = false;
  $("f-parada").checked = false;
}

document.querySelectorAll("nav.abas button").forEach(b =>
  b.addEventListener("click", () => {
    mudarAba(b.dataset.tipo);
    estado.tipo === "painel" ? carregarPainel() : carregarLista();
  }));
$("f-conteudo").addEventListener("change", () => {
  porConteudo = $("f-conteudo").checked;
  estado.pagina = 1;
  carregarLista();
});
$("f-corrigir").addEventListener("change", () => {
  corrigirIpca = $("f-corrigir").checked;
  estado.pagina = 1;
  carregarLista();
});
["f-propostas", "f-vigentes", "f-vence60", "f-parada", "f-homologados",
 "f-so-meu"].forEach(id => $(id).addEventListener("change",
    () => { estado.pagina = 1; carregarLista(); }));

// navegação programática (KPIs e alertas). Cada campo é sempre escrito, não
// só quando presente em `ajustes` — meio-termo já rendeu bug: o alerta de
// limite mandava a modalidade e ela nunca chegava a ser lida, porque o
// clique na aba resetava só propostas/vigentes e o resto ficava do jeito
// que a navegação anterior tinha deixado.
function irPara(tipo, ajustes = {}) {
  mudarAba(tipo);
  $("f-ano").value = ajustes.ano ?? "";
  $("f-modalidade").value = ajustes.modalidade ?? "";
  $("f-situacao").value = ajustes.situacao ?? "";
  $("f-orgao").value = ajustes.orgao ?? "";
  $("f-propostas").checked = !!ajustes.propostas;
  $("f-vigentes").checked = !!ajustes.vigentes;
  $("f-vence60").checked = !!ajustes.vencendo;
  $("f-parada").checked = !!ajustes.parada;
  estado.objetosAlvo = ajustes.objetos || null;
  if (ajustes.ord) { estado.ord = ajustes.ord; estado.dir = ajustes.dir || "asc"; }
  carregarLista();
}
$("kpi-card-contratacoes").addEventListener("click", () => irPara("contratacoes"));
$("kpi-card-homologado").addEventListener("click",
  () => irPara("contratacoes", {ano: String(new Date().getFullYear())}));
$("kpi-card-vigentes").addEventListener("click",
  () => irPara("contratos", {vigentes: true, ord: "vigencia", dir: "asc"}));
["f-ano","f-modalidade","f-situacao","f-orgao"].forEach(id =>
  $(id).addEventListener("change", () => { estado.pagina = 1; carregarLista(); }));
// achado do usuário (2026-08-08): escolher uma unidade aqui já filtrava a
// lista, mas não classificava a pesquisa de preços — buscar "alface" mistura
// maço, quilo e unidade, e comparar por uma só exigia marcar item por item
// na mão. Agora a escolha já seleciona só os da unidade.
$("f-unidade").addEventListener("change", async () => {
  estado.pagina = 1;
  const unidade = $("f-unidade").value;
  const termo = $("f-busca").value.trim();
  if (unidade && estado.tipo === "itens" && termo && api.classificar_por_unidade) {
    await api.classificar_por_unidade(termo, unidade,
      $("f-ano").value ? +$("f-ano").value : null,
      $("f-so-meu").checked ? "proprio" : null);
    await recarregarDescartes(termo);
    await recarregarSelecao(termo);
  }
  carregarLista();
  mostrarResumoPrecos();
});

// pedido do usuário (2026-08-08): opção de marcar tudo que a busca trouxe de
// uma vez — sobre a pesquisa inteira, não só a página visível na tela.
async function selecionarTodosPrecos() {
  const termo = $("f-busca").value.trim();
  if (!termo || !api.selecionar_todos_precos) return;
  await api.selecionar_todos_precos(termo,
    $("f-ano").value ? +$("f-ano").value : null,
    $("f-so-meu").checked ? "proprio" : null);
  await recarregarDescartes(termo);
  await recarregarSelecao(termo);
  carregarLista();
  mostrarResumoPrecos();
  atualizarSelecaoPrecos();
}
$("btn-selecionar-todos")?.addEventListener("click", selecionarTodosPrecos);
let buscaTimer;
$("f-busca").addEventListener("input", () => {
  clearTimeout(buscaTimer);
  buscaTimer = setTimeout(() => { estado.pagina = 1; carregarLista(); }, 300);
});
$("pag-ant").addEventListener("click", () => {
  estado.pagina--; carregarLista(); });
$("pag-prox").addEventListener("click", () => {
  estado.pagina++; carregarLista(); });

// ── detalhe ───────────────────────────────────────────────────────────────
const ROTULOS = {
  unidade:"Unidade", material_servico:"Tipo",
  valor_unitario_estimado:"Valor unitário estimado",
  valor_unitario_homologado:"Valor unitário homologado",
  valor_total_homologado:"Valor total homologado",
  quantidade_homologada:"Quantidade homologada",
  fornecedor_porte:"Porte do fornecedor", data_resultado:"Data do resultado",
  numero_ata:"Ata nº", ano_ata:"Ano da ata",
  numero_contrato:"Contrato nº", ano_contrato:"Ano do contrato",
  numero_item:"Item nº", categoria:"Categoria", grupo:"Grupo de contratação",
  quantidade:"Quantidade estimada", valor_total:"Valor total",
  id_pca:"Plano (id PNCP)", ano:"Ano",
  modalidade_nome:"Modalidade", situacao:"Situação", orgao_nome:"Órgão",
  valor_estimado:"Valor estimado",
  valor_homologado:"Valor homologado", valor_global:"Valor global",
  fornecedor_nome:"Fornecedor", fornecedor_ni:"CNPJ/CPF fornecedor",
  data_publicacao:"Publicação", data_atualizacao:"Última atualização",
  vigencia_inicio:"Início da vigência", vigencia_fim:"Fim da vigência",
  contratacao_controle:"Contratação de origem", orgao_cnpj:"CNPJ do órgão",
};
function jsonColorido(obj) {
  // escapa só &, < e > (aspas precisam sobreviver para o tokenizador)
  const json = JSON.stringify(obj, null, 2)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  return json.replace(
    /("(?:\\.|[^"\\])*")(?=\s*:)|("(?:\\.|[^"\\])*")|\b(true|false)\b|\b(null)\b|(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)/g,
    (m, chave, str, bool, nulo) => {
      const cls = chave ? "j-chave" : str ? "j-str" : bool ? "j-bool"
                : nulo ? "j-null" : "j-num";
      return `<span class="${cls}">${m}</span>`;
    });
}

let detalheAtual = null;
async function abrirDetalhe(nc) {
  const d = await api.detalhe(estado.tipo, nc);
  if (!d) return;
  detalheAtual = nc;
  $("det-titulo").textContent = d.objeto || d.descricao || d.numero_controle || d.id;
  $("det-sub").textContent = d.numero_controle || d.id_pca || "";
  $("det-pncp").classList.toggle("oculto", estado.tipo === "pca");
  $("det-meta").innerHTML = Object.entries(ROTULOS)
    .filter(([campo]) => d[campo] != null && d[campo] !== "")
    .map(([campo, rotulo]) => {
      let v = d[campo];
      if (campo.startsWith("valor")) v = dinheiro(v);
      else if (campo === "numero_contrato") v = numContrato(d);
      else if (/^(data|vigencia)/.test(campo)) v = dataBr(v);
      return `<div><div class="k">${rotulo}</div><div class="v">${esc(v)}</div></div>`;
    }).join("");
  $("det-raw").innerHTML = jsonColorido(d.raw);
  abrirModal("veu-detalhe");
}
$("det-pncp").addEventListener("click", () =>
  api.abrir_pncp(estado.tipo, detalheAtual));
$("det-imprimir").addEventListener("click", () =>
  api.imprimir_detalhe(estado.tipo, detalheAtual,
    $("det-titulo").textContent, $("det-sub").textContent,
    $("det-meta").innerHTML));

// ── montador de minuta do PCA ─────────────────────────────────────────────
$("btn-pca").addEventListener("click", async () => {
  const anos = await api.anos_com_itens();
  const sel = $("pca-ano");
  if (!sel.options.length) {
    const proximo = (anos.length ? Math.max(...anos) : new Date().getFullYear()) + 1;
    for (let a = proximo; a >= proximo - 2; a--) sel.add(new Option(a, a));
  }
  if (!anos.length) {
    $("pca-status").textContent =
      "Sincronize os itens antes: a minuta vem do que já foi contratado.";
  }
  await carregarMinuta();
  abrirModal("veu-pca");
});

function parametrosPca() {
  return {
    base: $("pca-base").value,
    estatistica: $("pca-estatistica").value,
    margem: parseFloat($("pca-margem").value) || 0,
    palavras: +$("pca-palavras").value,
    so_recorrentes: $("pca-recorrentes").checked,
  };
}

$("pca-gerar").addEventListener("click", async () => {
  $("pca-gerar").disabled = true;
  $("pca-status").textContent = "Consolidando o histórico…";
  const r = await api.gerar_minuta_pca(+$("pca-ano").value, parametrosPca());
  $("pca-gerar").disabled = false;
  $("pca-status").textContent = r.ok
    ? `${r.grupos} grupos gerados · ajustes manuais foram preservados`
    : `Falha: ${r.erro}`;
  await carregarMinuta();
});

$("pca-ano").addEventListener("change", carregarMinuta);

let familiaFiltro = null;      // família selecionada na revisão em 2 níveis
let selecionados = new Set();  // itens marcados para mesclar

async function carregarMinuta() {
  const dados = await api.listar_minuta_pca(+$("pca-ano").value);
  const t = dados.totais;
  // chips de família: revisar 1.500 linhas soltas é inviável; por família,
  // o gestor ataca PNEU, FILTRO, PAPEL… um bloco de cada vez
  const familias = dados.familias || [];
  $("pca-familias").innerHTML = familias.length > 1 ? [
    `<button data-familia="" class="${familiaFiltro ? "" : "on"}">Todas
       <small>${dados.itens.length}</small></button>`,
    ...familias.slice(0, 40).map(f =>
      `<button data-familia="${esc(f.familia)}"
        class="${familiaFiltro === f.familia ? "on" : ""}"
        title="${dinheiro(f.valor)}">${esc(f.familia)}
        <small>${f.itens}</small></button>`)].join("") : "";
  $("pca-familias").querySelectorAll("button").forEach(b =>
    b.addEventListener("click", () => {
      familiaFiltro = b.dataset.familia || null;
      carregarMinuta();
    }));
  const classeA = dados.itens.filter(i => i.abc === "A").length;
  $("pca-totais").innerHTML = dados.itens.length
    ? `<b>${t.grupos}</b> itens no plano · <b>${dinheiro(t.valor)}</b>
       ${classeA ? ` · <b>${classeA}</b> itens classe A concentram 80% do valor` : ""}
       ${t.excluidos ? ` · ${t.excluidos} excluído(s)` : ""}
       ${dados.gerado_em ? ` · gerado em ${dataBr(dados.gerado_em)}` : ""}`
    : `Nenhuma minuta para este exercício — ajuste os parâmetros e clique em
       <b>Gerar</b>.`;
  const cab = `<div class="linha cab g-pca-minuta">
      <span title="Selecionar para mesclar">⚯</span>
      <span title="Incluir no plano">✓</span>
      <span title="Curva ABC: A concentra 80% do valor">ABC</span>
      <span>Descrição</span>
      <span>Unid.</span><span class="num">Quantidade</span>
      <span class="num">Unitário</span><span class="num">Margem</span>
      <span class="num">Total</span></div>`;
  const visiveis = familiaFiltro
    ? dados.itens.filter(i => i.familia === familiaFiltro) : dados.itens;
  const linhas = visiveis.map(i => `
    <div class="linha g-pca-minuta" data-id="${i.id}">
      <span><input type="checkbox" data-sel="${i.id}"
        ${selecionados.has(i.id) ? "checked" : ""}
        aria-label="Selecionar para mesclar"></span>
      <span><input type="checkbox" data-campo="incluir"
        ${i.incluir ? "checked" : ""} aria-label="Incluir"></span>
      <span><span class="abc abc-${i.abc || "C"}"
        title="Classe ${i.abc || "C"}">${i.abc || "C"}</span></span>
      <span><input type="text" data-campo="descricao"
        value="${esc(i.descricao ?? "")}">
        ${i.origem && i.origem.recorrente === false
          ? '<span class="tag-unico" title="Contratado uma única vez: confira se cabe no plano">OCORRÊNCIA ÚNICA</span>' : ""}
        ${i.origem && i.origem.preco_disperso
          ? `<span class="tag-unico" title="Preços do grupo variam de
              ${dinheiro(i.origem.preco_min)} a ${dinheiro(i.origem.preco_max)}:
              provável lote lançado como item">PREÇO DISPERSO</span>` : ""}
        ${i.mesclado
          ? '<button class="tag-mesclado" data-dividir="' + i.id + '" title="Desfazer a mesclagem">MESCLADO ⤢</button>' : ""}</span>
      <span><input type="text" data-campo="unidade" value="${esc(i.unidade ?? "")}">
        ${i.origem && i.origem.unidades_divergentes
          ? '<span class="aviso-un" title="O grupo tem unidades diferentes; confira">⚠</span>' : ""}</span>
      <span><input type="number" data-campo="quantidade" step="0.01"
        value="${i.quantidade ?? 0}"></span>
      <span><input type="number" data-campo="valor_unitario" step="0.01"
        value="${i.valor_unitario ?? 0}"></span>
      <span><input type="number" data-campo="margem" step="1"
        value="${i.margem ?? 0}"></span>
      <span class="num">${dinheiro(i.valor_total)}</span>
    </div>`).join("");
  $("pca-lista").innerHTML = cab + (linhas ||
    `<div class="vazio">Sem itens. Clique em <b>Gerar</b>.</div>`);
  // seleção para mesclagem
  $("pca-lista").querySelectorAll("[data-sel]").forEach(cx =>
    cx.addEventListener("change", () => {
      const id = +cx.dataset.sel;
      cx.checked ? selecionados.add(id) : selecionados.delete(id);
      $("pca-mesclar").disabled = selecionados.size < 2;
      $("pca-mesclar").textContent = selecionados.size > 1
        ? `⚯ Mesclar ${selecionados.size} itens` : "⚯ Mesclar selecionados";
    }));
  $("pca-lista").querySelectorAll("[data-dividir]").forEach(b =>
    b.addEventListener("click", async () => {
      const r = await api.dividir_item_minuta(+b.dataset.dividir);
      $("pca-status").textContent = r.ok
        ? `Mesclagem desfeita: ${r.itens} itens restaurados` : r.erro;
      await carregarMinuta();
    }));
  $("pca-lista").querySelectorAll("[data-campo]").forEach(campo =>
    campo.addEventListener("change", async () => {
      const linha = campo.closest(".linha");
      const valor = campo.type === "checkbox" ? (campo.checked ? 1 : 0)
                  : campo.type === "number" ? parseFloat(campo.value) || 0
                  : campo.value;
      await api.editar_item_minuta(+linha.dataset.id,
                                   { [campo.dataset.campo]: valor });
      await carregarMinuta();   // recalcula totais com o ajuste
    }));
}

$("pca-mesclar").addEventListener("click", async () => {
  const r = await api.mesclar_itens_minuta(+$("pca-ano").value,
                                           [...selecionados]);
  $("pca-status").textContent = r.ok
    ? `${r.itens} itens fundidos — quantidade somada e preço ponderado`
    : r.erro;
  selecionados.clear();
  $("pca-mesclar").disabled = true;
  $("pca-mesclar").textContent = "⚯ Mesclar selecionados";
  await carregarMinuta();
});

$("pca-csv").addEventListener("click", async () => {
  const r = await api.exportar_csv("minuta_pca", { ano: +$("pca-ano").value });
  $("pca-status").textContent = r.ok
    ? `CSV com ${r.linhas} itens em ${r.arquivo}` : (r.erro || "");
});
$("pca-relatorio").addEventListener("click", async () => {
  const r = await api.gerar_relatorio("minuta_pca", { ano: +$("pca-ano").value });
  $("pca-status").textContent = r.ok ? "Relatório aberto no navegador"
                                     : (r.erro || "Falha ao gerar");
});

// ── relatórios ────────────────────────────────────────────────────────────
async function montarOpcoesRelatorio() {
  const tipo = $("rel-tipo").value;
  const f = await api.filtros_disponiveis();
  const sel = $("rel-ano");
  sel.length = 0;
  const soExercicio = ["executivo", "fracionamento"].includes(tipo);
  $("rel-termo-caixa").classList.toggle("oculto", tipo !== "precos");
  if (!soExercicio) {
    if (!["contratacoes", "precos"].includes(tipo))
      sel.add(new Option("Vigentes hoje", "vigentes"));
    sel.add(new Option("Todo o período", "todos"));
  }
  f.anos.forEach(a => sel.add(new Option(`Exercício ${a}`, `ano:${a}`)));
  if (soExercicio && !f.anos.length)
    sel.add(new Option(`Exercício ${new Date().getFullYear()}`,
                       `ano:${new Date().getFullYear()}`));
  const modCaixa = $("rel-mod-caixa");
  modCaixa.classList.toggle("oculto", tipo !== "contratacoes");
  const modSel = $("rel-modalidade");
  modSel.length = 1;
  f.modalidades.forEach(m => modSel.add(new Option(m.nome, m.id)));
  const orgSel = $("rel-orgao");
  orgSel.length = 1;
  f.orgaos.forEach(o => orgSel.add(new Option(o.nome ?? o.cnpj, o.cnpj)));
}
$("btn-relatorios").addEventListener("click", async () => {
  await montarOpcoesRelatorio();
  $("rel-status").textContent = "";
  abrirModal("veu-relatorios");
});
$("rel-tipo").addEventListener("change", montarOpcoesRelatorio);
// atalho: na aba Preços, o termo buscado já vai preenchido no relatório
function abrirRelatorioPrecos() {
  $("rel-tipo").value = "precos";
  montarOpcoesRelatorio().then(() => {
    $("rel-termo").value = $("f-busca").value.trim();
    $("rel-status").textContent = "";
    abrirModal("veu-relatorios");
  });
}
$("rel-gerar").addEventListener("click", async () => {
  const periodo = $("rel-ano").value;
  const params = {
    ano: periodo.startsWith("ano:") ? +periodo.slice(4) : null,
    vigentes: periodo === "vigentes",
    modalidade: $("rel-modalidade").value || null,
    orgao: $("rel-orgao").value || null,
    termo: $("rel-termo").value || null,
  };
  // o que o usuário descartou na tela não entra no documento — mas só
  // quando o relatório é o da própria pesquisa em curso
  if ($("rel-tipo").value === "precos" && precosDescartados.size
      && params.termo === ultimoTermoPrecos)
    params.excluidos = [...precosDescartados.keys()];
  if ($("rel-tipo").value === "precos" && !params.termo) {
    $("rel-status").textContent = "Informe o que pesquisar";
    $("rel-termo").focus();
    return;
  }
  $("rel-gerar").disabled = true;
  $("rel-status").textContent = "Gerando…";
  // desenha o mesmo gráfico da aba Preços num contêiner fora da tela,
  // captura o SVG e manda pro papel — sem isso o relatório de preços
  // nunca passa pela tela antes de imprimir (diferente do Painel) e
  // ficaria preso ao SVG à mão pra sempre. Se a prévia falhar (nada
  // selecionado, por exemplo), segue sem grafico_html: gerar_relatorio
  // já dá o mesmo erro por conta própria, então o usuário não fica sem
  // explicação — só sem o gráfico bonito.
  if ($("rel-tipo").value === "precos" && api.dados_grafico_precos) {
    const g = await api.dados_grafico_precos(
      params.termo, params.ano, params.orgao, params.excluidos,
      false, false);
    if (g?.ok) {
      desenharBoxplotPreco($("grafico-oculto"), g.resumo);
      params.grafico_html = $("grafico-oculto").innerHTML;
    }
  }
  // mesma ideia pros dois relatórios que usam os gráficos do Painel —
  // api.painel() já devolve exatamente o que dados_painel() usaria, então
  // não precisa de método novo. Cada gráfico é desenhado no MESMO
  // contêiner oculto, um de cada vez, e capturado antes do próximo.
  if (["executivo", "economia"].includes($("rel-tipo").value) && api.painel) {
    const anoAlvo = params.ano || new Date().getFullYear();
    const dp = await api.painel(anoAlvo, params.orgao);
    if (dp) {
      params.graficos = {};
      const capturar = (chave, itens, opts) => {
        desenharBarrasEcharts($("grafico-oculto"), itens, opts);
        params.graficos[chave] = $("grafico-oculto").innerHTML;
      };
      if ($("rel-tipo").value === "executivo") {
        desenharColunasEcharts($("grafico-oculto"), dp.execucao.meses, "--s1");
        params.graficos.meses = $("grafico-oculto").innerHTML;
        capturar("modalidade", dp.execucao.modalidades.slice(0, 6), {
          valor: m => m.homologado || m.estimado || 0,
          rotulo: m => m.modalidade_nome || "–",
          sub: m => `${m.n} ${m.n === 1 ? "processo" : "processos"}` });
      } else {
        const item = n => n === 1 ? "item" : "itens";
        capturar("modalidade", dp.economia.por_modalidade, {
          valor: m => m.economizado || 0, rotulo: m => m.modalidade || "–",
          sub: m => `${m.n} ${m.n === 1 ? "processo" : "processos"}` });
        capturar("familia", dp.economia.por_familia, {
          valor: f => f.economizado || 0, rotulo: f => f.nome || "–",
          sub: f => `${f.n} ${item(f.n)}` });
        capturar("categoria", dp.economia.por_categoria, {
          valor: c => c.economizado || 0, rotulo: c => c.nome || "–",
          sub: c => `${c.n} ${item(c.n)}` });
        capturar("fornecedor", dp.economia.por_fornecedor, {
          valor: f => f.economizado || 0, rotulo: f => f.nome || "–",
          sub: f => `${f.n} ${item(f.n)} · ${(f.pct || 0).toFixed(0)}%` });
      }
    }
  }
  const r = await api.gerar_relatorio($("rel-tipo").value, params);
  $("rel-gerar").disabled = false;
  $("rel-status").textContent = r.ok
    ? "Aberto no navegador" + (r.csv ? " · CSV gerado ao lado" : "")
    : (r.erro || "Falha ao gerar");
});

// ── municípios de referência (banco de preços) ────────────────────────────
// backend já devolve por tamanho desc (o padrão); nome/itens são reordenados
// aqui — lista é pequena (poucas dezenas), não vale ida ao banco por critério
const ORDENS_REFERENCIA = {
  tamanho: (a, b) => (b.mb || 0) - (a.mb || 0),
  nome: (a, b) => a.nome.localeCompare(b.nome, "pt-BR"),
  itens: (a, b) => (b.itens || 0) - (a.itens || 0),
};
$("ref-ordem").addEventListener("change", renderReferencia);

async function renderReferencia() {
  const lista = await api.listar_municipios_referencia();
  lista.sort(ORDENS_REFERENCIA[$("ref-ordem").value]);
  // mesmo formato dos órgãos monitorados logo acima: nome, identificação
  // embaixo e o controle à direita
  $("cfg-referencia").innerHTML = lista.map(m =>
    `<div class="orgrow"><span>${esc(m.nome)} — ${esc(m.uf)}
       <small>IBGE ${esc(m.ibge)} · ${m.itens
         ? `${m.itens.toLocaleString("pt-BR")} ${m.itens === 1 ? "preço" : "preços"} no banco`
           + ` · ocupa ~${(m.mb || 0).toLocaleString("pt-BR")} MB`
         : "ainda sem preços — serão baixados na próxima sincronização"}</small></span>
     <button class="btn ghost" data-remover="${esc(m.ibge)}">Remover</button></div>`)
    .join("") || `<div class="dim">Nenhum — o banco de preços usa só o seu
      município.</div>`;
  $("cfg-referencia").querySelectorAll("button[data-remover]").forEach(b =>
    b.addEventListener("click", async () => {
      const nome = b.closest(".orgrow").querySelector("span")
        .firstChild.textContent.trim();
      if (!confirm(`Remover ${nome}?\n\n`
                   + "Os preços que ele trouxe saem do banco.")) return;
      b.disabled = true;
      const r = await api.remover_municipio_referencia(b.dataset.remover);
      if (!r?.ok) {
        alert(r?.erro || "Não consegui remover.");
        b.disabled = false;
        return;
      }
      await renderReferencia();
    }));
}

// O peso varia em ordens de grandeza entre municípios: um vizinho pequeno
// custa minutos, uma cidade média custa horas e centenas de MB. Perguntar
// antes evita a descoberta desagradável no meio da coleta.
async function confirmarVolume(codigo, nome) {
  if (!api.estimar_municipio_referencia) return true;
  $("sync-msg").textContent = `Consultando o volume de ${nome}…`;
  const e = await api.estimar_municipio_referencia(codigo);
  $("sync-msg").textContent = "";
  const nl = "\n";
  if (!e || e.erro) {
    return confirm(`Não consegui consultar o volume de ${nome}`
      + `${e && e.erro ? ` (${e.erro})` : ""}.${nl}${nl}`
      + "Adicionar mesmo assim?");
  }
  if (!e.contratacoes) {
    alert(`${nome} não tem contratações publicadas no PNCP — não traria `
      + "nenhum preço.");
    return false;
  }
  const tempo = e.minutos >= 60
    ? `${(e.minutos / 60).toFixed(1).replace(".", ",")} horas`
    : `${e.minutos} minutos`;
  // coleta de horas merece aviso destacado: é o caso de cidade média
  const pesado = e.minutos >= 60
    ? `${nl}${nl}ATENÇÃO: é uma coleta longa. Ela roda em segundo plano e `
      + "você pode continuar usando o programa, mas leva bastante tempo."
    : "";
  return confirm(
    `${nome} tem ${e.contratacoes.toLocaleString("pt-BR")} contratações`
    + `${e.parcial ? " (pelo menos — algumas consultas falharam)" : ""}.`
    + `${nl}${nl}A coleta deve trazer cerca de `
    + `${e.itens.toLocaleString("pt-BR")} preços, ocupar `
    + `${String(e.mb).replace(".", ",")} MB e levar aproximadamente `
    + `${tempo}.${pesado}${nl}${nl}Adicionar mesmo assim?`);
}

// A razão pode vir depois: exigi-la no clique atrapalharia quem descarta
// dez itens de uma vez. Quem cobra é o relatório.
async function descartar(id, linha) {
  const celulas = linha ? linha.querySelectorAll("span") : [];
  precosDescartados.set(id, {
    motivo: precosDescartados.get(id)?.motivo ?? null,
    descricao: celulas[1]?.textContent.trim() ?? null,
    valor: null,
  });
  await api.descartar_preco(ultimoTermoPrecos ?? "", id,
                              precosDescartados.get(id).motivo);
}

// Motivos vêm do backend para tela e documento falarem igual; carregados
// uma vez, porque a lista é fixa.
let motivosDescarte = null;

async function carregarMotivos() {
  if (!motivosDescarte && api.motivos_descarte)
    motivosDescarte = await api.motivos_descarte();
  return motivosDescarte ?? [];
}

// O descarte é registrado por pesquisa: sai do cálculo, entra no relatório
// numa seção própria e a razão fica gravada. Sem razão, o documento acusa.
async function atualizarSelecaoPrecos() {
  const caixa = $("precos-selecao");
  if (!caixa) return;
  const n = precosDescartados.size;
  caixa.classList.toggle("oculto", n === 0);
  if (!n) return;
  const motivos = await carregarMotivos();
  const opcoes = (atual) => motivos.map(m =>
    `<option value="${esc(m.id)}"${m.id === atual ? " selected" : ""}
      >${esc(m.texto)}</option>`).join("");
  const linhas = [...precosDescartados.entries()].map(([id, d]) => {
    const conhecido = motivos.some(m => m.id === d.motivo);
    const livre = d.motivo && !conhecido;
    return `<div class="descartado">
      <span class="obj" title="${esc(d.descricao ?? "")}"
        >${esc(d.descricao ?? id)}</span>
      <span class="num dim">${d.valor != null ? dinheiro(d.valor) : ""}</span>
      <select data-motivo="${esc(id)}" aria-label="Razão do descarte">
        <option value="">Sem justificativa…</option>
        ${opcoes(d.motivo)}
        <option value="__outro"${livre ? " selected" : ""}>Outro…</option>
      </select>
      <input type="text" data-livre="${esc(id)}" maxlength="200"
        class="${livre ? "" : "oculto"}" placeholder="Escreva a razão"
        value="${esc(livre ? d.motivo : "")}">
    </div>`;
  }).join("");
  const semRazao = [...precosDescartados.values()].filter(d => !d.motivo).length;
  caixa.innerHTML =
    `<div class="descarte-topo">
       <span>${n} ${n === 1 ? "item descartado" : "itens descartados"} desta
         pesquisa — ${n === 1 ? "não entra" : "não entram"} no resumo, mas
         ${n === 1 ? "consta" : "constam"} no relatório com a razão.${
           semRazao ? ` <b>${semRazao} sem justificativa.</b>` : ""}</span>
       <button class="btn ghost" id="precos-restaurar">Restaurar todos</button>
     </div>${linhas}`;
  $("precos-restaurar").addEventListener("click", async () => {
    // "restaurar" reconsidera — cada item volta a ser selecionado, não só
    // sai da lista de descartados (senão ficaria fora da conta de novo).
    // Cada gravação é conferida (mesmo cuidado do toggle individual,
    // auditoria de falha silenciosa 2026-08-09): sem isso, uma falha no
    // meio do lote deixava a tela "restaurada" com o banco ainda
    // descartado. `selecionar_preco` já apaga o descarte no servidor
    // quando grava — a releitura no fim reflete exatamente o que pegou.
    let falhou = 0;
    for (const id of [...precosDescartados.keys()]) {
      let gravou = false;
      try {
        gravou = (await api.selecionar_preco(
          ultimoTermoPrecos ?? "", id))?.ok === true;
      } catch { gravou = false; }     // o Proxy da ponte já avisou na tela
      if (gravou) precosIncluidos.add(id);
      else falhou++;
    }
    if (falhou) {
      $("sync-msg").textContent =
        `Não consegui restaurar ${falhou} ${falhou === 1 ? "item" : "itens"}` +
        " — a lista foi recarregada.";
      await recarregarSelecao(ultimoTermoPrecos ?? "");
    }
    await recarregarDescartes(ultimoTermoPrecos ?? "");
    carregarLista();
    mostrarResumoPrecos();
    atualizarSelecaoPrecos();
  });
  caixa.querySelectorAll("select[data-motivo]").forEach(sel =>
    sel.addEventListener("change", async () => {
      const id = sel.dataset.motivo;
      const livre = caixa.querySelector(`input[data-livre="${CSS.escape(id)}"]`);
      livre.classList.toggle("oculto", sel.value !== "__outro");
      if (sel.value === "__outro") { livre.focus(); return; }
      await registrarMotivo(id, sel.value || null);
    }));
  caixa.querySelectorAll("input[data-livre]").forEach(campo =>
    campo.addEventListener("change", () =>
      registrarMotivo(campo.dataset.livre, campo.value.trim() || null)));
}

async function registrarMotivo(id, motivo) {
  const d = precosDescartados.get(id);
  if (!d) return;
  d.motivo = motivo;
  await api.descartar_preco(ultimoTermoPrecos ?? "", id, motivo);
  atualizarSelecaoPrecos();
}

// ── cópia do acervo ───────────────────────────────────────────────────────
// Restaurar troca o banco inteiro, então a confirmação diz o que entra e o
// que sai — e o programa precisa reabrir para ler o arquivo novo.
$("btn-exportar-acervo")?.addEventListener("click", async () => {
  const msg = $("acervo-msg");
  msg.textContent = "Salvando cópia…";
  const r = await api.exportar_acervo();
  if (!r.ok) { msg.textContent = r.erro ? `Falhou: ${r.erro}` : ""; return; }
  const c = r.contagens || {};
  msg.textContent = `Cópia salva (${r.mb} MB): ${c.contratacoes || 0}`
    + ` contratações, ${(c.itens || 0).toLocaleString("pt-BR")} itens e`
    + ` ${c.municipios_referencia || 0} municípios de referência.`;
});

$("btn-importar-acervo")?.addEventListener("click", async () => {
  const msg = $("acervo-msg");
  if (!confirm("Restaurar uma cópia substitui todo o acervo atual.\n\n"
               + "O banco de agora é guardado ao lado, renomeado, e o "
               + "programa precisa ser fechado e aberto de novo.\n\n"
               + "Escolher o arquivo?")) return;
  msg.textContent = "Conferindo o arquivo…";
  const r = await api.importar_acervo();
  if (!r.ok) { msg.textContent = r.erro ? `Falhou: ${r.erro}` : ""; return; }
  msg.textContent = `Acervo restaurado (${(r.itens || 0).toLocaleString("pt-BR")}`
    + ` itens). Feche e abra o Licitarium para usá-lo.`;
  alert("Acervo restaurado.\n\nFeche e abra o Licitarium para carregar o "
        + "acervo restaurado.");
});

function ligarBuscaReferencia() {
  const uf = $("ref-uf");
  if (uf.options.length === 0) {
    uf.add(new Option("UF", ""));
    UFS.forEach(u => uf.add(new Option(u, u)));
  }
  const caixa = $("ref-sugestoes");
  $("ref-busca").addEventListener("input", async () => {
    const texto = $("ref-busca").value.trim();
    if (texto.length < 2) { caixa.classList.add("oculto"); return; }
    const achados = await api.municipios(texto, uf.value || null);
    caixa.innerHTML = achados.map(m =>
      `<button data-c="${m.c}" data-n="${esc(m.n)}" data-uf="${m.uf}">
         ${esc(m.n)} — ${m.uf}</button>`).join("")
      || `<button disabled>nenhum município encontrado</button>`;
    caixa.classList.remove("oculto");
    caixa.querySelectorAll("button[data-c]").forEach(b =>
      b.addEventListener("click", async () => {
        caixa.classList.add("oculto");
        $("ref-busca").value = "";
        if (!await confirmarVolume(b.dataset.c, b.dataset.n)) return;
        const r = await api.adicionar_municipio_referencia(
          b.dataset.c, b.dataset.n, b.dataset.uf);
        if (r && r.ok === false) { alert(r.erro); return; }
        await renderReferencia();
        // os preços só chegam na próxima coleta: dizer isso evita a
        // impressão de que o município entrou vazio
        $("sync-msg").textContent =
          `${b.dataset.n} adicionado — os preços chegam na próxima sincronização`;
      }));
  });
}
ligarBuscaReferencia();

// ── config ────────────────────────────────────────────────────────────────
$("btn-config").addEventListener("click", async () => {
  const e = await api.get_estado();
  $("cfg-municipio").innerHTML = `${esc(e.municipio)} — ${esc(e.uf)}
    <small class="dim">(IBGE ${esc(e.ibge)})</small>`;
  const brasao = await api.brasao();
  mostrarBrasao(brasao.dataurl);
  const orgaos = await api.listar_orgaos();
  $("cfg-orgaos").innerHTML = orgaos.map(o =>
    `<div class="orgrow"><span>${esc(o.razao_social ?? o.cnpj)}
       <small>${esc(o.cnpj)} · ${o.origem === "manual" ? "adicionado manualmente"
         : "descoberto automaticamente"}</small></span>
     <input type="checkbox" data-cnpj="${esc(o.cnpj)}" ${o.ativo ? "checked" : ""}
       aria-label="Monitorar ${esc(o.razao_social ?? o.cnpj)}"></div>`)
    .join("") || `<div class="dim">Nenhum órgão ainda — sincronize primeiro.</div>`;
  $("cfg-orgaos").querySelectorAll("input[data-cnpj]").forEach(c =>
    c.addEventListener("change", () =>
      api.set_orgao_ativo(c.dataset.cnpj, c.checked)));
  await renderReferencia();
  aplicarLimCompras(parseFloat(e.limite_dispensa_compras) || 0);
  aplicarLimObras(parseFloat(e.limite_dispensa_obras) || 0);
  const log = await api.ultimo_log();
  $("cfg-log").innerHTML = log.map(l =>
    `<div class="logline">${esc(l.iniciado_em?.slice(0,16).replace("T"," "))} ·
     ${esc(l.tipo)} · ${l.status === "ok" ? `${l.registros} registros`
       : `<span style="color:var(--warn)">erro: ${esc(l.erro)}</span>`}</div>`)
    .join("") || `<div class="dim">Nenhuma sincronização ainda.</div>`;
  abrirModal("veu-config");
});
function mostrarBrasao(dataurl) {
  const preview = $("cfg-brasao-preview");
  preview.src = dataurl || "";
  preview.classList.toggle("oculto", !dataurl);
  $("btn-brasao-remover").classList.toggle("oculto", !dataurl);
}
$("btn-brasao-carregar").addEventListener("click", async () => {
  const botao = $("btn-brasao-carregar");
  botao.disabled = true;
  $("brasao-status").textContent = "";
  const r = await api.carregar_brasao();
  botao.disabled = false;
  if (r.ok) mostrarBrasao((await api.brasao()).dataurl);
  else if (r.erro) $("brasao-status").textContent = r.erro;
});
$("btn-brasao-remover").addEventListener("click", async () => {
  await api.remover_brasao();
  mostrarBrasao(null);
  $("brasao-status").textContent = "";
});
// máscara de dinheiro: digita só dígitos, exibe R$ formatado,
// salva o valor numérico puro (dataset.valor)
function mascaraDinheiro(input, aoSalvar) {
  const aplicar = v => {
    input.value = brl.format(v);
    input.dataset.valor = v;
  };
  input.addEventListener("input", () => {
    const digitos = input.value.replace(/\D/g, "");
    aplicar((parseInt(digitos || "0", 10)) / 100);
  });
  input.addEventListener("change", () => aoSalvar(input.dataset.valor));
  return aplicar;
}
const aplicarLimCompras = mascaraDinheiro($("cfg-lim-compras"),
  v => api.set_config("limite_dispensa_compras", v));
const aplicarLimObras = mascaraDinheiro($("cfg-lim-obras"),
  v => api.set_config("limite_dispensa_obras", v));
$("btn-trocar").addEventListener("click", () => {
  fecharModal("veu-config");
  iniciarWizard();
});
$("btn-add-orgao").addEventListener("click", async () => {
  const r = await api.add_orgao($("novo-cnpj").value, $("novo-nome").value);
  if (r.ok) { $("novo-cnpj").value = ""; $("novo-nome").value = "";
    $("btn-config").click(); }
  else if (r.erro) alert(r.erro);
});

// ── modais: trava o fundo, move o foco e prende o Tab ─────────────────────
const FOCAVEIS = 'button:not([disabled]), input, select, textarea, a[href],' +
                 ' summary, [tabindex]:not([tabindex="-1"])';
let focoAnterior = null;

function abrirModal(id) {
  focoAnterior = document.activeElement;
  const veu = $(id);
  veu.classList.remove("oculto");
  document.body.classList.add("travado");
  veu.querySelector(FOCAVEIS)?.focus();
}

function fecharModal(id) {
  $(id).classList.add("oculto");
  if (!document.querySelector(".veu:not(.oculto)"))
    document.body.classList.remove("travado");
  focoAnterior?.focus();
}

function fecharTodosModais() {
  document.querySelectorAll(".veu:not(.oculto)")
    .forEach(v => v.classList.add("oculto"));
  document.body.classList.remove("travado");
  focoAnterior?.focus();
}

document.querySelectorAll("[data-fecha]").forEach(b =>
  b.addEventListener("click", () => fecharModal(b.dataset.fecha)));

document.addEventListener("keydown", e => {
  if (e.key === "Escape") { fecharTodosModais(); return; }
  if (e.key !== "Tab") return;
  const veu = document.querySelector(".veu:not(.oculto)");
  if (!veu) return;
  const itens = [...veu.querySelectorAll(FOCAVEIS)]
    .filter(el => el.offsetParent !== null);
  if (!itens.length) return;
  const primeiro = itens[0], ultimo = itens[itens.length - 1];
  if (e.shiftKey && document.activeElement === primeiro) {
    e.preventDefault(); ultimo.focus();
  } else if (!e.shiftKey && document.activeElement === ultimo) {
    e.preventDefault(); primeiro.focus();
  }
});

// ── sincronização ─────────────────────────────────────────────────────────
$("btn-sync").addEventListener("click", () => api.sincronizar());
window.onSyncProgresso = st => {
  $("sync-dot").classList.toggle("rodando", st.rodando);
  if (st.rodando && st.msg) $("sync-msg").textContent = st.msg;
  $("btn-sync").disabled = st.rodando;
};
window.onSyncFim = async st => {
  $("sync-dot").classList.remove("rodando");
  $("btn-sync").disabled = false;
  if (st.erro) { $("sync-msg").textContent = `Falha na sincronização: ${st.erro}`; }
  else {
    const r = st.resumo || {};
    const partes = Object.entries(r).map(([t, n]) =>
      n == null ? `${t}: falhou` : `${t}: ${n}`);
    $("sync-msg").textContent =
      `Sincronizado ${new Date().toLocaleTimeString("pt-BR",
        {hour:"2-digit",minute:"2-digit"})} · ` + partes.join(" · ");
  }
  const e = await api.get_estado();
  renderKpis(e.kpis);
  await carregarFiltros();
  await carregarLista();
};

// ── exportação ────────────────────────────────────────────────────────────
$("btn-csv").addEventListener("click", async () => {
  const r = await api.exportar_csv(estado.tipo, filtrosAtuais());
  if (r.ok) $("sync-msg").textContent =
    `CSV exportado: ${r.linhas} linhas em ${r.arquivo}`;
  else if (r.erro) alert(r.erro);
});
