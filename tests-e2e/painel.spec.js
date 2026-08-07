const { test, expect } = require("@playwright/test");
const { abrirApp } = require("./harness");

test.beforeEach(async ({ page }) => abrirApp(page));

test("o Painel é a tela inicial e não mostra a lista", async ({ page }) => {
  await expect(page.locator("#painel")).toBeVisible();
  await expect(page.locator('nav.abas button[data-tipo="painel"]'))
    .toHaveClass(/on/);
  await expect(page.locator("#lista")).toBeHidden();
  await expect(page.locator("#filtros-lista")).toBeHidden();
  // os KPIs do topo repetiriam o hero: somem no painel
  await expect(page.locator("#kpis-topo")).toBeHidden();

  await page.locator('nav.abas button[data-tipo="contratacoes"]').click();
  await expect(page.locator("#painel")).toBeHidden();
  await expect(page.locator("#lista")).toBeVisible();
  await expect(page.locator("#kpis-topo")).toBeVisible();
});

test("a marca sob o cursor acende e as irmãs recuam", async ({ page }) => {
  const barras = page.locator("#p-execucao svg rect");
  const alvo = barras.first();
  const irma = barras.nth(3);

  // em repouso ninguém está esmaecido nem aceso
  await expect(irma).toHaveCSS("fill-opacity", "1");
  await expect(alvo).toHaveCSS("filter", "none");

  await alvo.hover();
  await expect(alvo).toHaveCSS("filter", "brightness(1.16)");
  await expect(irma).toHaveCSS("fill-opacity", "0.38");

  // saindo do gráfico, tudo volta — realce não é estado, é resposta
  await page.locator(".painel-topo").hover();
  await expect(irma).toHaveCSS("fill-opacity", "1");
  await expect(alvo).toHaveCSS("filter", "none");
});

test("barra não muda de tamanho ao ser realçada", async ({ page }) => {
  /* A barra vale o número que representa: crescer no hover faria a marca
     mentir sobre o valor. Quem cresce é o ponto, onde tamanho não é dado. */
  const barra = page.locator("#p-execucao svg rect").first();
  const antes = await barra.boundingBox();
  await barra.hover();
  await expect(barra).toHaveCSS("filter", "brightness(1.16)");
  const depois = await barra.boundingBox();
  expect(depois.width).toBeCloseTo(antes.width, 1);
  expect(depois.height).toBeCloseTo(antes.height, 1);
});

test("o tooltip próprio aparece na hora, com o valor em destaque",
    async ({ page }) => {
  const barra = page.locator("#p-execucao svg rect[data-tip-v]").first();
  const tt = page.locator(".graf-tt");
  await expect(tt).toBeHidden();

  await barra.hover();
  await expect(tt).toBeVisible();
  // o valor é o elemento forte; o rótulo (mês/série) é secundário — a
  // hierarquia que a skill dataviz pede para tooltip (valor lidera)
  await expect(tt.locator(".v")).toHaveText(/R\$/);
  await expect(tt.locator(".l")).not.toHaveCount(0);

  // sai do gráfico, some — não é um painel que fica aberto
  await page.locator(".painel-topo").hover();
  await expect(tt).toBeHidden();
});

test("o corte vertical lê todos os anos no mês apontado", async ({ page }) => {
  await page.locator('.subabas button[data-vista="analise"]').click();
  const cartao = page.locator('#p-analise .card:has([data-graf="series"])');
  const hit = cartao.locator("svg [data-cross-hit]");
  const guia = cartao.locator("svg [data-cross-guia]");
  const padrao = cartao.locator("svg [data-serie-padrao]").first();

  // em repouso, só o ponto do mês corrente aparece — é o direto-label que
  // vale sem hover nenhum
  await expect(guia).toHaveAttribute("opacity", "0");
  await expect(padrao).toHaveAttribute("opacity", "1");

  const box = await hit.boundingBox();
  await page.mouse.move(box.x + box.width * 0.3, box.y + box.height / 2);

  await expect(guia).toHaveAttribute("opacity", "1");
  await expect(padrao).toHaveAttribute("opacity", "0");
  // três anos no acervo de exemplo: o tooltip lista os três, um por linha
  const tt = page.locator(".graf-tt");
  await expect(tt.locator(".cab")).toBeVisible();
  await expect(tt.locator(".linha")).toHaveCount(3);
  await expect(tt).toContainText("2026");
  await expect(tt).toContainText("2025");
  await expect(tt).toContainText("2024");

  // sai da área do gráfico: o corte some, o padrão volta
  await page.mouse.move(10, 10);
  await expect(guia).toHaveAttribute("opacity", "0");
  await expect(padrao).toHaveAttribute("opacity", "1");
  await expect(tt).toBeHidden();
});

