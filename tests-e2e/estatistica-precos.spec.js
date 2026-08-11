const { test, expect } = require("@playwright/test");
const { abrirApp } = require("./harness");

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
