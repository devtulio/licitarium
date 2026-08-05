const { test, expect } = require("@playwright/test");
const { abrirApp } = require("./harness");

test.beforeEach(async ({ page }) => abrirApp(page));

async function abrirPrecos(page, termo = "papel") {
  await page.locator('nav.abas button[data-tipo="itens"]').click();
  await page.locator("#f-busca").fill(termo);
  await expect(page.locator("#precos-resumo")).toBeVisible();
}

test("descartar grava na hora e a razão pode vir depois", async ({ page }) => {
  await abrirPrecos(page);
  await page.locator('.linha input[data-item="X-3#10"]').uncheck();

  const aviso = page.locator("#precos-selecao");
  await expect(aviso).toContainText("1 item descartado");
  await expect(aviso).toContainText("1 sem justificativa");
  // o item aparece pelo que é, não pelo id
  await expect(aviso.locator(".descartado .obj")).toContainText("CADEIRA DE RODAS");

  const gravado = await page.evaluate(() => window.__chamadas
    .filter(c => c.metodo === "descartar_preco").pop());
  expect([gravado.busca, gravado.item_id, gravado.motivo])
    .toEqual(["papel", "X-3#10", null]);

  await aviso.locator('select[data-motivo]').selectOption("nao_comparavel");
  const comRazao = await page.evaluate(() => window.__chamadas
    .filter(c => c.metodo === "descartar_preco").pop());
  expect(comRazao.motivo).toBe("nao_comparavel");
  await expect(aviso).not.toContainText("sem justificativa");
});

test("razão fora da lista é digitada", async ({ page }) => {
  await abrirPrecos(page);
  await page.locator('.linha input[data-item="X-3#10"]').uncheck();
  const aviso = page.locator("#precos-selecao");

  const livre = aviso.locator('input[data-livre]');
  await expect(livre).toBeHidden();
  await aviso.locator('select[data-motivo]').selectOption("__outro");
  await expect(livre).toBeVisible();

  await livre.fill("preço de campanha promocional");
  await livre.blur();
  const gravado = await page.evaluate(() => window.__chamadas
    .filter(c => c.metodo === "descartar_preco").pop());
  expect(gravado.motivo).toBe("preço de campanha promocional");
});

test("voltar ao mesmo termo traz os descartes gravados", async ({ page }) => {
  await page.evaluate(() => {
    window.__descartes = { "papel": [
      { item_id: "X-3#10", motivo: "inexequivel",
        descricao: "CADEIRA DE RODAS REFORÇADA DOBRÁVEL", valor: 635000 }] };
  });
  await abrirPrecos(page);

  const aviso = page.locator("#precos-selecao");
  await expect(aviso).toContainText("1 item descartado");
  await expect(aviso).not.toContainText("sem justificativa");
  await expect(aviso.locator("select[data-motivo]"))
    .toHaveValue("inexequivel");
  // a caixa do item nasce desmarcada, e o cálculo já sai sem ele
  await expect(page.locator('.linha input[data-item="X-3#10"]'))
    .not.toBeChecked();
  const stats = await page.evaluate(() => window.__chamadas
    .filter(c => c.metodo === "estatisticas_preco").pop());
  expect(stats.excluidos).toEqual(["X-3#10"]);
});

test("restaurar todos apaga o registro da pesquisa", async ({ page }) => {
  await abrirPrecos(page);
  await page.locator('.linha input[data-item="X-3#10"]').uncheck();
  await page.locator("#precos-restaurar").click();

  const apagou = await page.evaluate(() => window.__chamadas
    .filter(c => c.metodo === "restaurar_preco").pop());
  expect([apagou.busca, apagou.item_id]).toEqual(["papel", undefined]);
  await expect(page.locator("#precos-selecao")).toBeHidden();
});

test("remarcar o item devolve ele à pesquisa", async ({ page }) => {
  await abrirPrecos(page);
  const caixa = page.locator('.linha input[data-item="X-3#10"]');
  await caixa.uncheck();
  await caixa.check();

  const devolveu = await page.evaluate(() => window.__chamadas
    .filter(c => c.metodo === "restaurar_preco").pop());
  expect([devolveu.busca, devolveu.item_id]).toEqual(["papel", "X-3#10"]);
  await expect(page.locator("#precos-selecao")).toBeHidden();
});
