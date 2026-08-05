// ══ Painel: gráficos do acervo, desenhados aqui mesmo ══════════════════════
// SVG escrito à mão, sem biblioteca: o programa roda offline dentro de um exe,
// e uma dependência de gráfico custaria mais que estas funções. As mesmas
// marcas vão para a tela e para a impressão em A3 — uma fonte de desenho só.
//
// Convenções que valem para todos os gráficos daqui (design/DASHBOARD.md):
//   · um eixo só, nunca dois; escala sempre a partir do zero;
//   · cor nunca sozinha — toda série tem rótulo direto ou legenda;
//   · <title> em cada marca, que o navegador mostra ao passar o mouse;
//   · o que não tem dado aparece como "–", nunca como zero inventado.

const P = {                      // estado do painel
  vista: "execucao",
  dados: null,
};

const esconde = (v) => v == null || Number.isNaN(v);
const compacto = (v) => esconde(v) ? "–"
  : Math.abs(v) >= 1e6 ? `R$ ${(v / 1e6).toFixed(1).replace(".", ",")} mi`
  : Math.abs(v) >= 1e3 ? `R$ ${(v / 1e3).toFixed(0)} mil`
  : dinheiro(v);
const pct = (v, casas = 1) => esconde(v) ? "–"
  : `${v.toFixed(casas).replace(".", ",")}%`;
const MES = ["jan", "fev", "mar", "abr", "mai", "jun",
             "jul", "ago", "set", "out", "nov", "dez"];

// Escala com números que se leem: o passo é 1, 2, 2,5 ou 5 vezes uma
// potência de dez, e o topo é um múltiplo inteiro do passo. Sem isso o eixo
// sai com marcas em "1,7 mi" e "3,3 mi", que ninguém compara de cabeça.
function escala(maximo) {
  if (!(maximo > 0)) return { topo: 1, passo: 0.25 };
  const p = Math.pow(10, Math.floor(Math.log10(maximo / 3)));
  for (const m of [1, 2, 2.5, 5, 10]) {
    const passo = m * p;
    if (maximo / passo <= 4.2)
      return { topo: Math.ceil(maximo / passo) * passo, passo };
  }
  return { topo: maximo, passo: maximo / 4 };
}

function svg(largura, altura, dentro) {
  return `<svg viewBox="0 0 ${largura} ${altura}" width="100%"
    height="${altura}" role="img" preserveAspectRatio="xMidYMid meet"
    >${dentro}</svg>`;
}

// ── colunas pareadas: estimado (claro) × homologado (cheio) ────────────────
function grafMeses(meses) {
  const dados = meses.filter(m => m.valor || m.estimado);
  if (!dados.length) return `<div class="vazio">Sem contratações no exercício.</div>`;
  const alto = 170, base = 170, larg = 660;
  const e = escala(Math.max(...dados.map(m => Math.max(m.valor, m.estimado))));
  const passo = (larg - 60) / dados.length;
  const y = (v) => base - (v / e.topo) * (base - 30);
  let g = "";
  for (let v = 0; v <= e.topo + 1e-6; v += e.passo) {
    g += `<line class="eixo" x1="48" y1="${y(v)}" x2="${larg - 8}" y2="${y(v)}"
           opacity="${v ? .55 : 1}"/>
      <text class="rot" x="44" y="${y(v) + 4}" text-anchor="end"
        >${v ? compacto(v).replace("R$ ", "") : "0"}</text>`;
  }
  dados.forEach((m, i) => {
    const x = 56 + i * passo, w = Math.min(22, passo / 2.6);
    const he = Math.max(2, base - y(m.estimado)), hh = Math.max(2, base - y(m.valor));
    g += `<rect x="${x}" y="${y(m.estimado)}" width="${w}" height="${he}" rx="4"
            fill="var(--s1)" opacity=".32"><title>${MES[m.mes - 1]} · estimado ${
              compacto(m.estimado)}</title></rect>
          <rect x="${x + w + 2}" y="${y(m.valor)}" width="${w}" height="${hh}" rx="4"
            fill="var(--s1)"><title>${MES[m.mes - 1]} · homologado ${
              compacto(m.valor)} · ${m.n} ${m.n === 1 ? "processo" : "processos"
            }</title></rect>
          <text class="rot" x="${x + w + 1}" y="${base + 16}" text-anchor="middle"
            >${MES[m.mes - 1]}</text>`;
  });
  return svg(larg, alto + 26, g) + `<div class="leg">
    <span><i style="background:var(--s1);opacity:.32"></i>Estimado</span>
    <span><i style="background:var(--s1)"></i>Homologado</span></div>`;
}

