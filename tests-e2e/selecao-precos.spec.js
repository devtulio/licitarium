// Seleção de itens na pesquisa de preços: o usuário descarta o que não é
// comparável (suporte de papel higiênico numa busca por papel higiênico) e
// o resumo do art. 23 passa a valer só sobre o que ele manteve.
const { test, expect } = require("@playwright/test");
const { abrirApp } = require("./harness");

test.beforeEach(async ({ page }) => {
  await abrirApp(page);
  await page.locator('nav.abas button[data-tipo="itens"]').click();
});

const caixas = page => page.locator(".linha:not(.cab) .sel input");

test("todos vêm marcados e desmarcar tira o item do resumo",
    async ({ page }) => {
  await expect(caixas(page)).toHaveCount(5);
  for (const c of await caixas(page).all()) await expect(c).toBeChecked();
  await expect(page.locator("#precos-selecao")).toBeHidden();

  await page.locator("#f-busca").fill("papel");     // resumo exige termo
  await expect(page.locator("#precos-resumo")).toBeVisible();
  await caixas(page).nth(2).uncheck();

  const stat = await page.evaluate(() => window.__chamadas
    .filter(c => c.metodo === "estatisticas_preco").pop());
  expect(stat.excluidos).toEqual(["X-3#10"]);
  await expect(page.locator("#precos-selecao"))
    .toContainText("1 item descartado");

  // a linha CONTINUA na tela, desmarcada: é onde se desfaz a escolha
  await expect(caixas(page)).toHaveCount(5);
  await expect(caixas(page).nth(2)).not.toBeChecked();
});

test("descartar não abre o detalhe do item", async ({ page }) => {
  await caixas(page).first().uncheck();
  await expect(page.locator("#veu-detalhe")).toBeHidden();
  // mas clicar na linha continua abrindo
  await page.locator(".linha:not(.cab)").first().click();
  await expect(page.locator("#veu-detalhe")).toBeVisible();
});

test("restaurar devolve todos os itens", async ({ page }) => {
  await caixas(page).nth(0).uncheck();
  await caixas(page).nth(1).uncheck();
  await expect(page.locator("#precos-selecao"))
    .toContainText("2 itens descartados");
  await page.locator("#precos-restaurar").click();
  await expect(page.locator("#precos-selecao")).toBeHidden();
  for (const c of await caixas(page).all()) await expect(c).toBeChecked();
});

test("trocar o termo recomeça a seleção", async ({ page }) => {
  await page.locator("#f-busca").fill("papel");
  await expect(page.locator("#precos-resumo")).toBeVisible();
  await caixas(page).first().uncheck();
  await expect(page.locator("#precos-selecao")).toBeVisible();
  // descarte vale para a pesquisa em curso, não para a próxima
  await page.locator("#f-busca").fill("caneta");
  await expect(page.locator("#precos-selecao")).toBeHidden();
  const stat = await page.evaluate(() => window.__chamadas
    .filter(c => c.metodo === "estatisticas_preco").pop());
  expect(stat.excluidos).toEqual([]);
});