test("mudar o mês apontado muda os valores mostrados", async ({ page }) => {
  await page.locator('.subabas button[data-vista="analise"]').click();
  const hit = page.locator(
    '#p-analise .card:has([data-graf="series"]) svg [data-cross-hit]');
  const box = await hit.boundingBox();
  const tt = page.locator(".graf-tt");

  await page.mouse.move(box.x + box.width * 0.1, box.y + box.height / 2);
  const cedo = await tt.locator(".cab").textContent();
  await page.mouse.move(box.x + box.width * 0.9, box.y + box.height / 2);
  const tarde = await tt.locator(".cab").textContent();
  expect(cedo).not.toBe(tarde);
});

test("o corte vertical da concentração segue o cursor pela curva",
    async ({ page }) => {
  await page.locator('.subabas button[data-vista="analise"]').click();
  const cartao = page.locator(
    '#p-analise .card:has([data-graf="concentracao"])');
  const hit = cartao.locator("svg [data-cross-hit]");
  const ponto = cartao.locator("svg [data-cross-pt]");
  const padrao = cartao.locator("svg [data-serie-padrao]").first();

  await expect(ponto).toHaveAttribute("opacity", "0");
  const box = await hit.boundingBox();
  await page.mouse.move(box.x + box.width * 0.15, box.y + box.height / 2);

  await expect(ponto).toHaveAttribute("opacity", "1");
  await expect(padrao).toHaveAttribute("opacity", "0");
  const tt = page.locator(".graf-tt");
  await expect(tt).toContainText("do valor");
  await expect(tt).toContainText("fornecedor");
});

test("as três vistas trocam e ficam lembradas", async ({ page }) => {
  await expect(page.locator("#p-execucao")).toBeVisible();
  await expect(page.locator("#p-analise")).toBeHidden();

  await page.locator('.subabas button[data-vista="analise"]').click();
  await expect(page.locator("#p-analise")).toBeVisible();
  await expect(page.locator("#p-execucao")).toBeHidden();
  const salvo = await page.evaluate(() => window.__chamadas
    .find(c => c.metodo === "set_config" && c.k === "painel_vista"));
  expect(salvo.v).toBe("analise");
});

test("execução mostra hero, colunas mensais e modalidades",
    async ({ page }) => {
  const v = page.locator("#p-execucao");
  await expect(v).toContainText("Homologado em 2026");
  await expect(v).toContainText("contratações");
  await expect(v).toContainText("deságio médio");
  // colunas do mês: duas séries, com legenda (cor nunca sozinha)
  await expect(v.locator("svg rect").first()).toBeVisible();
  await expect(v).toContainText("Estimado");
  await expect(v).toContainText("Homologado");
  await expect(v).toContainText("Por modalidade");
});

test("análise traz as três séries e o mapa de calor", async ({ page }) => {
  await page.locator('.subabas button[data-vista="analise"]').click();
  const v = page.locator("#p-analise");
  await expect(v).toContainText("Valor homologado acumulado");
  await expect(v).toContainText("Deságio por modalidade");
  await expect(v).toContainText("Concentração de fornecedores");
  await expect(v).toContainText("processos por mês e modalidade");
  // uma linha por exercício comparado
  expect(await v.locator("svg polyline").count()).toBeGreaterThanOrEqual(3);
});