// ── barras horizontais, uma série, rótulo direto ──────────────────────────
function grafBarras(itens, {valor, rotulo, sub, cor = "var(--s1)"}) {
  if (!itens.length) return `<div class="vazio">Sem dados no exercício.</div>`;
  const max = Math.max(...itens.map(valor)) || 1;
  const linha = 40, larg = 360;
  let g = "";
  itens.forEach((it, i) => {
    const y = i * linha + 18, w = Math.max(3, (valor(it) / max) * (larg - 110));
    g += `<text class="rot" x="0" y="${y - 6}">${esc(rotulo(it))}${
            sub ? ` · ${esc(sub(it))}` : ""}</text>
          <rect x="0" y="${y}" width="${w}" height="17" rx="4" fill="${cor}"
            ><title>${esc(rotulo(it))} · ${compacto(valor(it))}</title></rect>
          <text class="val" x="${w + 8}" y="${y + 14}">${compacto(valor(it))}</text>`;
  });
  return svg(larg, itens.length * linha + 6, g);
}

// ── linhas do acumulado: ano corrente em destaque, anteriores em contexto ──
function grafSeries(series, anoAtual) {
  const anos = Object.keys(series).sort();
  const todos = anos.flatMap(a => series[a]);
  if (!todos.some(v => v)) return `<div class="vazio">Sem histórico para comparar.</div>`;
  // 90px à direita ficam para os rótulos dos anos: fora da área do plot,
  // dentro do viewBox — senão o texto sai cortado na borda
  const larg = 1000, base = 170, e = escala(Math.max(...todos));
  const x = (i) => 56 + i * ((larg - 150) / 11);
  const y = (v) => base - (v / e.topo) * (base - 26);
  let g = "";
  for (let v = 0; v <= e.topo + 1e-6; v += e.passo) {
    g += `<line class="eixo" x1="52" y1="${y(v)}" x2="${larg - 20}" y2="${y(v)}"
            opacity="${v ? .55 : 1}"/>
          <text class="rot" x="48" y="${y(v) + 4}" text-anchor="end"
            >${v ? compacto(v).replace("R$ ", "") : "0"}</text>`;
  }
  [0, 2, 4, 6, 8, 10].forEach(i =>
    g += `<text class="rot" x="${x(i)}" y="${base + 18}" text-anchor="middle"
           >${MES[i]}</text>`);
  anos.forEach((ano, k) => {
    const atual = ano === String(anoAtual);
    // o ano em curso só tem pontos até o mês corrente; os outros, o ano todo
    const pontos = series[ano]
      .map((v, i) => (atual && i > new Date().getMonth()) ? null : `${x(i)},${y(v)}`)
      .filter(Boolean).join(" ");
    g += `<polyline fill="none" points="${pontos}"
            stroke="${atual ? "var(--s1)" : "var(--muted)"}"
            stroke-width="${atual ? 2.5 : 2}"
            opacity="${atual ? 1 : (0.4 + k * 0.18)}"/>`;
    const ultimo = atual ? Math.min(new Date().getMonth(), 11) : 11;
    if (atual) {
      g += `<circle cx="${x(ultimo)}" cy="${y(series[ano][ultimo])}" r="4"
              fill="var(--s1)" stroke="var(--surface)" stroke-width="2"/>
            <text class="val" x="${x(ultimo) + 10}" y="${y(series[ano][ultimo]) - 2}"
              fill="var(--s1)" font-weight="600">${ano} · ${
                compacto(series[ano][ultimo])}</text>`;
    } else {
      g += `<text class="rot" x="${x(11) + 10}" y="${y(series[ano][11]) + 4}"
              >${ano}</text>`;
    }
  });
  return svg(larg, base + 30, g);
}

