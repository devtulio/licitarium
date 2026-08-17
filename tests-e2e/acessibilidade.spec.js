// Achados da auditoria de acessibilidade (2026-08-09). Estes travam o que
// um leitor de tela recebe — coisa que nenhum teste anterior olhava.
const { test, expect } = require("@playwright/test");
const { abrirApp } = require("./harness");

test.beforeEach(async ({ page }) => abrirApp(page));

test("aba selecionada é anunciada, não só pintada", async ({ page }) => {
  // a classe .on pinta; sem aria-selected o leitor de tela anuncia N abas
  // e nenhuma marcada
  const painel = page.locator('nav.abas button[data-tipo="painel"]');
  await expect(painel).toHaveAttribute("aria-selected", "true");
  await page.locator('nav.abas button[data-tipo="contratacoes"]').click();
  await expect(painel).toHaveAttribute("aria-selected", "false");
  await expect(page.locator('nav.abas button[data-tipo="contratacoes"]'))
    .toHaveAttribute("aria-selected", "true");
});

test("subaba do Painel também anuncia a seleção", async ({ page }) => {
  const execucao = page.locator('.subabas button[data-vista="execucao"]');
  await expect(execucao).toHaveAttribute("aria-selected", "true");
  await page.locator('.subabas button[data-vista="economia"]').click();
  await expect(execucao).toHaveAttribute("aria-selected", "false");
  await expect(page.locator('.subabas button[data-vista="economia"]'))
    .toHaveAttribute("aria-selected", "true");
});

test("todo gráfico tem nome acessível e não esconde os rótulos",
    async ({ page }) => {
  await page.locator('.subabas button[data-vista="economia"]').click();
  await page.waitForTimeout(250);
  // [data-overlay] é a camada de corte vertical/rótulo por cima do SVG do
  // ECharts (ver painel.js:grafSeries) — decorativa, aria-hidden, e o
  // gráfico de baixo já carrega o nome acessível
  const graficos = await page.evaluate(() =>
    [...document.querySelectorAll("#p-economia svg:not([data-overlay])")]
      .map(s => ({
        nome: s.querySelector("title")?.textContent ?? "",
        papel: s.getAttribute("role"),
      })));
  expect(graficos.length).toBeGreaterThanOrEqual(4);
  for (const g of graficos) {
    expect(g.nome.length).toBeGreaterThan(3);   // <title> = nome acessível
    // role="img" tornaria os <text> de dentro apresentacionais, e é neles
    // que moram os números — ver comentário em painel.js:svg()
    expect(g.papel).toBeNull();
  }
});

test("as mensagens dinâmicas são regiões vivas", async ({ page }) => {
  // são o único canal de retorno, inclusive dos erros
  for (const id of ["sync-msg", "brasao-status", "pca-status"])
    await expect(page.locator(`#${id}`)).toHaveAttribute("role", "status");
});
