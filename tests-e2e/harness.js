// Ponte pywebview mockada + dados de exemplo para os testes E2E e screenshots.
const path = require("path");

const URL_UI = "file://" +
  path.resolve(__dirname, "..", "ui", "index.html").replace(/\\/g, "/");

const DADOS = {
  contratacoes: [
    { numero_controle: "X-1", ano: 2026, sequencial: 12,
      modalidade_nome: "Dispensa", objeto: "Aquisição de gêneros alimentícios para merenda escolar",
      valor_estimado: 52000, valor_homologado: 48230,
      situacao: "Homologada", data_publicacao: "2026-03-14" },
    { numero_controle: "X-2", ano: 2026, sequencial: 4,
      modalidade_nome: "Pregão - Eletrônico", objeto: "Contratação de empresa para manutenção de vias públicas",
      valor_estimado: 200000, valor_homologado: null,
      situacao: "Divulgada no PNCP", data_publicacao: "2026-05-02" },
    { numero_controle: "X-3", ano: 2025, sequencial: 50,
      modalidade_nome: "Pregão - Eletrônico", objeto: "Registro de preços para medicamentos básicos",
      valor_estimado: 261115, valor_homologado: 261115,
      situacao: "Homologada", data_publicacao: "2025-11-20" },
  ],
  contratos: [
    { numero_controle: "Y-1", numero_contrato: "0033/26", ano_contrato: 2026,
      objeto: "Serviços de assessoria e consultoria técnica na área da educação",
      fornecedor_nome: "DANILO HENRIQUE NUNES CONSULTORIA",
      valor_global: 30294, vigencia_inicio: "2026-05-28",
      vigencia_fim: "2027-05-28", data_publicacao: "2026-07-13" },
  ],
  atas: [
    { numero_controle: "Z-1", numero_ata: "13", ano_ata: 2026,
      objeto: "Registro de preços de óleos lubrificantes para a frota",
      contratacao_controle: "45148970000177-1-000061/2025",
      vigencia_inicio: "2026-04-10", vigencia_fim: "2027-04-10" },
  ],
  pca: [],
  itens: [
    { id: "X-3#1", contratacao_controle: "X-3", ano: 2025, sequencial: 50,
      numero_item: 1, descricao: "PAPEL SULFITE A4 75G RESMA 500 FOLHAS",
      unidade: "RESMA", quantidade: 300, quantidade_homologada: 300,
      valor_unitario_estimado: 24.9, valor_unitario_homologado: 18.75,
      fornecedor_nome: "PAPELARIA CENTRAL LTDA",
      data_resultado: "2025-11-28" },
    // nomes e valores reais do acervo: a linha tem de caber sem quebrar
    { id: "X-3#9", contratacao_controle: "X-3", ano: 2025, sequencial: 43,
      numero_item: 9, descricao: "PÃO FRANCÊS 50G",
      unidade: "KG", quantidade: 9000, quantidade_homologada: 9000,
      valor_unitario_estimado: 30.0, valor_unitario_homologado: 26.8,
      fornecedor_nome: "ZILDA OLIVEIRA VIEIRA PANIFICADORA",
      data_resultado: "2025-09-15" },
    { id: "X-3#10", contratacao_controle: "X-3", ano: 2026, sequencial: 30,
      numero_item: 10, descricao: "CADEIRA DE RODAS REFORÇADA DOBRÁVEL",
      unidade: "UN", quantidade: 1, quantidade_homologada: 1,
      valor_unitario_estimado: 2100.0, valor_unitario_homologado: 635000.0,
      fornecedor_nome: "CENTRAL HOLDING LOGISTICA LTDA",
      data_resultado: "2026-07-02" },
    // pior caso real do acervo (105 chars): não cabe em coluna alguma,
    // serve para garantir que corta com reticências em vez de quebrar
    { id: "X-3#11", contratacao_controle: "X-3", ano: 2026, sequencial: 30,
      numero_item: 11, descricao: "SERVIÇO BANCÁRIO",
      unidade: "UN", quantidade: 1, quantidade_homologada: 1,
      valor_unitario_estimado: 100.0, valor_unitario_homologado: 90.0,
      fornecedor_nome: "COOPERATIVA DE CRÉDITO, POUPANÇA E INVESTIMENTO DO "
        + "NOROESTE DO ESTADO DE SÃO PAULO - SICREDI NOROESTE -SP",
      data_resultado: "2026-07-02" },
    { id: "X-3#2", contratacao_controle: "X-3", ano: 2025, sequencial: 50,
      numero_item: 2, descricao: "CANETA ESFEROGRÁFICA AZUL",
      unidade: "UN", quantidade: 500, quantidade_homologada: 500,
      valor_unitario_estimado: 1.9, valor_unitario_homologado: null,
      fornecedor_nome: null, data_resultado: null },
  ],
};