// ── deságio: economia à direita, estouro à esquerda do zero ───────────────
function grafDesagio(desagios) {
  if (!desagios.length)
    return `<div class="vazio">Nenhuma contratação com valor estimado e
            homologado no exercício.</div>`;
  const larg = 500, linha = 37, meio = 250;
  const max = Math.max(20, ...desagios.map(d => Math.abs(d.pct)));
  let g = `<line x1="${meio}" y1="10" x2="${meio}" y2="${desagios.length * linha + 6}"
             class="eixo"/>`;
  desagios.forEach((d, i) => {
    const y = i * linha + 14;
    const w = Math.max(3, (Math.abs(d.pct) / max) * (meio - 120));
    const economia = d.pct >= 0;
    g += `<rect x="${economia ? meio : meio - w}" y="${y}" width="${w}" height="17"
            rx="4" fill="${economia ? "var(--s3)" : "var(--s2)"}"
            ><title>${esc(d.modalidade)} · ${pct(d.pct)} ${
              economia ? "de deságio" : "acima do estimado"} · ${d.n} ${
              d.n === 1 ? "processo" : "processos"}</title></rect>
          <text class="val" x="${economia ? meio + w + 8 : meio - w - 8}"
            y="${y + 14}" text-anchor="${economia ? "start" : "end"}"
            >${pct(d.pct)}</text>
          <text class="rot" x="${economia ? meio - 8 : meio - w - 52}" y="${y + 14}"
            text-anchor="end">${esc(d.modalidade)}</text>`;
  });
  g += `<text class="rot" x="${meio}" y="${desagios.length * linha + 22}"
          text-anchor="middle">0%</text>
        <text class="rot" x="${meio - 110}" y="${desagios.length * linha + 22}"
          text-anchor="middle">acima do estimado</text>
        <text class="rot" x="${meio + 110}" y="${desagios.length * linha + 22}"
          text-anchor="middle">economia</text>`;
  return svg(larg, desagios.length * linha + 30, g);
}

// ── concentração: curva do valor acumulado por fornecedor ─────────────────
function grafConcentracao(curva, total) {
  if (curva.length < 3)
    return `<div class="vazio">Poucos fornecedores para medir concentração.</div>`;
  const larg = 500, alto = 190, x0 = 40, y0 = 160;
  const px = (i) => x0 + (i / (curva.length - 1)) * (larg - 60);
  const py = (v) => y0 - (v / 100) * (y0 - 20);
  const pontos = curva.map((v, i) => `${px(i)},${py(v)}`).join(" ");
  const dez = Math.min(9, curva.length - 1);
  const aDireita = px(dez) < larg - 220;
  return svg(larg, alto, `
    <line class="eixo" x1="${x0}" y1="${y0}" x2="${larg - 20}" y2="${y0}"/>
    <line class="eixo" x1="${x0}" y1="20" x2="${x0}" y2="${y0}"/>
    <polyline fill="none" points="${px(0)},${y0} ${px(curva.length - 1)},${py(100)}"
      stroke="var(--muted)" stroke-width="1.5" stroke-dasharray="4 4" opacity=".6"/>
    <polyline fill="none" points="${px(0)},${y0} ${pontos}" stroke="var(--s1)"
      stroke-width="2.5"/>
    <circle cx="${px(dez)}" cy="${py(curva[dez])}" r="4" fill="var(--s1)"
      stroke="var(--surface)" stroke-width="2"/>
    <text class="val" x="${px(dez) + (aDireita ? 10 : -10)}"
      y="${py(curva[dez]) + (aDireita ? -2 : 16)}"
      text-anchor="${aDireita ? "start" : "end"}"
      >${dez + 1} ${dez ? "fornecedores" : "fornecedor"} = ${
        pct(curva[dez], 0)} do valor</text>
    <text class="rot" x="${x0}" y="${y0 + 16}">1</text>
    <text class="rot" x="${larg - 24}" y="${y0 + 16}" text-anchor="end">${total}</text>
    <text class="rot" x="${larg / 2}" y="${y0 + 16}" text-anchor="middle"
      >fornecedores, do maior para o menor</text>`);
}

