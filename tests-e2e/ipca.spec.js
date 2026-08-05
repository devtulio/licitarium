const { test, expect } = require("@playwright/test");
const { abrirApp } = require("./harness");

test.beforeEach(async ({ page }) => abrirApp(page));

test("a caixa de corrigir pelo IPCA só existe na aba Preços",
    async ({ page }) => {
  await expect(page.locator("#cx-corrigir")).toBeHidden();
  await page.locator('nav.abas button[data-tipo="itens"]').click();
  await expect(page.locator("#cx-corrigir")).toBeVisible();
});

test("ligada, o resumo declara o índice e até quando corrigiu",
    async ({ page }) => {
  await page.locator('nav.abas button[data-tipo="itens"]').click();
  await page.locator("#f-busca").fill("papel");
  await expect(page.locator("#precos-resumo")).toBeVisible();
  await expect(page.locator("#precos-resumo")).not.toContainText("IPCA");

  await page.locator("#f-corrigir").check();
  const resumo = page.locator("#precos-resumo");
  await expect(resumo).toContainText("Valores corrigidos pelo IPCA até jun/2026");
  await expect(resumo).toContainText("1 item ficou de fora");

  const chamada = await page.evaluate(() => window.__chamadas
    .filter(c => c.metodo === "estatisticas_preco").pop());
  expect(chamada.corrigir).toBe(true);
});

test("ligada, a lista ganha a coluna Corrigido", async ({ page }) => {
  await page.locator('nav.abas button[data-tipo="itens"]').click();
  await expect(page.locator('.cab span', { hasText: "Corrigido" }))
    .toHaveCount(0);

  await page.locator("#f-corrigir").check();
  await expect(page.locator('.cab span', { hasText: "Corrigido" }))
    .toHaveCount(1);
  const chamada = await page.evaluate(() => window.__chamadas
    .filter(c => c.metodo === "listar").pop());
  expect(chamada.filtros.corrigir).toBe(true);
  const linha = page.locator('.linha:has(input[data-item="X-3#1"])');
  await expect(linha).toContainText("R$ 20,60");
});

test("os dois modos convivem, cada um com sua coluna", async ({ page }) => {
  await page.locator('nav.abas button[data-tipo="itens"]').click();
  await page.locator("#f-corrigir").check();
  await page.locator("#f-conteudo").check();

  const cab = page.locator(".cab");
  await expect(cab).toContainText("Corrigido");
  await expect(cab).toContainText("Por conteúdo");
  await expect(page.locator(".lista .linha.conteudo.corrigido").first())
    .toBeVisible();
  // a ordem é: valor pago, corrigido, por conteúdo (o cabeçalho tem spans
  // vazios no meio — seta de ordenação e alça de redimensionar)
  const rotulos = (await page.locator(".cab span").allTextContents())
    .map(t => t.trim()).filter(Boolean);
  const i = rotulos.indexOf("Valor unitário");
  expect(rotulos.slice(i + 1, i + 3)).toEqual(["Corrigido", "Por conteúdo"]);
});
