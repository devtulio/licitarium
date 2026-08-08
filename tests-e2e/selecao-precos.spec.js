// Seleção de itens na pesquisa de preços. Pedido do usuário (2026-08-08): a
// busca abria com tudo marcado (opt-out — desmarcar o que não servia); agora
// abre com tudo desmarcado (opt-in — marcar é ato positivo), com "Selecionar
// todos" como atalho para quem quer o comportamento de antes.
const { test, expect } = require("@playwright/test");
const { abrirApp } = require("./harness");

test.beforeEach(async ({ page }) => {
  await abrirApp(page);
  await page.evaluate(() => { window.__selecionados = {}; });  // busca nova
  await page.locator('nav.abas button[data-tipo="itens"]').click();
});

const caixas = page => page.locator(".linha:not(.cab) .sel input");

test("busca nova vem com tudo desmarcado", async ({ page }) => {
  await expect(caixas(page)).toHaveCount(5);
  for (const c of await caixas(page).all()) await expect(c).not.toBeChecked();
  await expect(page.locator("#precos-selecao")).toBeHidden();

  await page.locator("#f-busca").fill("papel");     // resumo exige termo
  await expect(page.locator("#precos-resumo")).toBeVisible();
  await expect(page.locator("#precos-resumo")).toContainText(
    "Nenhum item selecionado ainda");
});

test("marcar item soma ao resumo, desmarcar tira de novo",
    async ({ page }) => {
  await page.locator("#f-busca").fill("papel");
  await expect(page.locator("#precos-resumo")).toContainText(
    "Nenhum item selecionado ainda");

  await caixas(page).nth(2).check();
  const marcou = await page.evaluate(() => window.__chamadas
    .filter(c => c.metodo === "selecionar_preco").pop());
  expect([marcou.busca, marcou.item_id]).toEqual(["papel", "X-3#10"]);
  await expect(page.locator("#precos-resumo")).not.toContainText(
    "Nenhum item selecionado");
  await expect(page.locator("#precos-selecao")).toBeHidden();  // marcar não é descarte

  await caixas(page).nth(2).uncheck();
  await expect(page.locator("#precos-selecao"))
    .toContainText("1 item descartado");
  await expect(page.locator("#precos-resumo")).toContainText(
    "Nenhum item selecionado ainda");
});

test("descartar não abre o detalhe do item", async ({ page }) => {
  await caixas(page).first().check();
  await expect(page.locator("#veu-detalhe")).toBeHidden();
  // mas clicar na linha continua abrindo
  await page.locator(".linha:not(.cab)").first().click();
  await expect(page.locator("#veu-detalhe")).toBeVisible();
});

test("Selecionar todos marca a pesquisa inteira",
    async ({ page }) => {
  await page.locator("#f-busca").fill("papel");
  await expect(page.locator("#btn-selecionar-todos")).toBeVisible();
  await page.locator("#btn-selecionar-todos").click();

  const chamou = await page.evaluate(() => window.__chamadas
    .filter(c => c.metodo === "selecionar_todos_precos").pop());
  expect(chamou.busca).toBe("papel");
  // a seleção é relida do banco depois — não fica remendada com o que a
  // tela já tinha marcado (mesmo cuidado do classificar_por_unidade)
  const chamadas = await page.evaluate(() => window.__chamadas.map(c => c.metodo));
  const iChamou = chamadas.lastIndexOf("selecionar_todos_precos");
  expect(chamadas.slice(iChamou + 1)).toContain("selecionados");
});

test("Selecionar todos também aparece dentro do resumo vazio",
    async ({ page }) => {
  await page.locator("#f-busca").fill("papel");
  const resumo = page.locator("#precos-resumo");
  await expect(resumo).toContainText("Nenhum item selecionado ainda");
  await resumo.locator("#btn-selecionar-todos-resumo").click();
  const chamou = await page.evaluate(() => window.__chamadas
    .filter(c => c.metodo === "selecionar_todos_precos").pop());
  expect(chamou.busca).toBe("papel");
});