// ── calor: processos por mês e modalidade, rampa de uma cor só ────────────
function grafCalor(calor, meses) {
  const linhas = Object.entries(calor);
  const todos = linhas.flatMap(([, v]) => v);
  if (!todos.some(v => v)) return `<div class="vazio">Sem processos no exercício.</div>`;
  const max = Math.max(...todos);
  const larg = 1000, cel = 70, alt = 24;
  const passo = Math.min(cel, (larg - 180) / meses.length - 4);
  let g = "";
  linhas.forEach(([nome, valores], i) => {
    const y = 22 + i * 34;
    g += `<text class="rot" x="150" y="${y + 16}" text-anchor="end">${esc(nome)}</text>`;
    valores.forEach((v, m) => {
      const nivel = !v ? 1 : Math.min(5, 1 + Math.ceil((v / max) * 4));
      g += `<rect x="${160 + m * (passo + 4)}" y="${y}" width="${passo}"
              height="${alt}" rx="3" fill="var(--seq${nivel})"
              ><title>${MES[m]} · ${esc(nome)} · ${v} ${
                v === 1 ? "processo" : "processos"}</title></rect>`;
    });
  });
  meses.forEach((m, i) =>
    g += `<text class="rot" x="${160 + i * (passo + 4) + passo / 2}"
            y="${28 + linhas.length * 34}" text-anchor="middle">${MES[m - 1]}</text>`);
  // legenda embaixo, alinhada à direita: em cima ela disputava espaço com a
  // última coluna de meses e saía cortada
  const ly = 42 + linhas.length * 34, lx = larg - 250;
  g += `<text class="rot" x="${lx - 6}" y="${ly + 11}" text-anchor="end">menos</text>`;
  for (let n = 1; n <= 5; n++)
    g += `<rect x="${lx + (n - 1) * 28}" y="${ly}" width="26" height="14" rx="2"
            fill="var(--seq${n})"/>`;
  g += `<text class="rot" x="${lx + 146}" y="${ly + 11}">mais processos</text>`;
  return svg(larg, ly + 22, g);
}

// ── medidores do limite anual de dispensa ─────────────────────────────────
function grafLimites(unidades, limite) {
  if (!unidades.length)
    return `<div class="vazio">Nenhuma dispensa registrada no exercício.</div>`;
  const larg = 500, bloco = 66;
  let g = "";
  unidades.forEach((u, i) => {
    const y = i * bloco + 16;
    const w = Math.min(1, (u.pct || 0) / 100) * (larg - 60);
    const cor = u.pct >= 90 ? "var(--erro)" : u.pct >= 75 ? "var(--warn)"
                                                          : "var(--s3)";
    g += `<text class="rot" x="0" y="${y - 4}">${esc(u.unidade)} · ${u.n} ${
            u.n === 1 ? "dispensa" : "dispensas"}</text>
          <rect x="0" y="${y}" width="${larg - 60}" height="14" rx="4"
            fill="var(--surface2)"/>
          <rect x="0" y="${y}" width="${Math.max(3, w)}" height="14" rx="4"
            fill="${cor}"><title>${esc(u.unidade)} · ${dinheiro(u.total)} de ${
              dinheiro(limite)}</title></rect>
          <text class="val" x="0" y="${y + 30}">${dinheiro(u.total)} · <tspan
            fill="${cor}" font-weight="600">${pct(u.pct, 0)} do limite</tspan></text>`;
  });
  return svg(larg, unidades.length * bloco + 6, g);
}

