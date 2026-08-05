const { test, expect } = require("@playwright/test");
const { abrirApp } = require("./harness");

test.beforeEach(async ({ page }) => abrirApp(page));

test("salvar cópia relata o que foi guardado", async ({ page }) => {
  await page.locator("#btn-config").click();
  await page.locator("#btn-exportar-acervo").click();
  const msg = page.locator("#acervo-msg");
  await expect(msg).toContainText("Cópia salva (12.3 MB)");
  await expect(msg).toContainText("2.674 itens");
  await expect(msg).toContainText("6 municípios de referência");
});

test("restaurar pede confirmação e avisa que precisa reabrir",
    async ({ page }) => {
  await page.locator("#btn-config").click();

  // recusando, nada é chamado: trocar o acervo inteiro não pode ser acidente
  page.once("dialog", d => d.dismiss());
  await page.locator("#btn-importar-acervo").click();
  expect(await page.evaluate(() => window.__chamadas
    .some(c => c.metodo === "importar_acervo"))).toBe(false);

  page.on("dialog", d => d.accept());
  await page.locator("#btn-importar-acervo").click();
  await expect(page.locator("#acervo-msg"))
    .toContainText("Feche e abra o Licitarium");
});

test("arquivo recusado explica o motivo e não some com o aviso",
    async ({ page }) => {
  await page.evaluate(() => {
    window.__respostaImportar = { ok: false,
      erro: "o banco dentro do arquivo está corrompido" };
  });
  await page.locator("#btn-config").click();
  page.on("dialog", d => d.accept());
  await page.locator("#btn-importar-acervo").click();
  await expect(page.locator("#acervo-msg"))
    .toContainText("Falhou: o banco dentro do arquivo está corrompido");
});
