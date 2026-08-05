const { test, expect } = require("@playwright/test");
const { abrirApp } = require("./harness");

test.beforeEach(async ({ page }) => abrirApp(page));

async function abrirPrecos(page, termo = "papel") {
  await page.locator('nav.abas button[data-tipo="itens"]').click();
  await page.locator("#f-busca").fill(termo);
  await expect(page.locator("#precos-resumo")).toBeVisible();
}

test("a caixa de comparar por conteúdo só existe na aba Preços",
    async ({ page }) => {
  await expect(page.locator("#cx-conteudo")).toBeHidden();
  await page.locator('nav.abas button[data-tipo="itens"]').click();
  await expect(page.locator("#cx-conteudo")).toBeVisible();
});

test("ligada, o resumo passa a ser por unidade-base", async ({ page }) => {
  await abrirPrecos(page);
  // desligada: preço de embalagem, como foi pago
  await expect(page.locator("#precos-resumo")).toContainText("menor unitário");

  await page.locator("#f-conteudo").check();
  const resumo = page.locator("#precos-resumo");
  await expect(resumo).toContainText("menor por unidade");
  await expect(resumo).toContainText("R$ 0,0375");   // casas de centavo
  await expect(resumo).toContainText("2 itens ficaram de fora desta comparação");

  const chamada = await page.evaluate(() => window.__chamadas
    .filter(c => c.metodo === "estatisticas_preco").pop());
  expect(chamada.porConteudo).toBe(true);
});

test("ligada, a lista ganha a coluna e o item sem conteúdo fica vazio",
    async ({ page }) => {
  await abrirPrecos(page);
  await expect(page.locator('.cab span', { hasText: "Por conteúdo" }))
    .toHaveCount(0);

  await page.locator("#f-conteudo").check();
  await expect(page.locator('.cab span', { hasText: "Por conteúdo" }))
    .toHaveCount(1);
  await expect(page.locator(".lista .linha.conteudo").first()).toBeVisible();
  // item com conteúdo legível mostra o valor e a base
  const comValor = page.locator('.linha:has(input[data-item="X-3#1"])');
  await expect(comValor).toContainText("R$ 0,0375");
  await expect(comValor).toContainText("/unidade");
  // item sem conteúdo não inventa número
  const semValor = page.locator('.linha:has(input[data-item="X-3#10"])');
  await expect(semValor.locator("span").nth(5)).toHaveText("–");
});

test("nenhum item conversível: explica em vez de mostrar resumo vazio",
    async ({ page }) => {
  await page.evaluate(() => { window.__semConteudo = true; });
  await abrirPrecos(page);
  await page.locator("#f-conteudo").check();
  await expect(page.locator("#precos-resumo"))
    .toContainText("Nenhum dos 4 itens desta pesquisa diz quanto vem na embalagem");
});