// ── funil: onde os processos do exercício pararam ─────────────────────────
function grafFunil(f) {
  const etapas = [["Publicadas", f.publicadas], ["Com resultado", f.com_resultado],
                  ["Com contrato", f.com_contrato], ["Vigentes hoje", f.vigentes]];
  const max = etapas[0][1] || 1;
  const larg = 500;
  let g = "";
  etapas.forEach(([nome, v], i) => {
    const y = i * 40 + 14, w = Math.max(6, (v / max) * (larg - 70));
    g += `<rect x="0" y="${y}" width="${w}" height="26" rx="4" fill="var(--s1)"
            opacity="${0.85 - i * 0.15}"><title>${nome}: ${v}</title></rect>
          <text class="val" x="${w + 10}" y="${y + 18}">${v}</text>
          <text class="val" x="10" y="${y + 18}"
            fill="${i < 2 ? "var(--accent-fg)" : "var(--text)"}">${nome}</text>`;
  });
  return svg(larg, etapas.length * 40 + 10, g);
}

// ── agenda dos próximos 90 dias ───────────────────────────────────────────
// Vencimentos se amontoam: numa prefeitura pequena, meia dúzia de contratos
// termina no mesmo dia. Por isso a marca é o DIA, não o contrato — o tamanho
// dela conta quantos, e o rótulo nomeia o primeiro.
function grafAgenda(itens) {
  if (!itens.length)
    return `<div class="vazio">Nada vence nos próximos 90 dias.</div>`;
  const porDia = new Map();
  itens.forEach(it => {
    const d = Math.max(0, Math.min(90, it.dias ?? 0));
    (porDia.get(d) ?? porDia.set(d, []).get(d)).push(it);
  });
  const dias = [...porDia.keys()].sort((a, b) => a - b);
  const larg = 1000, y = 74;
  const x = (d) => 40 + d / 90 * (larg - 80);
  let g = `<line x1="40" y1="${y}" x2="${larg - 40}" y2="${y}" class="eixo"
             stroke-width="2"/>`;
  [0, 30, 60, 90].forEach(d =>
    g += `<text class="rot" x="${x(d)}" y="${y + 30}" text-anchor="middle"
           >${d ? `+${d} dias` : "hoje"}</text>`);
  let ultimoRotulo = -999;
  dias.forEach(d => {
    const grupo = porDia.get(d);
    const cor = d <= 15 ? "var(--erro)" : d <= 60 ? "var(--warn)" : "var(--s3)";
    const raio = Math.min(11, 6 + grupo.length);
    const lista = grupo.map(i => `${i.tipo}: ${i.nome ?? "–"}`).join(" · ");
    g += `<circle cx="${x(d)}" cy="${y}" r="${raio}" fill="${cor}"
            ><title>${esc(lista)} — vence${grupo.length > 1 ? "m" : ""} em ${d}
             ${d === 1 ? "dia" : "dias"} (${dataBr(grupo[0].vigencia_fim)})</title>
          </circle>`;
    if (grupo.length > 1)
      g += `<text class="val" x="${x(d)}" y="${y + 4}" text-anchor="middle"
              fill="var(--accent-fg)" font-weight="600">${grupo.length}</text>`;
    // um rótulo por vizinhança: sem isso os nomes se sobrepõem e nenhum se lê
    if (x(d) - ultimoRotulo > 120) {
      ultimoRotulo = x(d);
      const nome = fornecedorCurto(grupo[0].nome) ?? grupo[0].tipo;
      g += `<text class="val" x="${x(d)}" y="${y - raio - 8}"
              text-anchor="middle">${esc(nome.slice(0, 22))}${
                grupo.length > 1 ? ` +${grupo.length - 1}` : ""}</text>`;
    }
  });
  return svg(larg, y + 40, g);
}

