const { test, expect } = require("@playwright/test");
const { abrirApp } = require("./harness");

test.beforeEach(async ({ page }) => abrirApp(page));

test("boot: app abre com município, KPIs e alertas", async ({ page }) => {
  await expect(page.locator("#app")).toBeVisible();
  await expect(page.locator("#wizard")).toBeHidden();
  await expect(page.locator("#sub-municipio"))
    .toContainText("Orindiúva · SP");
  await expect(page.locator("#kpi-contratacoes")).toHaveText("131");
  await expect(page.locator("#chip-vencendo")).toContainText("9");
  await expect(page.locator("#chip-propostas")).toContainText("2");
});

test("lista renderiza e ordenação por clique manda ord/dir à ponte",
    async ({ page }) => {
  await expect(page.locator(".linha:not(.cab)")).toHaveCount(3);
  const cabObjeto = page.locator('.cab span[data-ord="objeto"]');
  await cabObjeto.click();
  await expect(cabObjeto).toHaveAttribute("aria-sort", "ascending");
  await cabObjeto.click();
  await expect(cabObjeto).toHaveAttribute("aria-sort", "descending");
  const chamadas = await page.evaluate(() =>
    window.__chamadas.filter(c => c.metodo === "listar").slice(-2));
  expect(chamadas[0].filtros.ord).toBe("objeto");
  expect(chamadas[0].filtros.dir).toBe("asc");
  expect(chamadas[1].filtros.dir).toBe("desc");
});

test("abas trocam colunas e detalhe abre ao clicar na linha",
    async ({ page }) => {
  await page.locator('nav.abas button[data-tipo="contratos"]').click();
  await expect(page.locator(".cab")).toContainText("Contrato");
  await expect(page.locator(".linha:not(.cab)").first())
    .toContainText("33/2026");   // "0033/26" normalizado para numero/ano
  await page.locator(".linha:not(.cab)").first().click();
  await expect(page.locator("#veu-detalhe")).toBeVisible();
  // JSON bruto formatado e colorido (chave + booleano do mock)
  await expect(page.locator("#det-raw .j-chave").first()).toContainText("exemplo");
  await expect(page.locator("#det-raw .j-bool")).toHaveText("true");
  await page.keyboard.press("Escape");
  await expect(page.locator("#veu-detalhe")).toBeHidden();
});

test("tema troca via configurações e persiste via set_config",
    async ({ page }) => {
  await page.locator("#btn-config").click();
  await page.locator('.tcard[data-tema="observatorio"]').click();
  await expect(page.locator("html"))
    .toHaveAttribute("data-theme", "observatorio");
  const salvo = await page.evaluate(() =>
    window.__chamadas.find(c => c.metodo === "set_config" && c.k === "tema"));
  expect(salvo.v).toBe("observatorio");
});

test("aba Preços lista itens e resume o histórico do termo buscado",
    async ({ page }) => {
  await page.locator('nav.abas button[data-tipo="itens"]').click();
  await expect(page.locator("#cx-homologados")).toBeVisible();
  await expect(page.locator("#f-busca"))
    .toHaveAttribute("placeholder", /papel A4/);
  // "só com preço fechado" vem ligado: o item sem resultado não aparece
  await expect(page.locator(".linha:not(.cab)")).toHaveCount(3);
  await expect(page.locator(".linha:not(.cab)").first())
    .toContainText("PAPEL SULFITE");
  // resumo estatístico aparece ao buscar
  await expect(page.locator("#precos-resumo")).toBeHidden();
  await page.locator("#f-busca").fill("papel");
  await expect(page.locator("#precos-resumo")).toBeVisible();
  await expect(page.locator("#precos-resumo")).toContainText("mediana");
  await expect(page.locator("#precos-resumo")).toContainText("18,75");
  // desmarcar traz também o item sem preço fechado
  await page.locator("#f-homologados").uncheck();
  await expect(page.locator(".linha:not(.cab)")).toHaveCount(4);
});

test("colunas da aba Preços cabem sem quebrar nem truncar",
    async ({ page }) => {
  await page.setViewportSize({ width: 1100, height: 800 });
  await page.locator('nav.abas button[data-tipo="itens"]').click();
  await expect(page.locator(".linha:not(.cab)")).toHaveCount(3);
  const medidas = await page.evaluate(() => {
    const fora = [];
    document.querySelectorAll(".linha").forEach((linha, iLinha) => {
      [...linha.children].forEach((cel, i) => {
        if (i === 0) return;                     // descrição pode quebrar
        const uma = parseFloat(getComputedStyle(cel).lineHeight) || 18;
        if (cel.scrollHeight > uma * 1.6)
          fora.push({ iLinha, i, motivo: "quebrou", txt: cel.textContent.trim() });
        if (cel.scrollWidth > cel.clientWidth + 1)
          fora.push({ iLinha, i, motivo: "truncou", txt: cel.textContent.trim() });
      });
    });
    return fora;
  });
  expect(medidas).toEqual([]);
});

