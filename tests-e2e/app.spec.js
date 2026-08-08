const { test, expect } = require("@playwright/test");
const { abrirApp, abrirLista } = require("./harness");

test.beforeEach(async ({ page }) => abrirApp(page));

test.describe("splash", () => {
  test.use({ }); // testes que precisam da splash antes do app pronto

  test("aparece no tema da URL e some quando o acervo abre",
      async ({ page }) => {
    // já montada pelo beforeEach: some sozinha ao fim do carregamento
    // sem timeout próprio: o global (10s) existe justamente porque o
    // primeiro teste do CI paga o aquecimento da máquina — com 5s aqui,
    // este assert já falhou em run frio enquanto passava em 1,8s local
    await expect(page.locator("#splash")).toHaveCount(0);
  });

  test("sem tema.js (reserva): assume o do banco e remonta a splash",
      async ({ page }) => {
    // cenário de fallback — o arquivo do Python não chegou; a splash nasce
    // no padrão e é remontada quando o tema do banco é lido
    // sem tema.js algum: cenário de reserva
    await page.route("**/tema.js", r => r.fulfill({ status: 404, body: "" }));
    await page.addInitScript(() => {
      delete window.__TEMA;
      try { localStorage.clear(); } catch {}
    });
    await abrirApp(page, { temaBanco: "pergaminho" });
    await expect(page.locator("#splash .cx.diploma")).toBeVisible();
    await expect(page.locator("html"))
      .toHaveAttribute("data-theme", "pergaminho");
    // e fica guardado para a próxima abertura já nascer certa
    expect(await page.evaluate(() => localStorage.getItem("tema")))
      .toBe("pergaminho");
  });

  for (const [tema, marca] of [["portal", ".cx"],
                               ["pergaminho", ".cx.diploma"],
                               ["observatorio", ".anel .giro"]]) {
    test(`composição do tema ${tema}`, async ({ page }) => {
      // serve o tema.js como o Python o escreve (interceptar o arquivo, e
      // não injetar a variável: o próprio arquivo do app a sobrescreveria)
      await page.route("**/tema.js", r =>
        r.fulfill({ contentType: "application/javascript",
                    body: `window.__TEMA = "${tema}";` }));
      await page.goto(require("./harness").URL_UI);
      await expect(page.locator("#splash")).toBeVisible();
      await expect(page.locator(`#splash ${marca}`)).toBeVisible();
      await expect(page.locator("html")).toHaveAttribute("data-theme", tema);
    });
  }
});

test("boot: app abre com município, KPIs e alertas", async ({ page }) => {
  await expect(page.locator("#app")).toBeVisible();
  await expect(page.locator("#wizard")).toBeHidden();
  await expect(page.locator("#sub-municipio"))
    .toContainText("Orindiúva · SP");
  await expect(page.locator("#kpi-contratacoes")).toHaveText("131");
  // contrato e ata são alertas separados — cada um vai a uma tela diferente
  await expect(page.locator("#chip-vencendo-contratos")).toContainText("7");
  await expect(page.locator("#chip-vencendo-atas")).toContainText("2");
  await expect(page.locator("#chip-propostas")).toContainText("2");
});