// ══ montagem das três vistas ══════════════════════════════════════════════

function cartao(titulo, corpo, nota) {
  return `<div class="card"><h3>${titulo}</h3>${corpo}${
    nota ? `<div class="nota">${nota}</div>` : ""}</div>`;
}

function vistaExecucao(d) {
  const c = d.execucao.cards, ano = d.ano;
  const varValor = c.homologado && d.execucao.homologado_anterior
    ? (c.homologado / d.execucao.homologado_anterior - 1) * 100 : null;
  const varN = c.n - (d.execucao.n_anterior || 0);
  const spark = d.execucao.meses.filter(m => m.valor);
  const maxS = Math.max(...spark.map(m => m.valor), 1);
  const linha = spark.map((m, i) =>
    `${8 + i * (224 / Math.max(1, spark.length - 1))},${38 - (m.valor / maxS) * 32}`
  ).join(" ");
  return `
  <div class="faixa f-4">
    <div class="card hero">
      <h3>Homologado em ${ano}</h3>
      <div class="n">${compacto(c.homologado)}</div>
      <div class="r">${varValor == null ? `sem ${ano - 1} para comparar`
        : `<span class="${varValor >= 0 ? "up" : "down"}">${
            varValor >= 0 ? "▲" : "▼"} ${pct(Math.abs(varValor), 0)}</span>
           sobre ${ano - 1}`}</div>
      ${spark.length > 1 ? svg(240, 44, `<polyline fill="none" stroke="var(--s1)"
        stroke-width="2" stroke-linejoin="round" points="${linha}"/>`) : ""}
    </div>
    <div class="card kpiv"><div class="v">${c.n}</div>
      <div class="r">contratações</div>
      <div class="r" style="margin-top:8px">${varN >= 0 ? "▲" : "▼"} ${
        Math.abs(varN)} vs. ${ano - 1}</div></div>
    <div class="card kpiv"><div class="v">${
        c.desagio == null ? "–" : pct(c.desagio)}</div>
      <div class="r">deságio médio</div>
      <div class="r" style="margin-top:8px">${
        c.estimado && c.homologado
          ? `${compacto(c.estimado - c.homologado)} economizados` : ""}</div></div>
    <div class="card kpiv"><div class="v">${c.contratos_vigentes}</div>
      <div class="r">contratos vigentes</div>
      <div class="r" style="margin-top:8px">${c.atas_vigentes} atas vigentes</div>
    </div>
  </div>
  <div class="faixa f-21">
    ${cartao(`Contratações por mês — estimado × homologado`,
             grafMeses(d.execucao.meses))}
    ${cartao("Por modalidade — valor homologado",
             grafBarras(d.execucao.modalidades.slice(0, 6), {
               valor: m => m.homologado || m.estimado || 0,
               rotulo: m => m.modalidade_nome ?? "–",
               sub: m => `${m.n} ${m.n === 1 ? "processo" : "processos"}`}))}
  </div>
  <div class="faixa f-11">
    ${cartao("Vence nos próximos 90 dias", tabelaVencendo(d.execucao.vencendo),
             `<span class="so-tela">Clicar leva à aba correspondente.</span>`)}
    ${cartao(`Onde o dinheiro foi — fornecedores de ${ano}`,
             tabelaFornecedores(d.execucao.fornecedores))}
  </div>`;
}

