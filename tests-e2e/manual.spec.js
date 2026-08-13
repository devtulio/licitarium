// O MANUAL.html é um documento avulso (não passa pelo harness): tem tema
// próprio, com a mesma chave do programa, e imprime sempre em pergaminho.
const path = require("path");
const { test, expect } = require("@playwright/test");

const MANUAL = "file://" +
  path.resolve(__dirname, "..", "MANUAL.html").replace(/\\/g, "/");

const corDeFundo = page => page.evaluate(() =>
  getComputedStyle(document.body).backgroundColor);

test("tema do manual troca, persiste e responde ao parâmetro de URL", async ({ page }) => {
  await page.goto(MANUAL);
  expect(await corDeFundo(page)).toBe("rgb(245, 239, 226)");  // pergaminho

  await page.click('.temas button[data-tema="observatorio"]');
  expect(await corDeFundo(page)).toBe("rgb(16, 21, 28)");
  await expect(page.locator('.temas button[data-tema="observatorio"]'))
    .toHaveAttribute("aria-pressed", "true");

  // sobrevive à reabertura, e sem piscar: o tema já está no <html> quando o
  // primeiro pixel é pintado (script no <head>, não no fim do body)
  await page.goto(MANUAL);
  expect(await corDeFundo(page)).toBe("rgb(16, 21, 28)");
  expect(await page.locator("script").first().evaluate(
    s => s.closest("head") !== null)).toBe(true);

  await page.goto(MANUAL + "?tema=portal");
  expect(await corDeFundo(page)).toBe("rgb(248, 249, 250)");
});

test("estandarte mantém a paleta da marca; só o exergo acompanha o tema", async ({ page }) => {
  await page.goto(MANUAL + "?tema=observatorio");
  // pedra e sinete são da marca (IDENTIDADE.md §4): não mudam com o tema
  await expect(page.locator("header.capa svg rect"))
    .toHaveCSS("fill", "rgb(222, 213, 194)");
  // o exergo é inscrito no suporte, não na pedra: some se não acompanhar.
  // Desde a 1.33.0 a inscrição é contorno vetorial, não <text> — o alvo é
  // o path pintado com var(--text), que é justamente o que segue o tema.
  await expect(page.locator('header.capa svg path[fill="var(--text)"]').last())
    .toHaveCSS("fill", "rgb(220, 227, 236)");
});

test("impressão sai em pergaminho mesmo com tema escuro na tela", async ({ page }) => {
  await page.goto(MANUAL + "?tema=observatorio");
  expect(await corDeFundo(page)).toBe("rgb(16, 21, 28)");
  await page.emulateMedia({ media: "print" });
  expect(await corDeFundo(page)).toBe("rgb(255, 255, 255)");
  await expect(page.locator("h2").first()).toHaveCSS("color", "rgb(139, 46, 46)");
  await expect(page.locator(".no-print")).toBeHidden();
});