test("lista renderiza e ordenação por clique manda ord/dir à ponte",
    async ({ page }) => {
  await abrirLista(page);   // a tela inicial agora é o Painel
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

test("fileira de filtros tem folga vertical maior que a horizontal",
    async ({ page }) => {
  // achado da auditoria de design (2026-08-08): quando a barra quebra em
  // duas linhas (Contratações, Preços — muitos filtros), a segunda linha
  // colava na primeira e parecia um acidente de largura, não uma fileira
  // deliberada. row-gap maior que column-gap separa as duas visualmente.
  await abrirLista(page, "contratacoes");
  const gap = await page.locator("#filtros-lista").evaluate(el => {
    const s = getComputedStyle(el);
    return { linha: parseFloat(s.rowGap), coluna: parseFloat(s.columnGap) };
  });
  expect(gap.linha).toBeGreaterThan(gap.coluna);
});

test("checkbox de filtro tem alvo de clique maior que a linha de texto",
    async ({ page }) => {
  // achado da auditoria de design (2026-08-08): a área clicável seguia a
  // altura da linha de texto (13px de fonte, ~16-18px de área) — não é
  // bloqueio WCAG AA (alvo de 44px é AAA), mas incomodava no trackpad
  await abrirLista(page, "contratacoes");
  const altura = await page.locator("#cx-propostas").evaluate(
    el => el.getBoundingClientRect().height);
  expect(altura).toBeGreaterThanOrEqual(24);
});

test("fornecedor da lista de contratos carrega o nome completo no title",
    async ({ page }) => {
  // achado da auditoria de design (2026-08-08) — mesmo padrão do Painel
  await page.locator('nav.abas button[data-tipo="contratos"]').click();
  // .dim aparece 3x por linha (nº do contrato, fornecedor, vigência) — o
  // fornecedor é o segundo, dentro do mesmo span que o objeto
  const fornecedor = page.locator(".linha:not(.cab)").first()
    .locator(".dim").nth(1);
  await expect(fornecedor).toHaveAttribute("title",
    "DANILO HENRIQUE NUNES CONSULTORIA");
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
  // (4 do município + 1 de referência)
  await expect(page.locator(".linha:not(.cab)")).toHaveCount(5);
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
  await expect(page.locator(".linha:not(.cab)")).toHaveCount(6);
});

test("colunas da aba Preços: nada quebra e o nome típico cabe inteiro",
    async ({ page }) => {
  await page.setViewportSize({ width: 1100, height: 800 });
  await page.locator('nav.abas button[data-tipo="itens"]').click();
  await expect(page.locator(".linha:not(.cab)")).toHaveCount(5);
  const m = await page.evaluate(() => {
    const quebrou = [], truncou = [];
    document.querySelectorAll(".linha:not(.cab)").forEach(linha => {
      [...linha.children].forEach((cel, i) => {
        if (i <= 1) return;      // 0 = seleção; 1 = descrição, pode quebrar
        // preço de município de referência leva a origem numa 2ª linha,
        // de propósito: é o que distingue a série própria da de fora
        if (cel.querySelector(".de-fora")) return;
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
  const forn = page.locator(".linha:not(.cab)").nth(2).locator("span").nth(5);
  await expect(forn).toHaveText("CENTRAL HOLDING LOGISTICA");
  await expect(forn).toHaveAttribute("title", "CENTRAL HOLDING LOGISTICA LTDA");
});

test("arrastar a alça redimensiona a coluna e persiste", async ({ page }) => {
  await page.setViewportSize({ width: 1100, height: 800 });
  await page.locator('nav.abas button[data-tipo="itens"]').click();
  const larguraDe = i => page.evaluate(n => parseFloat(
    getComputedStyle(document.querySelector(".lista .cab"))
      .gridTemplateColumns.split(" ")[n]), i);
  const antes = await larguraDe(5);                 // coluna Fornecedor
  const alca = page.locator(".cab > span").nth(5).locator(".alca");
  const cx = await alca.boundingBox();
  await page.mouse.move(cx.x + cx.width / 2, cx.y + cx.height / 2);
  await page.mouse.down();
  await page.mouse.move(cx.x + cx.width / 2 + 40, cx.y + cx.height / 2,
                        { steps: 5 });
  await page.mouse.up();
  const depois = await larguraDe(5);
  expect(depois).toBeGreaterThan(antes + 30);
  // a coluna elástica cedeu espaço, mas não abaixo do mínimo
  expect(await larguraDe(1)).toBeGreaterThanOrEqual(160);
  // largura salva para voltar na próxima abertura
  const salvo = await page.evaluate(() => window.__chamadas.filter(
    c => c.metodo === "set_config" && c.k === "colunas").pop());
  expect(JSON.parse(salvo.v).itens[5]).toBeGreaterThan(antes + 30);
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
      .map(l => l.children[5]).find(e => e.textContent.includes(t));
    return c.scrollWidth > c.clientWidth + 1;
  }, txt);
  // encolhe a coluna a ponto de cortar até um nome curto
  await page.evaluate(() => {
    larguras.itens = { 0:30, 2:52, 3:64, 4:124, 5:90, 6:100, 7:72 };
    aplicarLarguras("itens");
  });
  expect(await cortado("ZILDA")).toBe(true);
  await page.locator(".cab > span").nth(5).locator(".alca").dblclick();
  expect(await cortado("ZILDA")).toBe(false);        // autofit recuperou
  // e a coluna elástica não foi engolida pelo nome gigante
  // (índice 1: a 0 é a caixa de seleção da pesquisa)
  const flex = await page.evaluate(() => parseFloat(
    getComputedStyle(document.querySelector(".lista .cab"))
      .gridTemplateColumns.split(" ")[1]));
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

test("montador de PCA gera, edita e recalcula os totais", async ({ page }) => {
  await page.locator("#btn-pca").click();
  await expect(page.locator("#veu-pca")).toBeVisible();
  // exercício sugerido é o ano seguinte ao último com itens (2026 -> 2027)
  await expect(page.locator("#pca-ano")).toHaveValue("2027");
  await page.locator("#pca-gerar").click();
  await expect(page.locator("#pca-status")).toContainText("3 grupos");
  const linhas = page.locator("#pca-lista .linha:not(.cab)");
  await expect(linhas).toHaveCount(3);
  // sinalizações que orientam a revisão
  await expect(linhas.nth(0).locator(".aviso-un")).toBeVisible();
  await expect(linhas.nth(1).locator(".tag-unico")).toContainText("ÚNICA");
  await expect(page.locator("#pca-totais")).toContainText("525.000,00");
  // editar a quantidade recalcula o total
  await linhas.nth(0).locator('[data-campo="quantidade"]').fill("300");
  await linhas.nth(0).locator('[data-campo="quantidade"]').blur();
  await expect(page.locator("#pca-totais")).toContainText("533.000,00");
  // excluir um item sai da conta e é contado como excluído
  await linhas.nth(1).locator('[data-campo="incluir"]').uncheck();
  await expect(page.locator("#pca-totais")).toContainText("1 excluído");
  const chamadas = await page.evaluate(() => window.__chamadas.filter(
    c => c.metodo === "editar_item_minuta"));
  expect(chamadas.map(c => c.campos)).toEqual([
    { quantidade: 300 }, { incluir: 0 }]);
});

test("PCA: famílias filtram, ABC classifica e mesclagem funde itens",
    async ({ page }) => {
  await page.locator("#btn-pca").click();
  await page.locator("#pca-gerar").click();
  const linhas = page.locator("#pca-lista .linha:not(.cab)");
  await expect(linhas).toHaveCount(3);
  // curva ABC destacada e resumida no topo
  await expect(linhas.nth(0).locator(".abc")).toHaveText("B");
  await expect(page.locator("#pca-totais")).toContainText("classe A");
  // chips por família: FILTRO tem 2 itens
  const chipFiltro = page.locator('#pca-familias button[data-familia="FILTRO"]');
  await expect(chipFiltro).toContainText("2");
  await chipFiltro.click();
  await expect(linhas).toHaveCount(2);
  await page.locator('#pca-familias button[data-familia=""]').click();
  await expect(linhas).toHaveCount(3);
  // mesclar exige dois: o botão só habilita a partir do segundo
  await expect(page.locator("#pca-mesclar")).toBeDisabled();
  await linhas.nth(0).locator("[data-sel]").check();
  await expect(page.locator("#pca-mesclar")).toBeDisabled();
  await linhas.nth(2).locator("[data-sel]").check();
  await expect(page.locator("#pca-mesclar")).toContainText("2 itens");
  await page.locator("#pca-mesclar").click();
  await expect(page.locator("#pca-status")).toContainText("fundidos");
  await expect(linhas).toHaveCount(2);
  // o item fundido oferece desfazer
  await expect(page.locator("[data-dividir]")).toBeVisible();
  await page.locator("[data-dividir]").click();
  await expect(page.locator("#pca-status")).toContainText("desfeita");
});

test("modal do PCA ocupa a janela e a descrição tem espaço", async ({ page }) => {
  await page.setViewportSize({ width: 1600, height: 900 });
  await page.locator("#btn-pca").click();
  await page.locator("#pca-gerar").click();
  await expect(page.locator("#pca-lista .linha:not(.cab)")).toHaveCount(3);
  const m = await page.evaluate(() => {
    const modal = document.querySelector("#veu-pca .modal");
    const desc = document.querySelector(
      '#pca-lista .linha:not(.cab) [data-campo="descricao"]');
    return { modal: modal.clientWidth, janela: window.innerWidth,
             descricao: desc.clientWidth };
  });
  expect(m.modal).toBeGreaterThan(m.janela * 0.9);   // usa a janela toda
  expect(m.descricao).toBeGreaterThan(700);          // nome do item legível
});

test("parâmetros do PCA chegam ao motor", async ({ page }) => {
  await page.locator("#btn-pca").click();
  await page.locator("#pca-base").selectOption("ultimo");
  await page.locator("#pca-estatistica").selectOption("recente");
  await page.locator("#pca-margem").fill("25");
  await page.locator("#pca-palavras").selectOption("2");
  await page.locator("#pca-recorrentes").uncheck();
  await page.locator("#pca-gerar").click();
  const c = await page.evaluate(() => window.__chamadas.find(
    x => x.metodo === "gerar_minuta_pca"));
  expect(c.params).toEqual({ base: "ultimo", estatistica: "recente",
                             margem: 25, palavras: 2, so_recorrentes: false });
});

test("valor sem homologação é marcado como estimado", async ({ page }) => {
  await abrirLista(page);   // a tela inicial agora é o Painel
  const linhas = page.locator(".linha:not(.cab)");
  // X-1 tem homologado: valor limpo, sem marca
  await expect(linhas.nth(0).locator(".est")).toHaveCount(0);
  // X-2 só tem estimado: itálico + "est."
  await expect(linhas.nth(1).locator(".est")).toContainText("est.");
  await expect(linhas.nth(1).locator(".est")).toContainText("200.000,00");
});

test("badge de situação encurtada mantém o texto completo no title",
    async ({ page }) => {
  await abrirLista(page);   // a tela inicial agora é o Painel
  const badge = page.locator(".linha:not(.cab)").nth(1).locator(".badge");
  await expect(badge).toHaveText("Divulgada");
  await expect(badge).toHaveAttribute("title", "Divulgada no PNCP");
});

test("limpar filtros aparece com filtro ativo e restaura a lista",
    async ({ page }) => {
  await abrirLista(page);   // a tela inicial agora é o Painel
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

test("chip de vencimento de contratos filtra pela janela de 60 dias, não por vigentes",
    async ({ page }) => {
  // "vigentes" não tem teto — todo contrato ativo entrava, e o alerta de
  // 25 virava lista de 50. O chip tem de ligar a caixa da janela fechada.
  await abrirLista(page);   // a tela inicial agora é o Painel
  await page.locator("#chip-vencendo-contratos").click();
  await expect(page.locator('nav.abas button[data-tipo="contratos"]'))
    .toHaveClass(/on/);
  await expect(page.locator("#f-vence60")).toBeChecked();
  await expect(page.locator("#f-vigentes")).not.toBeChecked();
  const chamada = await page.evaluate(() => window.__chamadas
    .filter(c => c.metodo === "listar").pop());
  expect(chamada.tipo).toBe("contratos");
  expect(chamada.filtros.vencendo).toBe(true);
  expect(chamada.filtros.vigentes).toBeNull();
});

test("chip de vencimento de atas leva à aba de atas, não à de contratos",
    async ({ page }) => {
  // Um alerta que soma contrato e ata não tem como abrir as duas telas de
  // uma vez — por isso são dois chips, cada um levando à tela certa.
  await abrirLista(page);
  await page.locator("#chip-vencendo-atas").click();
  await expect(page.locator('nav.abas button[data-tipo="atas"]'))
    .toHaveClass(/on/);
  const chamada = await page.evaluate(() => window.__chamadas
    .filter(c => c.metodo === "listar").pop());
  expect(chamada.tipo).toBe("atas");
  expect(chamada.filtros.vencendo).toBe(true);
});

test("contratos e atas mostram a situação da vigência por cor e texto",
    async ({ page }) => {
  for (const [aba, esperado] of [
      ["contratos", [["ok", "Vigente"], ["warn", /Vence em \d+ d/],
                     ["err", "Encerrado"]]],
      ["atas", [["ok", "Vigente"], ["warn", /Vence em \d+ d/],
                ["err", "Encerrado"]]]]) {
    await page.locator(`nav.abas button[data-tipo="${aba}"]`).click();
    const selos = page.locator(".linha:not(.cab) .badge");
    await expect(selos).toHaveCount(3);
    for (const [i, [classe, texto]] of esperado.entries()) {
      await expect(selos.nth(i)).toHaveClass(new RegExp(`badge ${classe}$`));
      await expect(selos.nth(i)).toHaveText(texto);
      // cor não pode ser o único indicador (WCAG 1.4.1): o title carrega a data
      await expect(selos.nth(i)).toHaveAttribute("title", /Vigência até \d{2}\//);
    }
  }
});

test("situação da vigência não escorrega de dia por causa do fuso",
    async ({ page }) => {
  // `new Date("2026-01-01")` é meia-noite UTC e, no nosso fuso, cai no dia
  // anterior — o que faria um contrato que vence hoje aparecer como encerrado
  const r = await page.evaluate(() => {
    const d = new Date();
    const iso = x => `${x.getFullYear()}-${String(x.getMonth() + 1)
      .padStart(2, "0")}-${String(x.getDate()).padStart(2, "0")}`;
    const mais = n => { const y = new Date(); y.setDate(y.getDate() + n); return iso(y); };
    return {
      hoje: window.statusVigencia(iso(d)),
      ontem: window.statusVigencia(mais(-1)),
      amanha: window.statusVigencia(mais(1)),
      limite: window.statusVigencia(mais(60)),
      passouDoLimite: window.statusVigencia(mais(61)),
      semData: window.statusVigencia(null),
      comHora: window.statusVigencia(`${mais(5)}T00:00:00`),
    };
  });
  expect(r.hoje).toEqual({ cl: "warn", txt: "Vence hoje" });
  expect(r.ontem.cl).toBe("err");
  expect(r.amanha).toEqual({ cl: "warn", txt: "Vence em 1 d" });
  expect(r.limite.cl).toBe("warn");        // 60 dias ainda alerta
  expect(r.passouDoLimite.cl).toBe("ok");  // 61 já é rotina
  expect(r.semData).toBeNull();            // registro sem vigência: sem selo
  expect(r.comHora.cl).toBe("warn");       // tolera timestamp completo
});

test("selos de situação atingem o contraste AA nos três temas",
    async ({ page }) => {
  for (const tema of ["portal", "pergaminho", "observatorio"]) {
    await abrirApp(page, { tema, temaBanco: tema });
    await page.locator('nav.abas button[data-tipo="contratos"]').click();
    const medidas = await page.evaluate(() => {
      // o navegador devolve color-mix como `color(srgb r g b / a)`, com
      // componentes de 0 a 1 — e não como rgb() de 0 a 255
      const cor = s => {
        const n = (s.match(/[\d.]+/g) || []).map(Number);
        const srgb = s.startsWith("color(");
        const [r, g, b] = srgb ? n.slice(0, 3).map(v => v * 255) : n.slice(0, 3);
        const a = srgb ? (n[3] ?? 1) : (n[3] ?? 1);
        return { rgb: [r, g, b], a };
      };
      // fundo do selo é translúcido: compõe até achar algo opaco atrás
      const fundoOpaco = el => {
        for (let e = el; e; e = e.parentElement) {
          const c = cor(getComputedStyle(e).backgroundColor);
          if (c.a === 1) return c.rgb;
        }
        return [255, 255, 255];
      };
      const lum = ([r, g, b]) => {
        const f = v => (v /= 255) <= 0.03928 ? v / 12.92
          : Math.pow((v + 0.055) / 1.055, 2.4);
        return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
      };
      return [...document.querySelectorAll(".linha:not(.cab) .badge")].map(b => {
        const e = getComputedStyle(b);
        const selo = cor(e.backgroundColor), atras = fundoOpaco(b.parentElement);
        const fundo = selo.rgb.map((v, i) => v * selo.a + atras[i] * (1 - selo.a));
        const [hi, lo] = [lum(cor(e.color).rgb), lum(fundo)].sort((x, y) => y - x);
        return { classe: b.className, razao: (hi + 0.05) / (lo + 0.05) };
      });
    });
    expect(medidas.length).toBe(3);
    // AA para texto pequeno: 4.5:1 (o selo tem 10,5px)
    const reprovados = medidas.filter(m => m.razao < 4.5)
      .map(m => `${tema}/${m.classe} = ${m.razao.toFixed(2)}`);
    expect(reprovados).toEqual([]);
  }
});

test("selo de vigência: centralizado na célula e com respiro da data",
    async ({ page }) => {
  await page.setViewportSize({ width: 1300, height: 900 });
  for (const aba of ["contratos", "atas"]) {
    await page.locator(`nav.abas button[data-tipo="${aba}"]`).click();
    const m = await page.evaluate(() =>
      [...document.querySelectorAll(".linha:not(.cab)")].map(l => {
        const cel = l.querySelector(".vig");
        const selo = cel.querySelector(".badge");
        const rc = cel.getBoundingClientRect(), rs = selo.getBoundingClientRect();
        const rl = l.getBoundingClientRect();
        return {
          alturaLinha: rl.height,
          // quanto o centro da célula desvia do centro da linha
          desvioCentro: Math.abs((rc.top + rc.height / 2)
                                 - (rl.top + rl.height / 2)),
          // respiro entre as datas e o selo, e selo em bloco próprio
          respiro: parseFloat(getComputedStyle(selo).marginTop),
          seloEmBloco: getComputedStyle(selo).display === "block",
          // o selo não encosta nas bordas: fica centralizado sob as datas
          centradoNaCelula: Math.abs((rs.left + rs.width / 2)
                                     - (rc.left + rc.width / 2)) <= 2,
        };
      }));
    expect(m.length).toBe(3);
    // uma das linhas tem objeto longo: é onde o alinhamento aparecia errado
    expect(Math.max(...m.map(x => x.alturaLinha))).toBeGreaterThan(90);
    for (const x of m) {
      expect(x.desvioCentro).toBeLessThanOrEqual(2);   // centralizado
      expect(x.respiro).toBeGreaterThanOrEqual(4);     // com espaçamento
      expect(x.seloEmBloco).toBe(true);
      expect(x.centradoNaCelula).toBe(true);
    }
  }
});

test("municípios de referência: lista, adiciona e remove", async ({ page }) => {
  await page.locator("#btn-config").click();
  const secao = page.locator("#cfg-referencia");
  await expect(secao).toContainText("Palestina");
  await expect(secao).toContainText("812 preços");
  // quanto o município pesa no arquivo: quem decide remover precisa saber
  await expect(secao).toContainText("ocupa ~4,6 MB");

  // adicionar pelo autocomplete (o volume da coleta é confirmado antes —
  // ver tests-e2e/volume.spec.js)
  page.once("dialog", d => d.accept());
  await page.locator("#ref-busca").fill("paulo");
  await page.locator('#ref-sugestoes button[data-c="3536604"]').click();
  const enviado = await page.evaluate(() => window.__chamadas
    .filter(c => c.metodo === "adicionar_municipio_referencia").pop());
  expect(enviado.n).toBe("Paulo de Faria");
  await expect(secao).toContainText("Paulo de Faria");
  // o usuário precisa saber que os preços ainda não chegaram
  await expect(page.locator("#sync-msg"))
    .toContainText("chegam na próxima sincronização");

  // remover pede confirmação e leva os dados junto
  page.once("dialog", d => {
    expect(d.message()).toContain("Palestina");
    expect(d.message()).toContain("saem do banco");
    d.accept();
  });
  await page.locator('#cfg-referencia button[data-remover="3535002"]').click();
  await expect(secao).not.toContainText("Palestina");
  await expect(secao).toContainText("Paulo de Faria");
});

test("municípios de referência: seletor de ordem reordena a lista",
    async ({ page }) => {
  // pedido do usuário (2026-08-08): tamanho é o padrão, mas nome e nº de
  // preços também precisam estar disponíveis — nomes escolhidos de propósito
  // pra que ordem alfabética, por tamanho e por nº de preços discordem
  await page.evaluate(() => {
    window.__referencia = [
      { ibge: "1", nome: "Zeta", uf: "SP", itens: 5,   mb: 20 },
      { ibge: "2", nome: "Alfa", uf: "SP", itens: 50,  mb: 1 },
      { ibge: "3", nome: "Meia", uf: "SP", itens: 500, mb: 8 },
    ];
  });
  await page.locator("#btn-config").click();
  const nomes = () => page.locator("#cfg-referencia .orgrow")
    .evaluateAll(els => els.map(el => el.querySelector("span")
      .firstChild.textContent.trim().replace(" — SP", "")));

  // as três ordens dão as três permutações abaixo, de propósito — se uma
  // reordenação virar no-op ou copiar outro critério, o teste morde
  await expect(page.locator("#ref-ordem")).toHaveValue("tamanho");
  expect(await nomes()).toEqual(["Zeta", "Meia", "Alfa"]);      // 20 > 8 > 1

  await page.locator("#ref-ordem").selectOption("nome");
  expect(await nomes()).toEqual(["Alfa", "Meia", "Zeta"]);      // A-Z

  await page.locator("#ref-ordem").selectOption("itens");
  expect(await nomes()).toEqual(["Meia", "Alfa", "Zeta"]);      // 500 > 50 > 5
});

test("aba Preços mostra a origem e permite ficar só com o município",
    async ({ page }) => {
  await page.locator('nav.abas button[data-tipo="itens"]').click();
  // a coluna Município existe sempre e vale para as duas origens
  await expect(page.locator(".cab")).toContainText("Município");
  // e é ordenável como as demais
  const cabMunicipio = page.locator('.cab span[data-ord="municipio"]');
  await cabMunicipio.click();
  await expect(cabMunicipio).toHaveAttribute("aria-sort", "ascending");
  expect((await page.evaluate(() => window.__chamadas
    .filter(c => c.metodo === "listar").pop())).filtros.ord).toBe("municipio");
  const municipios = page.locator(".linha:not(.cab) > span:nth-child(7)");
  await expect(municipios.first()).toHaveText("Orindiúva");
  const deFora = page.locator(".linha:not(.cab) .de-fora");
  await expect(deFora).toHaveCount(1);
  await expect(deFora).toHaveText("Palestina");
  await expect(deFora).toHaveAttribute("title", /município de referência/);
  // o item do próprio município não recebe etiqueta: seria ruído em todas
  await expect(page.locator(".linha:not(.cab)")).toHaveCount(5);

  // o resumo diz quanto do resultado é da própria série
  await page.locator("#f-busca").fill("papel");
  await expect(page.locator("#precos-resumo h3"))
    .toContainText("do seu município");

  // filtro de origem só aparece havendo referência, e funciona
  await expect(page.locator("#cx-so-meu")).toBeVisible();
  await page.locator("#f-so-meu").check();
  await expect(page.locator(".linha:not(.cab) .de-fora")).toHaveCount(0);
  const enviado = await page.evaluate(() => window.__chamadas
    .filter(c => c.metodo === "listar" && c.tipo === "itens").pop());
  expect(enviado.filtros.origem).toBe("proprio");
});

test("largura de coluna guardada antes de a aba mudar não quebra a lista",
    async ({ page }) => {
  await page.locator('nav.abas button[data-tipo="itens"]').click();
  // formato antigo: 6 colunas, sem a de Município
  await page.evaluate(() => {
    larguras.itens = { 1: 52, 2: 74, 3: 124, 4: 320, 5: 78 };
    aplicarLarguras("itens");
  });
  const cols = await page.evaluate(() => getComputedStyle(
    document.querySelector(".lista .cab")).gridTemplateColumns);
  // sem a guarda, a coluna que falta viraria "NaNpx" e o grid desabaria
  expect(cols).not.toContain("NaN");
  expect(cols.split(" ").length).toBe(8);
  // o mapa incompatível é descartado, e não reaplicado na próxima troca
  expect(await page.evaluate(() => larguras.itens)).toBeUndefined();
});

test("Compacta é metade da janela, Expandida é a janela inteira",
    async ({ page }) => {
  // pedido do usuário (2026-08-08): a lista tinha teto próprio em pixels
  // (m2: 1400px, depois 1600px) enquanto o <main> do Painel não tinha
  // nenhum — o usuário viu a inconsistência comparando os dois lado a
  // lado na mesma janela Expandida. Regra virou global e relativa: metade
  // da janela em Compacta, a janela inteira em Expandida, pro <main> e
  // pra lista igual — sem teto fixo escolhido a dedo. Piso de 1000px
  // (janela larga o bastante aqui pra não entrar em jogo).
  await page.setViewportSize({ width: 2400, height: 900 });
  const compacta = await page.locator("main").evaluate(
    el => el.getBoundingClientRect().width);
  expect(compacta).toBeCloseTo(1200, 0);           // 50vw de 2400px

  await page.evaluate(() => { document.documentElement.dataset.largura = "expandida"; });
  const mainExpandida = await page.locator("main").evaluate(
    el => el.getBoundingClientRect().width);
  expect(mainExpandida).toBeCloseTo(2400, 0);       // 100% da janela

  // a lista segue a mesma regra do main, sem teto próprio
  await abrirLista(page, "contratos");
  const listaExpandida = await page.locator("#lista").evaluate(
    el => el.getBoundingClientRect().width);
  expect(listaExpandida).toBeGreaterThan(2300);
});

test("filtros que mudam o cálculo se destacam dos que só filtram a lista",
    async ({ page }) => {
  // achado da auditoria (m3, 2026-08-08): "Corrigir pelo IPCA" e "Comparar
  // por conteúdo" trocam o resumo inteiro; "Só do meu município" só filtra
  // a lista — mesma aparência antes, sem hierarquia entre os dois grupos.
  await page.locator('nav.abas button[data-tipo="itens"]').click();
  const cores = await page.evaluate(() => ({
    corrigir: getComputedStyle($("cx-corrigir")).backgroundColor,
    conteudo: getComputedStyle($("cx-conteudo")).backgroundColor,
    soMeu: getComputedStyle($("cx-so-meu")).backgroundColor,
  }));
  expect(cores.corrigir).not.toBe(cores.soMeu);
  expect(cores.conteudo).not.toBe(cores.soMeu);
  expect(cores.corrigir).not.toMatch(/rgba\(0, 0, 0, 0\)|transparent/);
});