function tabelaVencendo(itens) {
  if (!itens.length) return `<div class="vazio">Nada vence em 90 dias.</div>`;
  return `<table><tr><th>Fornecedor / ata</th><th>Objeto</th>
    <th class="num">Vence</th></tr>` + itens.slice(0, 6).map(v => {
      const cls = (v.dias ?? 0) <= 15 ? "b" : (v.dias ?? 0) <= 60 ? "a" : "c";
      return `<tr><td>${esc(fornecedorCurto(v.nome) ?? "–")}</td>
        <td>${esc((v.objeto ?? "–").slice(0, 40))}</td>
        <td class="num"><span class="badge ${cls === "b" ? "err"
          : cls === "a" ? "warn" : "ok"}">${v.dias} dias</span></td></tr>`;
    }).join("") + `</table>`;
}

function tabelaFornecedores(itens) {
  if (!itens.length) return `<div class="vazio">Sem contratos no exercício.</div>`;
  const total = itens.reduce((s, f) => s + (f.total || 0), 0);
  const topo4 = itens.slice(0, 4).reduce((s, f) => s + (f.total || 0), 0);
  return `<table><tr><th>Fornecedor</th><th class="num">Contratos</th>
    <th class="num">Total</th></tr>` + itens.slice(0, 5).map(f =>
    `<tr><td>${esc(fornecedorCurto(f.fornecedor_nome) ?? "–")}</td>
      <td class="num">${f.n}</td><td class="num">${compacto(f.total)}</td></tr>`
  ).join("") + `</table>` + (total ? `<div class="nota">Os quatro primeiros
    somam ${pct(topo4 / total * 100, 0)} do valor contratado.</div>` : "");
}

function vistaAnalise(d) {
  const a = d.analise;
  return `
  ${cartao(`Valor homologado acumulado — ${d.ano - 2} a ${d.ano}`,
           grafSeries(a.series, d.ano),
           `O ano corrente em destaque; os anteriores ficam como contexto — a
            comparação é com o mesmo mês, não com o total do ano.`)}
  <div class="faixa f-11">
    ${cartao("Deságio por modalidade — quanto o certame economizou",
             grafDesagio(a.desagios))}
    ${cartao(`Concentração de fornecedores — ${d.ano}`,
             grafConcentracao(a.curva, a.fornecedores_total),
             `A linha tracejada é a distribuição perfeitamente igual — quanto
              mais a curva se afasta dela, mais concentrado é o mercado.`)}
  </div>
  ${cartao("Quando o município compra — processos por mês e modalidade",
           grafCalor(a.calor, a.meses_calor))}`;
}

function vistaVigilancia(d) {
  const v = d.vigilancia;
  return `
  <div class="faixa f-11">
    ${cartao(`Limite anual de dispensa — art. 75, II (${
               dinheiro(v.limite_compras)})`,
             grafLimites(v.limites, v.limite_compras),
             `A soma é por unidade administrativa. O agrupamento legal é por
              objeto de mesma natureza — este medidor é termômetro, não
              veredito.`)}
    ${cartao("Do edital ao contrato — onde os processos estão",
             grafFunil(v.funil),
             `${v.funil.publicadas - v.funil.com_resultado} publicadas ainda sem
              resultado registrado no PNCP.`)}
  </div>
  ${cartao("Agenda dos próximos 90 dias", grafAgenda(v.agenda),
           `Vermelho vence em menos de 15 dias; âmbar, em 60; verde, além
            disso.`)}`;
}

// ══ ciclo de vida ═════════════════════════════════════════════════════════

async function carregarPainel() {
  const alvo = { execucao: "p-execucao", analise: "p-analise",
                 vigilancia: "p-vigilancia" };
  for (const id of Object.values(alvo))
    $(id).classList.toggle("oculto", alvo[P.vista] !== id);
  if (!api.painel) return;
  const dados = await api.painel($("p-ano").value || null,
                                 $("p-orgao").value || null);
  P.dados = dados;
  mostrarChips(dados.alertas);
  $("p-execucao").innerHTML = vistaExecucao(dados);
  $("p-analise").innerHTML = vistaAnalise(dados);
  $("p-vigilancia").innerHTML = vistaVigilancia(dados);
}

