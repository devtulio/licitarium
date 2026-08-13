const { test, expect } = require("@playwright/test");
const { abrirApp } = require("./harness");

// paleta fixa do papel, espelhando ui/app.js:PALETA_PAPEL — precisa ser um
// valor literal aqui (não lido do app) pra provar que o gráfico capturado
// NÃO segue a --erro do tema ativo na tela
const ERRO_PAPEL = "#a6231b";

test.beforeEach(async ({ page }) => abrirApp(page));

async function abrirPrecos(page, termo = "papel") {
  await page.locator('nav.abas button[data-tipo="itens"]').click();
  await page.locator("#f-busca").fill(termo);
  await expect(page.locator("#precos-resumo")).toBeVisible();
}

test("resumo traz dispersão além de média e mediana", async ({ page }) => {
  await abrirPrecos(page);
  // .disp também cobre os parágrafos de concentração e sensibilidade
  // (achado 2026-08-11) — o principal é sempre o primeiro
  const disp = page.locator("#precos-resumo .disp").first();
  await expect(disp).toContainText("Metade dos preços entre R$ 16,90 e R$ 30,50");
  await expect(disp).toContainText("Desvio padrão R$ 86,40");
  await expect(disp).toContainText("coeficiente de variação 161%");
  // o número sozinho não diz nada a quem assina a pesquisa
  await expect(disp).toContainText("confira se os itens são comparáveis");
});

test("box-plot ECharts mostra as duas cercas (Tukey e MAD)",
    async ({ page }) => {
  await abrirPrecos(page);
  const box = page.locator("#precos-boxplot");
  await expect(box).toBeVisible();
  await expect(box.locator("svg")).toBeVisible();
  await expect(box.locator("text").filter({ hasText: "Tukey" })).toBeVisible();
  await expect(box.locator("text").filter({ hasText: "MAD" })).toBeVisible();
});

test("box-plot anotado mostra um ponto por item, com rótulo",
    async ({ page }) => {
  await abrirPrecos(page);
  const box = page.locator("#precos-boxplot");
  await expect(box).toBeVisible();
  await expect(box).toHaveCSS("height", "240px");
  // 5 itens mockados: os 5 preços aparecem como rótulo no gráfico
  for (const preco of ["15,40", "16,90", "18,75", "30,50", "249,80"])
    await expect(box.locator("text").filter({ hasText: preco })).toBeVisible();
  // o extremo (R$ 249,80) vem na cor --erro do tema em uso, não na
  // --muted dos itens normais
  const erroTema = await page.evaluate(() =>
    getComputedStyle(document.documentElement).getPropertyValue("--erro").trim());
  const rotuloExtremo = box.locator("svg text", { hasText: "249,80" }).first();
  await expect(rotuloExtremo).toHaveAttribute("fill", erroTema);
});

test("box-plot some quando a amostra é pequena demais pra quartil",
    async ({ page }) => {
  await page.locator('nav.abas button[data-tipo="itens"]').click();
  // termo sem "papel" cai fora do mock -> resumo nulo; usa monkeypatch
  // direto no bridge pra simular n<5 (sem q1/q3)
  await page.evaluate(() => {
    window.pywebview.api.estatisticas_preco = async () => ({
      n: 3, minimo: 10, maximo: 40, media: 23, mediana: 20,
      desvio: 12, cv: 0.5, mad: 3, fornecedores: 2, proprios: 2,
      referencia: 0, total: 3
    });
  });
  await page.locator("#f-busca").fill("papel");
  await expect(page.locator("#precos-resumo")).toBeVisible();
  await expect(page.locator("#precos-boxplot")).toBeHidden();
});

test("relatório de preços manda o gráfico já desenhado pro papel",
    async ({ page }) => {
  await abrirPrecos(page);
  await page.locator("#btn-rel-precos").click();
  await expect(page.locator("#veu-relatorios")).toBeVisible();
  await page.locator("#rel-gerar").click();

  const previa = await page.evaluate(() => window.__chamadas
    .find(c => c.metodo === "dados_grafico_precos"));
  expect(previa.termo).toBe("papel");

  const chamada = await page.evaluate(() => window.__chamadas
    .filter(c => c.metodo === "gerar_relatorio").pop());
  expect(chamada.tipo).toBe("precos");
  expect(chamada.params.grafico_html).toContain("<svg");
  // o gráfico mandado pro papel tem o rótulo do extremo — prova que é o
  // mesmo desenho da tela, não um SVG à mão feito à parte
  expect(chamada.params.grafico_html).toContain("249,80");
});

