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
