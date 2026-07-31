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
  await expect(page.locator(".linha:not(.cab)")).toHaveCount(4);
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
  await expect(page.locator(".linha:not(.cab)")).toHaveCount(5);
});

test("colunas da aba Preços: nada quebra e o nome típico cabe inteiro",
    async ({ page }) => {
  await page.setViewportSize({ width: 1100, height: 800 });
  await page.locator('nav.abas button[data-tipo="itens"]').click();
  await expect(page.locator(".linha:not(.cab)")).toHaveCount(4);
  const m = await page.evaluate(() => {
    const quebrou = [], truncou = [];
    document.querySelectorAll(".linha:not(.cab)").forEach(linha => {
      [...linha.children].forEach((cel, i) => {
        if (i === 0) return;                     // descrição pode quebrar
        const uma = parseFloat(getComputedStyle(cel).lineHeight) || 18;
        const txt = cel.textContent.trim();
        if (cel.scrollHeight > uma * 1.6) quebrou.push(txt);
        if (cel.scrollWidth > cel.clientWidth + 1) truncou.push(txt);
      });
    });
    return { quebrou, truncou };
  });
  expect(m.quebrou).toEqual([]);                 // nunca quebra linha
  // razão social gigante (105 chars) corta com reticências; o resto cabe
  expect(m.truncou.length).toBe(1);
  expect(m.truncou[0]).toContain("COOPERATIVA");
  // sufixo societário sai do nome exibido, íntegro no title
  const forn = page.locator(".linha:not(.cab)").nth(2).locator("span").nth(4);
  await expect(forn).toHaveText("CENTRAL HOLDING LOGISTICA");
  await expect(forn).toHaveAttribute("title", "CENTRAL HOLDING LOGISTICA LTDA");
});

test("arrastar a alça redimensiona a coluna e persiste", async ({ page }) => {
  await page.setViewportSize({ width: 1100, height: 800 });
  await page.locator('nav.abas button[data-tipo="itens"]').click();
  const larguraDe = i => page.evaluate(n => parseFloat(
    getComputedStyle(document.querySelector(".lista .cab"))
      .gridTemplateColumns.split(" ")[n]), i);
  const antes = await larguraDe(4);                 // coluna Fornecedor
  const alca = page.locator(".cab > span").nth(4).locator(".alca");
  const cx = await alca.boundingBox();
  await page.mouse.move(cx.x + cx.width / 2, cx.y + cx.height / 2);
  await page.mouse.down();
  await page.mouse.move(cx.x + cx.width / 2 + 40, cx.y + cx.height / 2,
                        { steps: 5 });
  await page.mouse.up();
  const depois = await larguraDe(4);
  expect(depois).toBeGreaterThan(antes + 30);
  // a coluna elástica cedeu espaço, mas não abaixo do mínimo
  expect(await larguraDe(0)).toBeGreaterThanOrEqual(160);
  // largura salva para voltar na próxima abertura
  const salvo = await page.evaluate(() => window.__chamadas.filter(
    c => c.metodo === "set_config" && c.k === "colunas").pop());
  expect(JSON.parse(salvo.v).itens[4]).toBeGreaterThan(antes + 30);
  // ordenação não dispara ao arrastar sobre o cabeçalho
  const chamadas = await page.evaluate(() => window.__chamadas.filter(
    c => c.metodo === "listar" && c.filtros && c.filtros.ord));
  expect(chamadas).toEqual([]);
});

test("duplo clique na alça ajusta a coluna ao conteúdo (autofit)",
    async ({ page }) => {
  await page.setViewportSize({ width: 1100, height: 800 });
  await page.locator('nav.abas button[data-tipo="itens"]').click();
  const cortado = txt => page.evaluate(t => {
    const c = [...document.querySelectorAll(".lista .linha:not(.cab)")]
      .map(l => l.children[4]).find(e => e.textContent.includes(t));
    return c.scrollWidth > c.clientWidth + 1;
  }, txt);
  // encolhe a coluna a ponto de cortar até um nome curto
  await page.evaluate(() => {
    larguras.itens = { 1:52, 2:74, 3:124, 4:90, 5:78 };
    aplicarLarguras("itens");
  });
  expect(await cortado("ZILDA")).toBe(true);
  await page.locator(".cab > span").nth(4).locator(".alca").dblclick();
  expect(await cortado("ZILDA")).toBe(false);        // autofit recuperou
  // e a coluna elástica não foi engolida pelo nome gigante
  const flex = await page.evaluate(() => parseFloat(
    getComputedStyle(document.querySelector(".lista .cab"))
      .gridTemplateColumns.split(" ")[0]));
  expect(flex).toBeGreaterThanOrEqual(160);
  // ordenação não foi disparada pelos cliques do duplo clique
  const ord = await page.evaluate(() => window.__chamadas.filter(
    c => c.metodo === "listar" && c.filtros && c.filtros.ord));
  expect(ord).toEqual([]);
});

test("restaurar larguras volta ao padrão", async ({ page }) => {
  await page.locator('nav.abas button[data-tipo="itens"]').click();
  await page.locator(".cab > span").nth(4).locator(".alca").dblclick();
  await expect(page.locator("#lista")).toHaveAttribute("style", /--cols/);
  await page.locator("#btn-config").click();
  await page.locator("#btn-restaurar-colunas").click();
  const style = await page.locator("#lista").getAttribute("style");
  expect(style || "").not.toContain("--cols");
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

test("abrir maximizada vem ligada e persiste ao desmarcar",
    async ({ page }) => {
  await page.locator("#btn-config").click();
  await expect(page.locator("#cfg-maximizar")).toBeChecked();
  await page.locator("#cfg-maximizar").uncheck();
  const salvo = await page.evaluate(() => window.__chamadas.find(
    c => c.metodo === "set_config" && c.k === "maximizar"));
  expect(salvo.v).toBe("0");
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
