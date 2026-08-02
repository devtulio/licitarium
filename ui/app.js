// Interface do Licitarium: fala com o Python pela ponte pywebview
// (window.pywebview.api), montada em licitarium.py:Api.
"use strict";
const $ = id => document.getElementById(id);
const esc = s => String(s ?? "").replace(/[&<>"']/g,
  c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const brl = new Intl.NumberFormat("pt-BR", {style:"currency", currency:"BRL"});
const dinheiro = v => v == null ? "–" : brl.format(v);
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

const estado = { tipo:"contratacoes", pagina:1, total:0, municipio:null,
                 ord:null, dir:"desc" };
// há município de referência? decide se a aba Preços mostra a origem
let temReferencia = false;
// itens que o usuário tirou da pesquisa de preços. Guarda os DESCARTADOS
// (e não os escolhidos) para que item novo, vindo de uma sincronização ou
// de outra página, entre marcado por padrão.
let precosDescartados = new Set();
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

// ── boot ──────────────────────────────────────────────────────────────────
window.addEventListener("pywebviewready", async () => {
  api = window.pywebview.api;
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
  if (trocando) await api.trocar_municipio(wizEscolha.c, wizEscolha.n, wizEscolha.uf);
  else await api.configurar_municipio(wizEscolha.c, wizEscolha.n, wizEscolha.uf);
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
  await carregarLista();
  esconderSplash();
  api.sincronizar();  // sync ao abrir (catch-up incremental)
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
  if (k.vencendo_60 > 0)
    alertas.push(`<button class="chip" id="chip-vencendo">⚠ ${k.vencendo_60}
      contrato(s)/ata(s) vencem nos próximos 60 dias</button>`);
  if (k.propostas_abertas > 0)
    alertas.push(`<button class="chip info" id="chip-propostas">⏱
      ${k.propostas_abertas} processo(s) com propostas abertas</button>`);
  $("alertas").innerHTML = alertas.join("");
  $("alertas").classList.toggle("oculto", alertas.length === 0);
  $("chip-vencendo")?.addEventListener("click",
    () => irPara("contratos", {vigentes: true, ord: "vigencia", dir: "asc"}));
  $("chip-propostas")?.addEventListener("click",
    () => irPara("contratacoes", {propostas: true}));
}

async function carregarFiltros() {
  const f = await api.filtros_disponiveis();
  const preencher = (sel, itens, rotulo) => {
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
}

function filtrosAtuais() {
  return { ano: $("f-ano").value || null,
           modalidade: $("f-modalidade").value || null,
           situacao: $("f-situacao").value || null,
           orgao: $("f-orgao").value || null,
           propostas: $("f-propostas").checked || null,
           vigentes: $("f-vigentes").checked || null,
           so_homologados: $("f-homologados").checked || null,
           origem: $("f-so-meu").checked ? "proprio" : null,
           busca: $("f-busca").value.trim() || null,
           ord: estado.ord, dir: estado.dir };
}

// [rótulo, chave de ordenação na whitelist do backend — null = não ordenável]
const CAMPOS_FILTRO = ["f-ano", "f-modalidade", "f-situacao", "f-orgao",
                       "f-busca"];
const CAIXAS_FILTRO = ["f-propostas", "f-vigentes"];  // f-homologados é
// padrão ligado na aba Preços, então não conta como "filtro ativo"

function temFiltroAtivo() {
  return CAMPOS_FILTRO.some(id => $(id).value)
      || CAIXAS_FILTRO.some(id => $(id).checked);
}

function limparFiltros() {
  CAMPOS_FILTRO.forEach(id => $(id).value = "");
  CAIXAS_FILTRO.forEach(id => $(id).checked = false);
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
                 ["Qtde",null], ["Valor unitário","unitario"],
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
      <span><span class="obj">${esc(d.objeto ?? "–")}</span><br>
        <span class="dim">${esc(d.fornecedor_nome ?? "")}</span></span>
      <span class="dim vig">${dataBr(d.vigencia_inicio)} – ${dataBr(d.vigencia_fim)}${badgeVigencia(d)}</span>
      <span class="num">${dinheiro(d.valor_global)}</span>`;
  if (tipo === "itens") {
    const homologado = d.valor_unitario_homologado != null;
    const unit = homologado
      ? dinheiro(d.valor_unitario_homologado)
      : `<span class="est" title="Sem resultado homologado: valor de referência
          do edital">${dinheiro(d.valor_unitario_estimado)} <small>est.</small></span>`;
    return `<span class="sel"><input type="checkbox" data-item="${esc(d.id)}"
        ${precosDescartados.has(String(d.id)) ? "" : "checked"}
        aria-label="Usar este preço na pesquisa"></span>
      <span class="obj">${esc(d.descricao ?? "–")}</span>
      <span class="dim">${esc(d.unidade ?? "–")}</span>
      <span class="dim">${d.quantidade_homologada ?? d.quantidade ?? "–"}</span>
      <span class="num">${unit}</span>
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

let ultimoTermoPrecos = null;

async function mostrarResumoPrecos() {
  const caixa = $("precos-resumo");
  const termo = $("f-busca").value.trim();
  // o descarte vale para a pesquisa em curso; trocar o termo recomeça
  if (termo !== ultimoTermoPrecos) {
    ultimoTermoPrecos = termo;
    if (precosDescartados.size) {
      precosDescartados.clear();
      atualizarSelecaoPrecos();
    }
  }
  if (estado.tipo !== "itens" || termo.length < 3 || !api.estatisticas_preco) {
    caixa.classList.add("oculto");
    return;
  }
  const s = await api.estatisticas_preco(termo,
    $("f-ano").value ? +$("f-ano").value : null,
    $("f-so-meu").checked ? "proprio" : null,
    [...precosDescartados]);
  if (!s) { caixa.classList.add("oculto"); return; }
  const cel = (v, r, destaque) =>
    `<div class="cel${destaque ? " destaque" : ""}">
       <div class="v">${v}</div><div class="r">${r}</div></div>`;
  // quem decide precisa saber quanto do resultado é da própria série
  const origem = s.referencia
    ? ` <small class="dim">— ${s.proprios} do seu município e ${s.referencia} de referência</small>`
    : "";
  caixa.innerHTML = `<h3>Preços pagos para "${esc(termo)}"${origem}</h3>
    <div class="grade">
      ${cel(dinheiro(s.minimo), "menor unitário")}
      ${cel(dinheiro(s.mediana), "mediana", true)}
      ${cel(dinheiro(s.media), "média")}
      ${cel(dinheiro(s.maximo), "maior unitário")}
      ${cel(s.n, "itens homologados")}
      ${cel(s.fornecedores, "fornecedores")}
      <button class="btn ghost" id="btn-rel-precos" style="align-self:center">
        Relatório de pesquisa de preços</button>
    </div>`;
  caixa.classList.remove("oculto");
  $("btn-rel-precos").addEventListener("click", abrirRelatorioPrecos);
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

function aplicarLarguras(tipo) {
  const lista = $("lista");
  const mapa = larguras[tipo];
  if (!mapa) { lista.style.removeProperty("--cols"); return; }
  const flex = COL_FLEX[tipo];
  const n = COLUNAS[tipo].length;
  // larguras guardadas antes de a aba ganhar (ou perder) uma coluna não
  // servem: faltando uma, o grid receberia "NaNpx" e quebraria a lista
  for (let i = 0; i < n; i++)
    if (i !== flex && !(mapa[i] > 0)) {
      delete larguras[tipo];
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
  larguras[tipo] = {};
  px.forEach((v, i) => { if (i !== flex) larguras[tipo][i] = v; });
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
    if (i === flex || i === COLUNAS[tipo].length - 1) return;  // última não
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
  mostrarResumoPrecos();
  const r = await api.listar(estado.tipo, filtrosAtuais(), estado.pagina);
  estado.total = r.total;
  const g = `g-${estado.tipo}`;
  const cab = `<div class="linha cab ${g}">` +
    COLUNAS[estado.tipo].map(([rotulo, chave]) => {
      const ativa = chave && estado.ord === chave;
      const seta = ativa ? `<span class="seta">${estado.dir === "asc" ? "▲" : "▼"}</span>` : "";
      const sort = chave ? ` data-ord="${chave}" role="button" tabindex="0"
        aria-sort="${ativa ? (estado.dir === "asc" ? "ascending" : "descending") : "none"}"` : "";
      return `<span${sort}>${rotulo} ${seta}</span>`;
    }).join("") + `</div>`;
  const selecionavel = estado.tipo === "itens";
  const linhas = r.itens.map(d => {
    const nc = esc(d.numero_controle ?? d.id);
    return selecionavel
      ? `<div class="linha ${g}" data-nc="${nc}" role="button" tabindex="0">`
        + renderLinha(estado.tipo, d) + `</div>`
      : `<button class="linha ${g}" data-nc="${nc}">`
        + renderLinha(estado.tipo, d) + `</button>`;
  }).join("");
  const comFiltro = temFiltroAtivo();
  $("btn-limpar").classList.toggle("oculto", !comFiltro);
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
    c.addEventListener("change", () => {
      const id = String(c.dataset.item);
      if (c.checked) precosDescartados.delete(id);
      else precosDescartados.add(id);
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

document.querySelectorAll("nav.abas button").forEach(b =>
  b.addEventListener("click", () => {
    document.querySelectorAll("nav.abas button").forEach(x =>
      x.classList.toggle("on", x === b));
    estado.tipo = b.dataset.tipo;
    estado.pagina = 1;
    estado.ord = null; estado.dir = "desc";
    const soContratacoes = estado.tipo === "contratacoes";
    $("f-modalidade").classList.toggle("oculto", !soContratacoes);
    $("f-situacao").classList.toggle("oculto", !soContratacoes);
    $("cx-propostas").classList.toggle("oculto", !soContratacoes);
    $("cx-vigentes").classList.toggle("oculto",
      !["contratos", "atas"].includes(estado.tipo));
    const ehItens = estado.tipo === "itens";
    $("cx-homologados").classList.toggle("oculto", !ehItens);
    // o filtro de origem só faz sentido havendo município de referência
    $("cx-so-meu").classList.toggle("oculto", !ehItens || !temReferencia);
    $("f-busca").placeholder = ehItens
      ? "Buscar item — ex.: papel A4, óleo, pneu…"
      : "Buscar no objeto…";
    $("f-propostas").checked = false;
    $("f-vigentes").checked = false;
    carregarLista();
  }));
["f-propostas", "f-vigentes", "f-homologados", "f-so-meu"].forEach(id =>
  $(id).addEventListener("change", () => { estado.pagina = 1; carregarLista(); }));

// navegação programática (KPIs e alertas)
function irPara(tipo, ajustes = {}) {
  document.querySelector(`nav.abas button[data-tipo="${tipo}"]`).click();
  if (ajustes.ano !== undefined) $("f-ano").value = ajustes.ano ?? "";
  if (ajustes.vigentes) $("f-vigentes").checked = true;
  if (ajustes.propostas) $("f-propostas").checked = true;
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
  unidade:"Unidade", valor_estimado:"Valor estimado",
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
    params.excluidos = [...precosDescartados];
  if ($("rel-tipo").value === "precos" && !params.termo) {
    $("rel-status").textContent = "Informe o que pesquisar";
    $("rel-termo").focus();
    return;
  }
  $("rel-gerar").disabled = true;
  $("rel-status").textContent = "Gerando…";
  const r = await api.gerar_relatorio($("rel-tipo").value, params);
  $("rel-gerar").disabled = false;
  $("rel-status").textContent = r.ok
    ? "Aberto no navegador" + (r.csv ? " · CSV gerado ao lado" : "")
    : (r.erro || "Falha ao gerar");
});

// ── municípios de referência (banco de preços) ────────────────────────────
async function renderReferencia() {
  const lista = await api.listar_municipios_referencia();
  // mesmo formato dos órgãos monitorados logo acima: nome, identificação
  // embaixo e o controle à direita
  $("cfg-referencia").innerHTML = lista.map(m =>
    `<div class="orgrow"><span>${esc(m.nome)} — ${esc(m.uf)}
       <small>IBGE ${esc(m.ibge)} · ${m.itens
         ? `${m.itens.toLocaleString("pt-BR")} ${m.itens === 1 ? "preço" : "preços"} no banco`
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
      await api.remover_municipio_referencia(b.dataset.remover);
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

function atualizarSelecaoPrecos() {
  const caixa = $("precos-selecao");
  if (!caixa) return;
  const n = precosDescartados.size;
  caixa.classList.toggle("oculto", n === 0);
  if (n) caixa.innerHTML =
    `${n} ${n === 1 ? "item descartado" : "itens descartados"} desta pesquisa —
     não entram no resumo nem no relatório.
     <button class="btn ghost" id="precos-restaurar">Restaurar todos</button>`;
  $("precos-restaurar")?.addEventListener("click", () => {
    precosDescartados.clear();
    carregarLista();
    atualizarSelecaoPrecos();
  });
}

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