test("restaurar reconsidera cada item — volta a valer no resumo",
    async ({ page }) => {
  await caixas(page).nth(0).check();
  await caixas(page).nth(1).check();
  await caixas(page).nth(0).uncheck();
  await caixas(page).nth(1).uncheck();
  await expect(page.locator("#precos-selecao"))
    .toContainText("2 itens descartados");
  await page.locator("#precos-restaurar").click();
  await expect(page.locator("#precos-selecao")).toBeHidden();
  await expect(caixas(page).nth(0)).toBeChecked();
  await expect(caixas(page).nth(1)).toBeChecked();
});

test("trocar o termo recomeça a seleção", async ({ page }) => {
  await page.locator("#f-busca").fill("papel");
  await expect(page.locator("#precos-resumo")).toBeVisible();
  await caixas(page).first().check();
  await caixas(page).first().uncheck();
  await expect(page.locator("#precos-selecao")).toBeVisible();
  // descarte vale para a pesquisa em curso, não para a próxima
  await page.locator("#f-busca").fill("caneta");
  await expect(page.locator("#precos-selecao")).toBeHidden();
});

// ── contador e filtros que selecionam (2026-08-08, propostos e pedidos) ────

test("contador mostra quantos de quantos estão selecionados",
    async ({ page }) => {
  await page.locator("#f-busca").fill("papel");
  await expect(page.locator("#precos-resumo")).toContainText(
    "0 de 6 selecionados");
  await caixas(page).first().check();
  // o total nunca muda (é a busca inteira); o "N de" segue o que a
  // estatística conta — a fixture do mock não recalcula por item marcado,
  // então só confere que saiu do estado "0 de"
  await expect(page.locator("#precos-resumo")).not.toContainText(
    "0 de 6 selecionados");
  await expect(page.locator("#precos-resumo")).toContainText(
    "de 6 selecionados");
});

test("selecionar por fornecedor soma à seleção", async ({ page }) => {
  await page.locator("#f-busca").fill("papel");
  const resumo = page.locator("#precos-resumo");
  await expect(resumo.locator("#sel-fornecedor-preco")).toBeVisible();
  await expect(resumo.locator("#sel-fornecedor-preco option")).toHaveCount(3); // vazio + 2
  await resumo.locator("#sel-fornecedor-preco")
    .selectOption("11.111.111/0001-11");

  const chamou = await page.evaluate(() => window.__chamadas
    .filter(c => c.metodo === "selecionar_por_fornecedor").pop());
  expect([chamou.busca, chamou.fornecedor_ni])
    .toEqual(["papel", "11.111.111/0001-11"]);
});

test("selecionar por faixa de valor soma à seleção", async ({ page }) => {
  await page.locator("#f-busca").fill("papel");
  const resumo = page.locator("#precos-resumo");
  await resumo.locator("#sel-valor-min").fill("100");
  await resumo.locator("#sel-valor-max").fill("300");
  await resumo.locator("#btn-selecionar-faixa").click();

  const chamou = await page.evaluate(() => window.__chamadas
    .filter(c => c.metodo === "selecionar_por_faixa").pop());
  expect([chamou.busca, chamou.minimo, chamou.maximo])
    .toEqual(["papel", 100, 300]);
});

test("faixa aceita só um lado preenchido", async ({ page }) => {
  await page.locator("#f-busca").fill("papel");
  const resumo = page.locator("#precos-resumo");
  await resumo.locator("#sel-valor-min").fill("1000");
  await resumo.locator("#btn-selecionar-faixa").click();
  const chamou = await page.evaluate(() => window.__chamadas
    .filter(c => c.metodo === "selecionar_por_faixa").pop());
  expect([chamou.minimo, chamou.maximo]).toEqual([1000, null]);
});

test("selecionar por texto na descrição soma à seleção", async ({ page }) => {
  await page.locator("#f-busca").fill("papel");
  const resumo = page.locator("#precos-resumo");
  await resumo.locator("#sel-texto").fill("sulfite");
  await resumo.locator("#btn-selecionar-texto").click();

  const chamou = await page.evaluate(() => window.__chamadas
    .filter(c => c.metodo === "selecionar_por_texto").pop());
  expect([chamou.busca, chamou.contendo]).toEqual(["papel", "sulfite"]);
});
