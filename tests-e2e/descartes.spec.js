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
    // um item descartado não pode estar também selecionado — mesma
    // invariante que o backend garante (ver licitarium.py)
    window.__selecionados = { "papel": ["X-3#1", "X-3#9", "X-3#11",
                                        "REF#1", "X-3#2"] };
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
  expect(stats.incluidos).not.toContain("X-3#10");
});

test("restaurar todos reconsidera cada item — volta a valer no resumo",
    async ({ page }) => {
  await abrirPrecos(page);
  await page.locator('.linha input[data-item="X-3#10"]').uncheck();
  await page.locator("#precos-restaurar").click();

  // "restaurar" não só apaga o descarte — tem de selecionar de novo,
  // senão o item volta a ficar fora da conta (achado ao migrar para o
  // modelo de seleção: o antigo restaurar_preco sozinho não bastava)
  const selecionou = await page.evaluate(() => window.__chamadas
    .filter(c => c.metodo === "selecionar_preco").pop());
  expect([selecionou.busca, selecionou.item_id]).toEqual(["papel", "X-3#10"]);
  await expect(page.locator("#precos-selecao")).toBeHidden();
  await expect(page.locator('.linha input[data-item="X-3#10"]')).toBeChecked();
});

test("remarcar o item devolve ele à pesquisa", async ({ page }) => {
  await abrirPrecos(page);
  const caixa = page.locator('.linha input[data-item="X-3#10"]');
  await caixa.uncheck();
  await caixa.check();

  const devolveu = await page.evaluate(() => window.__chamadas
    .filter(c => c.metodo === "selecionar_preco").pop());
  expect([devolveu.busca, devolveu.item_id]).toEqual(["papel", "X-3#10"]);
  await expect(page.locator("#precos-selecao")).toBeHidden();
});

test("escolher unidade classifica a pesquisa inteira, não só a página",
    async ({ page }) => {
  // achado do usuário (2026-08-08): buscar "alface" mistura maço, quilo e
  // unidade — escolher uma unidade aqui precisa marcar só os itens dela e
  // descartar o resto com a justificativa pronta, sem exigir clicar item a
  // item (e sem se limitar à página visível: o cálculo usa a pesquisa toda)
  await abrirPrecos(page);
  await page.locator("#f-unidade").selectOption("Caixa");

  const classificou = await page.evaluate(() => window.__chamadas
    .filter(c => c.metodo === "classificar_por_unidade").pop());
  expect([classificou.busca, classificou.unidade, classificou.ano,
          classificou.origem]).toEqual(["papel", "Caixa", null, null]);
  // o mapa de descartes é relido do banco depois — não fica remendado com
  // o estado antigo do que a página já tinha marcado
  const chamadas = await page.evaluate(() => window.__chamadas
    .map(c => c.metodo));
  const iClassificou = chamadas.lastIndexOf("classificar_por_unidade");
  expect(chamadas.slice(iClassificou + 1)).toContain("descartes");
});

test("unidade sem termo de busca não classifica nada",
    async ({ page }) => {
  await page.locator('nav.abas button[data-tipo="itens"]').click();
  await page.locator("#f-unidade").selectOption("Caixa");
  const chamou = await page.evaluate(() => window.__chamadas
    .some(c => c.metodo === "classificar_por_unidade"));
  expect(chamou).toBe(false);
});
