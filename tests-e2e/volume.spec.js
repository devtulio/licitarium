// O peso de um município de referência varia em ordens de grandeza: um
// vizinho pequeno custa minutos, uma cidade média custa horas e centenas de
// MB. Estes testes garantem que o usuário é avisado ANTES da coleta.
const { test, expect } = require("@playwright/test");
const { abrirApp } = require("./harness");

test.beforeEach(async ({ page }) => {
  await abrirApp(page);
  await page.locator("#btn-config").click();
});

async function escolher(page, nome, codigo) {
  await page.locator("#ref-busca").fill(nome.slice(0, 4));
  await page.locator(`#ref-sugestoes button[data-c="${codigo}"]`).click();
}

test("cidade média avisa o tamanho da coleta e respeita o cancelamento",
    async ({ page }) => {
  let msg = "";
  page.once("dialog", async d => { msg = d.message(); await d.dismiss(); });
  await escolher(page, "Olímpia", "3533908");

  expect(msg).toContain("5.982 contratações");
  expect(msg).toContain("105.283");        // preços estimados
  expect(msg).toContain("384 MB");
  expect(msg).toContain("5,9 horas");      // minutos viram horas
  expect(msg).toContain("ATENÇÃO");        // destaque para coleta longa

  // cancelou: não entra na lista
  await expect(page.locator("#cfg-referencia")).not.toContainText("Olímpia");
  const adicionou = await page.evaluate(() => window.__chamadas
    .some(c => c.metodo === "adicionar_municipio_referencia"));
  expect(adicionou).toBe(false);
});

test("vizinho pequeno mostra minutos e entra ao confirmar", async ({ page }) => {
  let msg = "";
  page.once("dialog", async d => { msg = d.message(); await d.accept(); });
  await escolher(page, "Paulo de Faria", "3536604");

  expect(msg).toContain("14 minutos");
  expect(msg).not.toContain("ATENÇÃO");
  await expect(page.locator("#cfg-referencia")).toContainText("Paulo de Faria");
});

test("município sem publicação no PNCP nem é oferecido", async ({ page }) => {
  let msg = "";
  page.once("dialog", async d => { msg = d.message(); await d.accept(); });
  await escolher(page, "Nova Granada", "3533007");

  // é um aviso, não uma pergunta: não há o que decidir
  expect(msg).toContain("não tem contratações publicadas");
  await expect(page.locator("#cfg-referencia")).not.toContainText("Nova Granada");
  const adicionou = await page.evaluate(() => window.__chamadas
    .some(c => c.metodo === "adicionar_municipio_referencia"));
  expect(adicionou).toBe(false);
});

test("falha ao consultar o volume não impede o usuário de decidir",
    async ({ page }) => {
  await page.evaluate(() => {
    window.__estimativas["3536604"] = { erro: "sem conexão com o PNCP" };
  });
  let msg = "";
  page.once("dialog", async d => { msg = d.message(); await d.accept(); });
  await escolher(page, "Paulo de Faria", "3536604");

  expect(msg).toContain("Não consegui consultar o volume");
  expect(msg).toContain("sem conexão");
  // portal fora do ar não pode barrar o cadastro: o usuário escolhe
  await expect(page.locator("#cfg-referencia")).toContainText("Paulo de Faria");
});