test("relatório de preços sem seleção não quebra — só fica sem o gráfico pronto",
    async ({ page }) => {
  await page.evaluate(() => { window.__semSelecaoPrecos = true; });
  await abrirPrecos(page);
  await page.locator("#btn-rel-precos").click();
  await page.locator("#rel-gerar").click();
  const chamada = await page.evaluate(() => window.__chamadas
    .filter(c => c.metodo === "gerar_relatorio").pop());
  expect(chamada.params.grafico_html).toBeUndefined();
  // gerar_relatorio segue chamado — quem recusa e explica é o backend
  // real (mock aqui sempre devolve ok, então só confere que não travou)
  await expect(page.locator("#rel-status")).toContainText("Aberto");
});

test("preço fora da curva é apontado e só sai se o usuário mandar",
    async ({ page }) => {
  await abrirPrecos(page);
  const aviso = page.locator("#precos-resumo .fora");
  await expect(aviso).toContainText("1 preço destoa");
  await expect(aviso).toContainText("R$ 50,90");   // limite superior

  // nada foi descartado sozinho
  expect(await page.evaluate(() => window.__chamadas
    .filter(c => c.metodo === "estatisticas_preco"
                 && (c.excluidos || []).length).length)).toBe(0);

  await page.locator("#btn-descartar-fora").click();
  await expect(page.locator("#precos-selecao")).toContainText("1 item descartado");
  const ultima = await page.evaluate(() => window.__chamadas
    .filter(c => c.metodo === "estatisticas_preco").pop());
  expect(ultima.incluidos).not.toContain("X-3#10");
  // some do cálculo, mas continua na lista com a caixa desmarcada — dá para
  // voltar atrás sem refazer a pesquisa
  await expect(page.locator('.linha input[data-item="X-3#10"]'))
    .not.toBeChecked();
  await expect(page.locator("#precos-resumo .fora")).toHaveCount(0);
});

test("filtro por unidade de medida só existe na aba Preços",
    async ({ page }) => {
  const filtro = page.locator("#f-unidade");
  await expect(filtro).toBeHidden();
  await page.locator('nav.abas button[data-tipo="itens"]').click();
  await expect(filtro).toBeVisible();
  // agrupado e com a contagem, do mais frequente para o mais raro
  await expect(filtro.locator("option").nth(1)).toHaveText("Unidade (12)");
  await expect(filtro.locator("option").nth(2)).toHaveText("Caixa (4)");

  await filtro.selectOption("Caixa");
  const ultima = await page.evaluate(() => window.__chamadas
    .filter(c => c.metodo === "listar").pop());
  expect(ultima.filtros.unidade).toBe("Caixa");

  // sai da aba: o filtro some e para de restringir a consulta
  await page.locator('nav.abas button[data-tipo="contratos"]').click();
  await expect(filtro).toBeHidden();
  const depois = await page.evaluate(() => window.__chamadas
    .filter(c => c.metodo === "listar").pop());
  expect(depois.filtros.unidade).toBeFalsy();
});

test("gráfico do relatório de preços usa a cor fixa do papel, não a do tema da tela",
    async ({ page }) => {
  // achado 2026-08-13 (/dataviz): o box-plot capturado pra impressão
  // herdava a --erro do tema ativo na tela (Pergaminho/Observatório nunca
  // validados pra fundo branco) — documento oficial não tem tema
  for (const tema of ["pergaminho", "observatorio"]) {
    await abrirApp(page, { tema, temaBanco: tema });
    const erroTema = await page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue("--erro").trim());
    expect(erroTema).not.toBe(ERRO_PAPEL);

    await abrirPrecos(page);
    await page.locator("#btn-rel-precos").click();
    await page.locator("#rel-gerar").click();
    const chamada = await page.evaluate(() => window.__chamadas
      .filter(c => c.metodo === "gerar_relatorio").pop());
    // extremo (R$ 249,80) sempre na --erro do papel, nunca na do tema
    expect(chamada.params.grafico_html).toContain(`fill="${ERRO_PAPEL}"`);
    expect(chamada.params.grafico_html).not.toContain(`fill="${erroTema}"`);
  }
});

test("coluna Qtde ordena como as demais", async ({ page }) => {
  await page.locator('nav.abas button[data-tipo="itens"]').click();
  await page.locator('.cab span[data-ord="quantidade"]').click();
  let ultima = await page.evaluate(() => window.__chamadas
    .filter(c => c.metodo === "listar").pop());
  expect([ultima.filtros.ord, ultima.filtros.dir]).toEqual(["quantidade", "asc"]);
  await page.locator('.cab span[data-ord="quantidade"]').click();
  ultima = await page.evaluate(() => window.__chamadas
    .filter(c => c.metodo === "listar").pop());
  expect(ultima.filtros.dir).toBe("desc");
});