test("vigilância mostra medidores, funil e agenda", async ({ page }) => {
  await page.locator('.subabas button[data-vista="vigilancia"]').click();
  const v = page.locator("#p-vigilancia");
  await expect(v).toContainText("Limite anual de dispensa");
  await expect(v).toContainText("Do edital ao contrato");
  await expect(v).toContainText("Agenda dos próximos 90 dias");
  await expect(v).toContainText("Publicadas");
});

test("os alertas viram chips clicáveis acima das subabas",
    async ({ page }) => {
  const chips = page.locator("#painel-chips .chip");
  expect(await chips.count()).toBeGreaterThan(0);
  await expect(chips.first()).toContainText("limite anual de dispensa");
  await chips.nth(1).click();          // vencimentos levam aos contratos
  await expect(page.locator("#lista")).toBeVisible();
  const ultima = await page.evaluate(() => window.__chamadas
    .filter(c => c.metodo === "listar").pop());
  expect(ultima.tipo).toBe("contratos");
});

test("chip de limite filtra por modalidade, exercício e os objetos exatos",
    async ({ page }) => {
  await page.locator("#painel-chips .chip").first().click();
  const chamadas = await page.evaluate(() => window.__chamadas
    .filter(c => c.metodo === "listar"));
  // um clique, uma consulta — não a corrida entre o reset da aba e o filtro
  expect(chamadas.length).toBe(1);
  const [c] = chamadas;
  expect(c.tipo).toBe("contratacoes");
  expect(c.filtros.modalidade).toBe("8");
  expect(c.filtros.ano).toBe("2026");
  // não é "toda dispensa do ano": é só o que o alerta apontou
  expect(c.filtros.objetos).toEqual(
    ["MATERIAL LIMPEZA", "MEDICAMENTOS BÁSICOS", "SERVIÇOS TRANSPORTE",
     "PNEUS CÂMARAS", "MATERIAL ESCRITÓRIO", "COMBUSTÍVEL"]);
  await expect(page.locator("#f-modalidade")).toHaveValue("8");
  // sem caixa própria — o aviso é o que diz que o filtro está ativo
  await expect(page.locator("#filtro-alerta")).toBeVisible();
  await expect(page.locator("#filtro-alerta")).toContainText("limite anual");
});

test("chip de processo parado liga o filtro dedicado, sem corrida",
    async ({ page }) => {
  // não é nth(3): "propostas" está zerado neste acervo de exemplo e o chip
  // some da lista, deslocando os índices — pega pelo texto, não pela posição
  await page.locator("#painel-chips .chip", { hasText: "sem resultado" })
    .click();
  const chamadas = await page.evaluate(() => window.__chamadas
    .filter(c => c.metodo === "listar"));
  expect(chamadas.length).toBe(1);
  const [c] = chamadas;
  expect(c.tipo).toBe("contratacoes");
  expect(c.filtros.parada).toBe(true);
  expect(c.filtros.ano).toBe("2026");
  await expect(page.locator("#f-parada")).toBeChecked();
});

test("limpar filtros também derruba o filtro de objetos do alerta",
    async ({ page }) => {
  await page.locator("#painel-chips .chip").first().click();
  await expect(page.locator("#btn-limpar")).toBeVisible();
  await page.locator("#btn-limpar").click();
  await expect(page.locator("#filtro-alerta")).toBeHidden();
  await expect(page.locator("#f-modalidade")).toHaveValue("");
  const ultima = await page.evaluate(() => window.__chamadas
    .filter(c => c.metodo === "listar").pop());
  expect(ultima.filtros.objetos).toBeNull();
  expect(ultima.filtros.modalidade).toBeNull();
});

test("trocar de aba depois do alerta não carrega o filtro do alerta junto",
    async ({ page }) => {
  await page.locator("#painel-chips .chip").first().click();
  await page.locator('nav.abas button[data-tipo="contratos"]').click();
  await expect(page.locator("#filtro-alerta")).toBeHidden();
  const ultima = await page.evaluate(() => window.__chamadas
    .filter(c => c.metodo === "listar").pop());
  expect(ultima.filtros.objetos).toBeNull();
});