test("resumo de preços abre o relatório com o termo preenchido",
    async ({ page }) => {
  await page.locator('nav.abas button[data-tipo="itens"]').click();
  await page.locator("#f-busca").fill("papel");
  await page.locator("#btn-rel-precos").click();
  await expect(page.locator("#veu-relatorios")).toBeVisible();
  await expect(page.locator("#rel-tipo")).toHaveValue("precos");
  await expect(page.locator("#rel-termo")).toHaveValue("papel");
});

test("valor sem homologação é marcado como estimado", async ({ page }) => {
  const linhas = page.locator(".linha:not(.cab)");
  // X-1 tem homologado: valor limpo, sem marca
  await expect(linhas.nth(0).locator(".est")).toHaveCount(0);
  // X-2 só tem estimado: itálico + "est."
  await expect(linhas.nth(1).locator(".est")).toContainText("est.");
  await expect(linhas.nth(1).locator(".est")).toContainText("200.000,00");
});

test("badge de situação encurtada mantém o texto completo no title",
    async ({ page }) => {
  const badge = page.locator(".linha:not(.cab)").nth(1).locator(".badge");
  await expect(badge).toHaveText("Divulgada");
  await expect(badge).toHaveAttribute("title", "Divulgada no PNCP");
});

test("limpar filtros aparece com filtro ativo e restaura a lista",
    async ({ page }) => {
  await expect(page.locator("#btn-limpar")).toBeHidden();
  await page.locator("#f-busca").fill("merenda");
  await expect(page.locator("#btn-limpar")).toBeVisible();
  await page.locator("#btn-limpar").click();
  await expect(page.locator("#f-busca")).toHaveValue("");
  await expect(page.locator("#btn-limpar")).toBeHidden();
});

test("selo, título da janela e última sincronização no rodapé",
    async ({ page }) => {
  await expect(page.locator("#svg-selo polygon").first()).toBeVisible();
  const titulo = await page.evaluate(() =>
    window.__chamadas.find(c => c.metodo === "set_titulo"));
  expect(titulo.t).toBe("Licitarium — Orindiúva/SP");
  await expect(page.locator("#sync-msg")).toContainText("Sincronizado");
});

test("densidade compacta aplica e persiste", async ({ page }) => {
  await page.locator("#btn-config").click();
  await page.locator("#cfg-densidade").selectOption("compacta");
  await expect(page.locator("html"))
    .toHaveAttribute("data-densidade", "compacta");
  const salvo = await page.evaluate(() => window.__chamadas.find(
    c => c.metodo === "set_config" && c.k === "densidade"));
  expect(salvo.v).toBe("compacta");
});

test("modal trava o fundo, recebe foco e prende o Tab", async ({ page }) => {
  await page.locator("#btn-relatorios").click();
  await expect(page.locator("body")).toHaveClass(/travado/);
  // foco entrou no diálogo
  expect(await page.evaluate(() =>
    document.querySelector("#veu-relatorios").contains(document.activeElement)))
    .toBe(true);
  // Tab circula dentro do diálogo, nunca volta para o fundo
  for (let i = 0; i < 12; i++) await page.keyboard.press("Tab");
  expect(await page.evaluate(() =>
    document.querySelector("#veu-relatorios").contains(document.activeElement)))
    .toBe(true);
  await page.keyboard.press("Escape");
  await expect(page.locator("body")).not.toHaveClass(/travado/);
});

test("tamanho da fonte aplica zoom e persiste", async ({ page }) => {
  await page.locator("#btn-config").click();
  await page.locator("#cfg-fonte").selectOption("grande");
  await expect(page.locator("html")).toHaveAttribute("data-fonte", "grande");
  const salvo = await page.evaluate(() =>
    window.__chamadas.find(c => c.metodo === "set_config" && c.k === "fonte"));
  expect(salvo.v).toBe("grande");
});

test("limites de dispensa usam máscara de dinheiro e salvam número puro",
    async ({ page }) => {
  await page.locator("#btn-config").click();
  const campo = page.locator("#cfg-lim-compras");
  await expect(campo).toHaveValue(/R\$/);            // carrega formatado
  await campo.fill("7500000");                        // digita só dígitos
  await expect(campo).toHaveValue(/75\.000,00/);      // exibe mascarado
  await page.keyboard.press("Tab");                   // dispara change
  const salvo = await page.evaluate(() =>
    window.__chamadas.filter(c => c.metodo === "set_config"
      && c.k === "limite_dispensa_compras").pop());
  expect(parseFloat(salvo.v)).toBe(75000);            // persiste numérico
});

test("chip de vencimento navega para contratos vigentes", async ({ page }) => {
  await page.locator("#chip-vencendo").click();
  await expect(page.locator('nav.abas button[data-tipo="contratos"]'))
    .toHaveClass(/on/);
  await expect(page.locator("#f-vigentes")).toBeChecked();
});