// Os alertas ficam acima das subabas de propósito: alerta que só aparece
// depois de escolher a subaba certa não alerta ninguém.
function mostrarChips(a) {
  const chips = [];
  if (a.perto_do_limite) chips.push(["grave", "⚠", a.perto_do_limite,
    `unidade${a.perto_do_limite > 1 ? "s" : ""} perto do limite anual de dispensa`,
    () => irPara("contratacoes", {modalidade: "8"})]);
  if (a.vencendo) chips.push(["aviso", "⏱", a.vencendo,
    "contratos/atas vencem em 60 dias",
    () => irPara("contratos", {vigentes: true, ord: "vigencia", dir: "asc"})]);
  if (a.propostas) chips.push(["", "📄", a.propostas,
    "processos com proposta aberta",
    () => irPara("contratacoes", {propostas: true})]);
  if (a.paradas) chips.push(["", "⏳", a.paradas,
    "sem resultado há mais de 90 dias",
    () => irPara("contratacoes", {})]);
  const caixa = $("painel-chips");
  caixa.classList.toggle("oculto", !chips.length);
  caixa.innerHTML = chips.map(([cls, icone, n, texto], i) =>
    `<button class="chip ${cls}" data-chip="${i}">${icone} <b>${n}</b> ${texto}</button>`
  ).join("");
  caixa.querySelectorAll("[data-chip]").forEach(b =>
    b.addEventListener("click", () => chips[+b.dataset.chip][4]()));
}


// ── ligações da tela ──────────────────────────────────────────────────────
$("painel").querySelectorAll(".subabas button").forEach(b =>
  b.addEventListener("click", () => {
    P.vista = b.dataset.vista;
    $("painel").querySelectorAll(".subabas button").forEach(x =>
      x.classList.toggle("on", x === b));
    // a subaba fica lembrada: quem usa o painel para vigiar abre nela
    api.set_config?.("painel_vista", P.vista);
    carregarPainel();
  }));

["p-ano", "p-orgao"].forEach(id =>
  $(id).addEventListener("change", carregarPainel));

// Preenche os filtros do painel com os mesmos valores da lista — anos vindos
// do acervo, órgãos monitorados.
async function prepararPainel(estadoInicial) {
  const vista = estadoInicial?.painel_vista;
  if (vista && ["execucao", "analise", "vigilancia"].includes(vista)) {
    P.vista = vista;
    $("painel").querySelectorAll(".subabas button").forEach(b =>
      b.classList.toggle("on", b.dataset.vista === vista));
  }
  const f = await api.filtros_disponiveis();
  const ano = $("p-ano");
  ano.length = 0;
  (f.anos ?? []).forEach(a => ano.add(new Option(`Exercício ${a}`, a)));
  if (!ano.length) ano.add(new Option(`Exercício ${new Date().getFullYear()}`, ""));
  const orgao = $("p-orgao");
  orgao.length = 1;
  (f.orgaos ?? []).forEach(o =>
    orgao.add(new Option(o.nome ?? o.cnpj, o.cnpj)));
}

// A impressão leva as três vistas, cada uma numa página A3 deitada: o SVG é
// vetorial, então sai na resolução da impressora, não na da tela.
$("btn-imprimir-painel").addEventListener("click", async () => {
  if (!P.dados || !api.imprimir_painel) return;
  const botao = $("btn-imprimir-painel");
  const rotulo = botao.textContent;
  botao.disabled = true;
  botao.textContent = "Gerando…";
  try {
    const vistas = [["execucao", $("p-execucao").innerHTML],
                    ["analise", $("p-analise").innerHTML],
                    ["vigilancia", $("p-vigilancia").innerHTML]];
    await api.imprimir_painel(vistas, P.dados.ano);
  } finally {
    botao.disabled = false;
    botao.textContent = rotulo;
  }
});