// serializada para dentro do addInitScript (roda no contexto da página)
function scriptPonte(temaBanco = "portal") {
  return `
    window.__chamadas = [];
    window.__temaBanco = ${JSON.stringify(temaBanco)};
    const DADOS = ${JSON.stringify(DADOS)};
    window.pywebview = { api: {
      get_estado: async () => ({ versao: "9.9.9", municipio: "Orindiúva",
        uf: "SP", ibge: "3534203", tema: window.__temaBanco,
        largura: "compacta",
        fonte: "normal", densidade: "confortavel", colunas: "{}",
        maximizar: "1",
        limite_dispensa_compras: "62639.92", limite_dispensa_obras: "125279.84",
        last_sync: "2026-07-29", sincronizado_em: "2026-07-29T14:32:00",
        kpis: { contratacoes: 131, homologado_ano: 10828702.73, vigentes: 47,
                vencendo_60: 9, propostas_abertas: 2 } }),
      filtros_disponiveis: async () => ({ anos: [2026, 2025, 2024],
        situacoes: ["Homologada", "Divulgada no PNCP"],
        modalidades: [{ id: 8, nome: "Dispensa" },
                      { id: 6, nome: "Pregão - Eletrônico" }],
        orgaos: [{ cnpj: "45148970000177", nome: "MUNICIPIO DE ORINDIUVA" },
                 { cnpj: "51351716000174", nome: "ORINDIUVA CAMARA MUNICIPAL" }] }),
      listar: async (tipo, filtros, pagina) => {
        window.__chamadas.push({ metodo: "listar", tipo, filtros, pagina });
        let itens = DADOS[tipo] || [];
        if (tipo === "itens" && filtros && filtros.so_homologados)
          itens = itens.filter(i => i.valor_unitario_homologado != null);
        return { itens, total: itens.length };
      },
      estatisticas_preco: async (busca, ano) => {
        window.__chamadas.push({ metodo: "estatisticas_preco", busca, ano });
        if (!/papel/i.test(busca || "")) return null;
        return { n: 3, minimo: 15.4, maximo: 24.9, media: 19.68,
                 mediana: 18.75, fornecedores: 2 };
      },
      detalhe: async (tipo, nc) =>
        ({ ...(DADOS[tipo] || []).find(d => d.numero_controle === nc),
           raw: { exemplo: true } }),
      sincronizar: async () => true,
      status_sync: async () => ({ rodando: false }),
      checar_atualizacao: async () => null,
      set_config: async (k, v) => {
        window.__chamadas.push({ metodo: "set_config", k, v }); return true; },
      set_titulo: async t => {
        window.__chamadas.push({ metodo: "set_titulo", t }); return true; },
      listar_orgaos: async () => [],
      ultimo_log: async () => [],
      municipios: async () => [],
      gerar_relatorio: async () => ({ ok: true }),
      exportar_csv: async () => ({ ok: false, erro: null }),
      abrir_pncp: async () => true,
    }};
  `;
}

async function abrirApp(page, opcoes = {}) {
  await page.addInitScript(scriptPonte(opcoes.temaBanco || "portal"));
  // o Python passa o tema na URL para a splash nascer na cor certa
  await page.goto(opcoes.tema ? `${URL_UI}?tema=${opcoes.tema}` : URL_UI);
  await page.evaluate(() => window.dispatchEvent(new Event("pywebviewready")));
}

module.exports = { URL_UI, DADOS, abrirApp };