test("trocar o exercício recarrega o painel inteiro", async ({ page }) => {
  await page.locator("#p-ano").selectOption("2025");
  const chamada = await page.evaluate(() => window.__chamadas
    .filter(c => c.metodo === "painel").pop());
  expect(chamada.ano).toBe("2025");
});

test("imprimir manda as três vistas ao documento", async ({ page }) => {
  await page.locator("#btn-imprimir-painel").click();
  const chamada = await page.evaluate(() => window.__chamadas
    .filter(c => c.metodo === "imprimir_painel").pop());
  expect(chamada.tamanhos.map(t => t[0]))
    .toEqual(["execucao", "analise", "vigilancia"]);
  // as três vão com conteúdo, mesmo as que não estavam à vista
  expect(chamada.tamanhos.every(([, tamanho]) => tamanho > 500)).toBe(true);
});

test("os gráficos são desenhados na largura do espaço, não esticados",
    async ({ page }) => {
  // na largura "compacta" o conteúdo tem teto fixo: quem varia é o modo
  // expandido, que é onde a faixa morta aparecia
  await page.evaluate(() =>
    document.documentElement.dataset.largura = "expandida");
  const svg = page.locator('#p-execucao [data-graf="meses"] svg');
  await expect(svg).toBeVisible();
  await page.waitForTimeout(300);
  const antes = await svg.getAttribute("viewBox");

  // tela mais larga: o viewBox acompanha, em vez de escalar com faixa morta
  await page.setViewportSize({ width: 1800, height: 1000 });
  await page.waitForTimeout(300);
  const depois = await svg.getAttribute("viewBox");
  expect(depois).not.toBe(antes);
  const larguraSvg = Number(depois.split(" ")[2]);
  const caixa = await page.locator('#p-execucao [data-graf="meses"]')
    .boundingBox();
  expect(Math.abs(larguraSvg - caixa.width)).toBeLessThan(3);
});

test("vista oculta desenha ao aparecer", async ({ page }) => {
  // com display:none o contêiner tem largura zero; sem redesenhar, a vista
  // abriria vazia
  await page.locator('.subabas button[data-vista="vigilancia"]').click();
  const svg = page.locator('#p-vigilancia [data-graf="funil"] svg');
  await expect(svg).toBeVisible();
  const larg = Number((await svg.getAttribute("viewBox")).split(" ")[2]);
  expect(larg).toBeGreaterThan(200);
});

test("chips concordam em número", async ({ page }) => {
  await page.evaluate(() => {
    window.__painel = { ...window.PAINEL_DADOS,
      alertas: { perto_do_limite: 1, acima_do_limite: 0, vencendo: 1,
                 propostas: 1, paradas: 1 } };
  });
  await page.locator("#p-ano").selectOption({ index: 0 });
  const chips = page.locator("#painel-chips .chip");
  await expect(chips.nth(0)).toContainText("objeto perto do limite");
  await expect(chips.nth(1)).toContainText("contrato ou ata vence");
  await expect(chips.nth(2)).toContainText("processo com proposta aberta");
  await expect(chips.nth(3)).toContainText("processo sem resultado");
});

test("trocar de subaba não vai ao banco de novo", async ({ page }) => {
  const antes = await page.evaluate(() => window.__chamadas
    .filter(c => c.metodo === "painel").length);
  await page.locator('.subabas button[data-vista="analise"]').click();
  await page.locator('.subabas button[data-vista="vigilancia"]').click();
  await page.locator('.subabas button[data-vista="execucao"]').click();
  const depois = await page.evaluate(() => window.__chamadas
    .filter(c => c.metodo === "painel").length);
  expect(depois).toBe(antes);           // as três vistas já estão montadas
});

test("falha na consulta explica em vez de deixar a tela muda",
    async ({ page }) => {
  await page.evaluate(() => {
    window.pywebview.api.painel = async () => {
      throw new Error("database is locked");
    };
  });
  await page.locator("#p-ano").selectOption({ index: 0 });
  await expect(page.locator("#p-execucao")).toContainText("Não consegui montar");
  await expect(page.locator("#p-execucao")).toContainText("database is locked");
  await expect(page.locator("#painel")).not.toHaveClass(/carregando/);
});
