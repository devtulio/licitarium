"""Relatórios do Licitarium — relações oficiais (TCE) e resumo executivo.

Gera HTML standalone timbrado (imprimível pelo navegador, título vira nome do
PDF) e CSV para as relações. Só stdlib.
"""
import csv
import html
import json
import re
from datetime import date, datetime

# fonte da verdade da arte: design/estandarte-t3.svg
ESTANDARTE = """<svg viewBox="0 0 64 64" width="88" height="88" aria-hidden="true">
  <line x1="32" y1="57" x2="32" y2="15" stroke="#b08d3e" stroke-width="2.6" stroke-linecap="round"/>
  <ellipse cx="32" cy="10.5" rx="2.3" ry="5" fill="#b08d3e"/>
  <polygon points="12,25.5 5,21 5,37 12,32.5" fill="#ded5c2" stroke="#2b2115" stroke-width="1.6"/>
  <polygon points="52,25.5 59,21 59,37 52,32.5" fill="#ded5c2" stroke="#2b2115" stroke-width="1.6"/>
  <rect x="11" y="19" width="42" height="20" fill="#ded5c2" stroke="#2b2115" stroke-width="1.6"/>
  <text x="32" y="27.5" font-family="Georgia, serif" font-size="5.4" fill="#2b2115"
        text-anchor="middle" textLength="36" lengthAdjust="spacingAndGlyphs">LICITARIVM</text>
  <text x="32" y="34.5" font-family="Georgia, serif" font-size="3.6" fill="#8b2e2e"
        text-anchor="middle" textLength="36" lengthAdjust="spacingAndGlyphs">SVB · HASTA · PVBLICA</text>
  <line x1="20" y1="57.5" x2="44" y2="57.5" stroke="#2b2115" stroke-width="1.6" stroke-linecap="round"/>
  <text x="32" y="62.5" font-family="Georgia, serif" font-size="4.6" letter-spacing="1"
        fill="#2b2115" text-anchor="middle">MMXXVI</text>
</svg>"""

TITULOS = {"contratacoes": "Relação de Contratações",
           "contratos": "Relação de Contratos",
           "atas": "Relação de Atas de Registro de Preços",
           "executivo": "Resumo Executivo de Contratações",
           "fracionamento": "Alerta de Fracionamento — Dispensas × Limites",
           "precos": "Pesquisa de Preços — Histórico de Contratações",
           "minuta_pca": "Minuta do Plano de Contratações Anual"}

# Valores do art. 75, I e II, da Lei 14.133/2021 conforme Decreto de
# atualização — parametrizáveis nas configurações (confira o decreto vigente)
LIMITE_PADRAO_OBRAS = 125279.84
LIMITE_PADRAO_COMPRAS = 62639.92


def _e(v):
    return html.escape(str(v)) if v is not None else "–"


def documento(v):
    """Formata o identificador do fornecedor conforme o que ele é.

    O campo do PNCP (`niFornecedor`) guarda CNPJ e também CPF — no acervo
    real são 14 registros de pessoa física em contratos e 20 em itens.
    Máscara de CNPJ aplicada às cegas estragaria justamente esses.
    """
    digitos = re.sub(r"\D", "", str(v or ""))
    if len(digitos) == 14:
        return (f"{digitos[:2]}.{digitos[2:5]}.{digitos[5:8]}"
                f"/{digitos[8:12]}-{digitos[12:]}")
    if len(digitos) == 11:
        return f"{digitos[:3]}.{digitos[3:6]}.{digitos[6:9]}-{digitos[9:]}"
    return str(v) if v else "–"    # identificador estrangeiro ou ausente


def moeda(v):
    if v is None:
        return "–"
    inteiro, decimal = f"{v:,.2f}".split(".")
    return "R$ " + inteiro.replace(",", ".") + "," + decimal


def num_contrato(numero, ano):
    """PNCP grava '0033/26'; padrão de exibição é numero/ano: 33/2026."""
    if not numero:
        return None
    m = re.match(r"0*(\d+)", str(numero))
    n = m.group(1) if m else str(numero)
    return f"{n}/{ano}" if ano else str(n)


def data_br(s):
    if not s:
        return "–"
    p = str(s)[:10].split("-")
    return f"{p[2]}/{p[1]}/{p[0]}" if len(p) == 3 else str(s)


# ── consultas ───────────────────────────────────────────────────────────────

def dados_contratacoes(db, ano=None, modalidade=None, orgao=None):
    # relatório oficial: só o município do usuário (ver referencia=0 no
    # esquema — município de referência existe apenas para preços)
    where, args = ["referencia=0"], []
    if ano:
        where.append("ano=?")
        args.append(ano)
    if modalidade:
        where.append("modalidade_id=?")
        args.append(modalidade)
    if orgao:
        where.append("orgao_cnpj=?")
        args.append(orgao)
    sql_where = (" WHERE " + " AND ".join(where)) if where else ""
    linhas = [dict(r) for r in db.execute(
        f"""SELECT sequencial, ano, modalidade_nome,
                   json_extract(raw, '$.amparoLegal.nome') amparo,
                   objeto, unidade, valor_estimado, valor_homologado,
                   data_publicacao
            FROM contratacoes{sql_where}
            ORDER BY data_publicacao""", args)]
    tot_est = sum(l["valor_estimado"] or 0 for l in linhas)
    tot_hom = sum(l["valor_homologado"] or 0 for l in linhas)
    # deságio calculado só sobre processos com os dois valores
    pares = [(l["valor_estimado"], l["valor_homologado"]) for l in linhas
             if l["valor_estimado"] and l["valor_homologado"]]
    desagio = (1 - sum(h for _, h in pares) / sum(e for e, _ in pares)) * 100 \
        if pares else None
    return {"linhas": linhas,
            "totais": {"n": len(linhas), "estimado": tot_est,
                       "homologado": tot_hom, "desagio": desagio}}


def dados_contratos(db, ano=None, vigentes=False, orgao=None):
    where, args = [], []
    if vigentes:
        where.append("date(vigencia_fim) >= date('now')")
    elif ano:
        where.append("substr(data_publicacao,1,4)=?")
        args.append(str(ano))
    if orgao:
        where.append("orgao_cnpj=?")
        args.append(orgao)
    sql_where = (" WHERE " + " AND ".join(where)) if where else ""
    linhas = [dict(r) for r in db.execute(
        f"""SELECT numero_controle,
                   json_extract(raw, '$.numeroContratoEmpenho') numero,
                   json_extract(raw, '$.anoContrato') ano_contrato,
                   fornecedor_ni, fornecedor_nome, objeto, valor_global,
                   vigencia_inicio, vigencia_fim, data_publicacao
            FROM contratos{sql_where}
            ORDER BY data_publicacao""", args)]
    return {"linhas": linhas,
            "totais": {"n": len(linhas),
                       "valor": sum(l["valor_global"] or 0 for l in linhas)}}


def dados_atas(db, ano=None, vigentes=False, orgao=None):
    where, args = [], []
    if vigentes:
        where.append("date(vigencia_fim) >= date('now')")
    elif ano:
        where.append("substr(vigencia_inicio,1,4)=?")
        args.append(str(ano))
    if orgao:
        where.append("orgao_cnpj=?")
        args.append(orgao)
    sql_where = (" WHERE " + " AND ".join(where)) if where else ""
    linhas = [dict(r) for r in db.execute(
        f"""SELECT numero_controle,
                   json_extract(raw, '$.numeroAtaRegistroPreco') numero,
                   json_extract(raw, '$.anoAta') ano_ata,
                   json_extract(raw, '$.objetoContratacao') objeto,
                   contratacao_controle, vigencia_inicio, vigencia_fim,
                   json_extract(raw, '$.dataPublicacaoPncp') data_publicacao
            FROM atas{sql_where}
            ORDER BY vigencia_inicio""", args)]
    return {"linhas": linhas, "totais": {"n": len(linhas)}}


def dados_executivo(db, ano, orgao=None):
    ano = int(ano)
    og = " AND orgao_cnpj=?" if orgao else ""
    og_args = [orgao] if orgao else []
    modalidades = [dict(r) for r in db.execute(
        f"""SELECT modalidade_nome, COUNT(*) n,
                  SUM(valor_estimado) estimado, SUM(valor_homologado) homologado
           FROM contratacoes WHERE referencia=0 AND ano=?{og} GROUP BY 1
           ORDER BY COALESCE(SUM(COALESCE(valor_homologado, valor_estimado)),0)
           DESC""", [ano] + og_args)]
    meses = {r[0]: {"n": r[1], "valor": r[2] or 0} for r in db.execute(
        f"""SELECT substr(data_publicacao,6,2), COUNT(*),
                  SUM(COALESCE(valor_homologado, valor_estimado))
           FROM contratacoes
           WHERE referencia=0 AND ano=? AND data_publicacao IS NOT NULL{og}
           GROUP BY 1""", [ano] + og_args)}
    fornecedores = [dict(r) for r in db.execute(
        f"""SELECT fornecedor_nome, fornecedor_ni, COUNT(*) n,
                  SUM(COALESCE(valor_global,0)) total
           FROM contratos WHERE substr(data_publicacao,1,4)=?{og}
           GROUP BY fornecedor_ni ORDER BY total DESC LIMIT 10""",
        [str(ano)] + og_args)]
    vencendo = [dict(r) for r in db.execute(
        f"""SELECT 'Contrato' tipo, fornecedor_nome nome, objeto, vigencia_fim,
                  CAST(julianday(vigencia_fim) - julianday('now') AS INTEGER) dias
           FROM contratos
           WHERE date(vigencia_fim) BETWEEN date('now') AND date('now','+90 day'){og}
           UNION ALL
           SELECT 'Ata', json_extract(raw,'$.numeroAtaRegistroPreco') || '/' ||
                  json_extract(raw,'$.anoAta'),
                  json_extract(raw,'$.objetoContratacao'), vigencia_fim,
                  CAST(julianday(vigencia_fim) - julianday('now') AS INTEGER)
           FROM atas
           WHERE date(vigencia_fim) BETWEEN date('now') AND date('now','+90 day'){og}
           ORDER BY vigencia_fim""", og_args + og_args)]
    cards = dados_contratacoes(db, ano, orgao=orgao)["totais"]
    cards["contratos_vigentes"] = db.execute(
        f"SELECT COUNT(*) FROM contratos WHERE date(vigencia_fim)>=date('now')"
        f"{og}", og_args).fetchone()[0]
    cards["atas_vigentes"] = db.execute(
        f"SELECT COUNT(*) FROM atas WHERE date(vigencia_fim)>=date('now')"
        f"{og}", og_args).fetchone()[0]
    return {"ano": ano, "cards": cards, "modalidades": modalidades,
            "meses": meses, "fornecedores": fornecedores, "vencendo": vencendo}


def dados_fracionamento(db, ano, orgao=None, limites=None):
    """Dispensas do exercício somadas por unidade, contra os limites do art. 75.

    O agrupamento legal correto é por "objeto de mesma natureza" — juízo do
    gestor; aqui a soma por unidade é um termômetro de autocontrole.
    """
    ano = int(ano)
    limites = limites or {}

    def _limite(valor, padrao):
        try:
            return float(valor)
        except (TypeError, ValueError):
            return padrao
    limite_compras = _limite(limites.get("compras"), LIMITE_PADRAO_COMPRAS)
    limite_obras = _limite(limites.get("obras"), LIMITE_PADRAO_OBRAS)
    og = " AND orgao_cnpj=?" if orgao else ""
    og_args = [orgao] if orgao else []
    unidades = [dict(r) for r in db.execute(
        f"""SELECT COALESCE(unidade,'(sem unidade)') unidade, COUNT(*) n,
                   SUM(COALESCE(valor_homologado, valor_estimado, 0)) total
            FROM contratacoes
            WHERE referencia=0 AND ano=? AND modalidade_id=8{og}
            GROUP BY 1 ORDER BY total DESC""", [ano] + og_args)]
    for u in unidades:
        u["pct"] = u["total"] / limite_compras * 100 if limite_compras else 0
    dispensas = [dict(r) for r in db.execute(
        f"""SELECT sequencial, ano, unidade, objeto,
                   COALESCE(valor_homologado, valor_estimado) valor,
                   data_publicacao
            FROM contratacoes
            WHERE referencia=0 AND ano=? AND modalidade_id=8{og}
            ORDER BY unidade, data_publicacao""", [ano] + og_args)]
    return {"ano": ano, "unidades": unidades, "dispensas": dispensas,
            "limite_compras": limite_compras, "limite_obras": limite_obras,
            "total": sum(d["valor"] or 0 for d in dispensas),
            "n": len(dispensas)}


def _blocos(ids, tamanho=400):
    """Fatia ids para caber no limite de parâmetros do SQLite."""
    ids = [str(i) for i in (ids or []) if i]
    return [ids[i:i + tamanho] for i in range(0, len(ids), tamanho)]


def dados_precos(db, termo, ano=None, orgao=None, excluidos=None):
    """Histórico de preços unitários homologados para um termo de busca."""
    where = ["valor_unitario_homologado IS NOT NULL"]
    args = []
    palavras = re.findall(r"[0-9A-Za-zÀ-ÿ]+", termo or "")
    if palavras:   # mesma busca por palavras da aba Preços
        where.append("rowid IN (SELECT rowid FROM itens_fts"
                     " WHERE itens_fts MATCH ?)")
        args.append(" AND ".join(f'"{p}"*' for p in palavras))
    else:
        where.append("descricao LIKE ?")
        args.append(f"%{(termo or '').strip()}%")
    if ano:
        where.append("ano=?")
        args.append(int(ano))
    if orgao:
        where.append("orgao_cnpj=?")
        args.append(orgao)
    # itens que o usuário descartou na tela não entram no documento
    for grupo in _blocos(excluidos):
        where.append("id NOT IN (%s)" % ",".join("?" * len(grupo)))
        args += grupo
    sql_where = " WHERE " + " AND ".join(where)
    linhas = [dict(r) for r in db.execute(
        f"""SELECT descricao, unidade, quantidade_homologada, unidade,
                   valor_unitario_homologado, valor_total_homologado,
                   fornecedor_nome, fornecedor_ni, data_resultado,
                   sequencial, ano, contratacao_controle,
                   referencia, municipio_ibge
            FROM itens{sql_where}
            ORDER BY valor_unitario_homologado""", args)]
    # de onde veio cada preço: o documento tem de dizer, porque parâmetro
    # de outro ente é admitido pelo art. 23, §1º, I, mas precisa estar claro
    nomes = {r["ibge"]: r["nome"] for r in
             db.execute("SELECT ibge, nome FROM municipios_referencia")}
    proprio = db.execute(
        "SELECT valor FROM config WHERE chave='municipio_ibge'").fetchone()
    nome_proprio = db.execute(
        "SELECT valor FROM config WHERE chave='municipio_nome'").fetchone()
    if proprio:
        nomes[proprio[0]] = nome_proprio[0] if nome_proprio else proprio[0]
    for l in linhas:
        l["municipio_nome"] = nomes.get(l["municipio_ibge"]) or "–"
    valores = [l["valor_unitario_homologado"] for l in linhas]
    resumo = None
    if valores:
        n = len(valores)
        meio = n // 2
        resumo = {
            "n": n, "minimo": valores[0], "maximo": valores[-1],
            "media": sum(valores) / n,
            "mediana": valores[meio] if n % 2
                       else (valores[meio - 1] + valores[meio]) / 2,
            "fornecedores": len({l["fornecedor_ni"] for l in linhas}),
        }
    return {"termo": (termo or "").strip(), "linhas": linhas, "resumo": resumo,
            "ano": ano}


# ── render ──────────────────────────────────────────────────────────────────

# paletas espelham os temas do app; impressão força sempre a "pergaminho"
# (tinta sobre papel — tema escuro não faz sentido impresso)
PALETAS = {
    "pergaminho": dict(bg="#f5efe2", superficie="#fbf7ee", zebra="#faf6ec",
                       cabecalho="#efe6d2", texto="#2b2115", suave="#6f5b3e",
                       borda="#d9cbaa", acento="#8b2e2e", detalhe="#b08d3e",
                       alerta="#8b2e2e", atencao="#8a6d1f"),
    "portal": dict(bg="#f8f9fa", superficie="#ffffff", zebra="#f8f9fa",
                   cabecalho="#f1f3f5", texto="#1b1b1b", suave="#5c6670",
                   borda="#e3e6e8", acento="#1351b4", detalhe="#1351b4",
                   alerta="#b00020", atencao="#a26a00"),
    "observatorio": dict(bg="#10151c", superficie="#1a212b", zebra="#161d27",
                         cabecalho="#141a23", texto="#dce3ec", suave="#8b97a7",
                         borda="#232c38", acento="#f0a836", detalhe="#f0a836",
                         alerta="#ff8a80", atencao="#f0a836"),
}


def _vars(p):
    return (f"--bg:{p['bg']}; --superficie:{p['superficie']};"
            f" --zebra:{p['zebra']}; --cabecalho:{p['cabecalho']};"
            f" --texto:{p['texto']}; --suave:{p['suave']};"
            f" --borda:{p['borda']}; --acento:{p['acento']};"
            f" --detalhe:{p['detalhe']}; --alerta:{p['alerta']};"
            f" --atencao:{p['atencao']};")


def _css(paisagem, tema="pergaminho"):
    p = PALETAS.get(tema) or PALETAS["pergaminho"]
    return f"""
  :root {{ {_vars(p)} }}
  @media print {{ :root {{ {_vars(PALETAS["pergaminho"])} }} }}
  @page {{
    size: A4 {"landscape" if paisagem else "portrait"}; margin: 1.6cm 1.4cm;
    @top-center {{ content: string(titulo); font-size: 8pt; color: #6f5b3e; }}
    @bottom-right {{ content: "Página " counter(page) " de " counter(pages);
                     font-size: 8pt; color: #6f5b3e; }}
  }}
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family:'Segoe UI',system-ui,sans-serif; color:var(--texto);
          background:var(--bg); font-size:13px; line-height:1.45; }}
  .pagina {{ max-width:{1080 if paisagem else 820}px; margin:0 auto;
             padding:26px 30px 50px; }}
  header {{ display:flex; align-items:center; gap:18px; padding-bottom:14px;
            border-bottom:3px double var(--detalhe); margin-bottom:16px; }}
  h1 {{ font-family:Georgia,serif; font-size:21px; font-weight:400;
        string-set: titulo content(); }}
  .meta {{ font-size:11.5px; color:var(--suave); margin-top:3px; }}
  h2 {{ font-family:Georgia,serif; font-size:15px; font-weight:400;
        color:var(--acento); margin:20px 0 8px; break-after:avoid; }}
  table {{ border-collapse:collapse; width:100%; font-size:11.5px; }}
  th, td {{ border:1px solid var(--borda); padding:5px 8px; text-align:left;
            vertical-align:middle; }}
  th {{ background:var(--cabecalho); font-size:10px; letter-spacing:.05em;
        text-transform:uppercase; }}
  tr {{ break-inside:avoid; }}
  tbody tr:nth-child(even) td {{ background:var(--zebra); }}
  /* colunas curtas (valores, datas, qtde): centro nos dois eixos */
  td.num, th.num {{ text-align:center; font-variant-numeric:tabular-nums;
                    white-space:nowrap; }}
  /* centro com quebra de linha permitida (textos curtos não-numéricos) */
  td.ctr, th.ctr {{ text-align:center; }}
  tfoot td {{ background:var(--cabecalho); font-weight:600; }}
  .obj {{ text-transform:uppercase; text-align:justify; hyphens:auto; }}
  /* nome de fornecedor quebra feio; a coluna cede espaço da descrição */
  td.forn, th.forn {{ text-align:center; min-width:170px; }}
  .cards {{ display:flex; gap:10px; margin-bottom:6px; }}
  .card {{ background:var(--superficie); border:1px solid var(--borda);
           border-radius:3px;
           padding:10px 12px; break-inside:avoid; flex:1 1 auto; }}
  .card .n {{ font-family:Georgia,serif; font-size:17px; color:var(--acento);
              white-space:nowrap; }}
  .card .l {{ font-size:9.5px; letter-spacing:.06em; text-transform:uppercase;
              color:var(--suave); margin-top:2px; }}
  .barra {{ background:var(--detalhe); height:10px; display:inline-block;
            vertical-align:middle; border-radius:2px; }}
  .caixa-aviso {{ background:var(--superficie); border:1px solid var(--borda);
                  border-left:4px solid var(--alerta); border-radius:3px;
                  padding:10px 14px; font-size:11.5px; margin-bottom:12px;
                  break-inside:avoid; }}
  .farol-alerta {{ color:var(--alerta); font-weight:600; }}
  .farol-atencao {{ color:var(--atencao); font-weight:600; }}
  footer {{ margin-top:22px; padding-top:10px;
            border-top:3px double var(--detalhe);
            font-size:10.5px; color:var(--suave); display:flex;
            justify-content:space-between; }}
  .no-print {{ position:fixed; top:14px; right:14px; }}
  .no-print button {{ font-size:14px; padding:8px 14px; cursor:pointer;
    background:var(--acento); color:var(--superficie); border:none;
    border-radius:3px; }}
  @media print {{ body {{ background:#fff; font-size:10pt; }}
    tbody tr:nth-child(even) td {{ background:#faf6ec; }}
    .pagina {{ max-width:none; padding:0; }} .no-print {{ display:none; }} }}
"""


def _pagina(titulo_doc, corpo, municipio, uf, periodo_txt, paisagem,
            tema="pergaminho"):
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
    return f"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8">
<title>{_e(titulo_doc)}</title><style>{_css(paisagem, tema)}</style></head><body>
<div class="no-print"><button onclick="print()">🖨 Imprimir</button></div>
<div class="pagina">
<header>{ESTANDARTE}
  <div><h1>{_e(titulo_doc)}</h1>
  <div class="meta">{_e(municipio)} — {_e(uf)} · {_e(periodo_txt)}<br>
  Fonte: Portal Nacional de Contratações Públicas (PNCP) · Lei 14.133/2021<br>
  Gerado pelo Licitarium em {agora}</div></div>
</header>
{corpo}
<footer><span>LICITARIVM · SVB HASTA PVBLICA</span>
<span>Documento gerado automaticamente a partir de dados públicos do PNCP</span></footer>
</div></body></html>"""


def render_contratacoes(d, municipio, uf, periodo_txt, tema="pergaminho"):
    linhas = "".join(f"""<tr>
      <td class="ctr">{_e(l['sequencial'])}/{_e(l['ano'])}</td>
      <td class="ctr">{_e(l['modalidade_nome'])}</td>
      <td class="ctr">{_e(l['amparo'])}</td>
      <td class="obj">{_e(l['objeto'])}</td>
      <td class="ctr">{_e(l['unidade'])}</td>
      <td class="num">{moeda(l['valor_estimado'])}</td>
      <td class="num">{moeda(l['valor_homologado'])}</td>
      <td class="num">{data_br(l['data_publicacao'])}</td></tr>"""
      for l in d["linhas"])
    t = d["totais"]
    desagio = f" · Deságio médio: {t['desagio']:.1f}%".replace(".", ",") \
        if t["desagio"] is not None else ""
    corpo = f"""<table>
<thead><tr><th class="ctr">Processo</th><th class="ctr">Modalidade</th>
<th class="ctr">Amparo legal</th>
<th>Objeto</th><th class="ctr">Unidade</th><th class="num">Valor estimado</th>
<th class="num">Valor homologado</th><th class="num">Publicação</th></tr></thead>
<tbody>{linhas or '<tr><td colspan="8">Nenhum registro no período.</td></tr>'}</tbody>
<tfoot><tr><td colspan="5">Total: {t['n']} contratações{desagio}</td>
<td class="num">{moeda(t['estimado'])}</td>
<td class="num">{moeda(t['homologado'])}</td><td></td></tr></tfoot></table>"""
    titulo = f"{TITULOS['contratacoes']} — {municipio} — {periodo_txt}"
    return _pagina(titulo, corpo, municipio, uf, periodo_txt, paisagem=True,
                   tema=tema)


def render_contratos(d, municipio, uf, periodo_txt, tema="pergaminho"):
    linhas = "".join(f"""<tr>
      <td class="ctr">{_e(num_contrato(l['numero'], l['ano_contrato'])
                          or l['numero_controle'])}</td>
      <td class="ctr">{_e(l['fornecedor_nome'])}<br>
          <small>{_e(documento(l['fornecedor_ni']))}</small></td>
      <td class="obj">{_e(l['objeto'])}</td>
      <td class="num">{moeda(l['valor_global'])}</td>
      <td class="num">{data_br(l['vigencia_inicio'])} – {data_br(l['vigencia_fim'])}</td>
      <td class="num">{data_br(l['data_publicacao'])}</td></tr>"""
      for l in d["linhas"])
    t = d["totais"]
    corpo = f"""<table>
<thead><tr><th class="ctr">Contrato</th><th class="ctr">Fornecedor</th><th>Objeto</th>
<th class="num">Valor global</th><th class="num">Vigência</th>
<th class="num">Publicação</th></tr></thead>
<tbody>{linhas or '<tr><td colspan="6">Nenhum registro no período.</td></tr>'}</tbody>
<tfoot><tr><td colspan="3">Total: {t['n']} contratos</td>
<td class="num">{moeda(t['valor'])}</td><td colspan="2"></td></tr></tfoot></table>"""
    titulo = f"{TITULOS['contratos']} — {municipio} — {periodo_txt}"
    return _pagina(titulo, corpo, municipio, uf, periodo_txt, paisagem=True,
                   tema=tema)


def render_atas(d, municipio, uf, periodo_txt, tema="pergaminho"):
    linhas = "".join(f"""<tr>
      <td class="ctr">{_e(l['numero'])}/{_e(l['ano_ata'])}</td>
      <td class="ctr">{_e(l['contratacao_controle'])}</td>
      <td class="obj">{_e(l['objeto'])}</td>
      <td class="num">{data_br(l['vigencia_inicio'])} – {data_br(l['vigencia_fim'])}</td>
      <td class="num">{data_br(l['data_publicacao'])}</td></tr>"""
      for l in d["linhas"])
    corpo = f"""<table>
<thead><tr><th class="ctr">Ata</th><th class="ctr">Contratação de origem</th><th>Objeto</th>
<th class="num">Vigência</th><th class="num">Publicação</th></tr></thead>
<tbody>{linhas or '<tr><td colspan="5">Nenhum registro no período.</td></tr>'}</tbody>
<tfoot><tr><td colspan="5">Total: {d['totais']['n']} atas</td></tr></tfoot></table>"""
    titulo = f"{TITULOS['atas']} — {municipio} — {periodo_txt}"
    return _pagina(titulo, corpo, municipio, uf, periodo_txt, paisagem=True,
                   tema=tema)


def render_fracionamento(d, municipio, uf, tema="pergaminho"):
    def farol(pct):
        if pct >= 100:
            return '<span class="farol-alerta">ACIMA DO LIMITE</span>'
        if pct >= 75:
            return '<span class="farol-atencao">Atenção</span>'
        return "ok"
    unid = "".join(f"""<tr><td>{_e(u['unidade'])}</td>
      <td class="num">{u['n']}</td>
      <td class="num">{moeda(u['total'])}</td>
      <td class="num">{u['pct']:.0f}%</td>
      <td class="ctr">{farol(u['pct'])}</td></tr>""" for u in d["unidades"])
    disp = "".join(f"""<tr><td class="ctr">{_e(l['sequencial'])}/{_e(l['ano'])}</td>
      <td class="ctr">{_e(l['unidade'])}</td>
      <td class="obj">{_e(l['objeto'])}</td>
      <td class="num">{moeda(l['valor'])}</td>
      <td class="num">{data_br(l['data_publicacao'])}</td></tr>"""
      for l in d["dispensas"])
    corpo = f"""<div class="caixa-aviso">Instrumento de <b>autocontrole
interno</b>. A soma por unidade é um termômetro: o enquadramento legal do
fracionamento considera despesas de <b>mesma natureza</b> (art. 75, §1º, Lei
14.133/2021), avaliação que cabe ao gestor. Limites parametrizados nas
configurações — confira o decreto de atualização vigente.
Limite adotado para compras/serviços: <b>{moeda(d['limite_compras'])}</b> ·
obras/serviços de engenharia: <b>{moeda(d['limite_obras'])}</b>.</div>
<div class="cards">
<div class="card"><div class="n">{d['n']}</div><div class="l">dispensas no exercício</div></div>
<div class="card"><div class="n">{moeda(d['total'])}</div><div class="l">total em dispensas</div></div>
</div>
<h2>Soma de dispensas por unidade × limite de compras/serviços</h2>
<table><thead><tr><th>Unidade</th><th class="num">Dispensas</th>
<th class="num">Total</th><th class="num">% do limite</th>
<th class="ctr">Situação</th></tr></thead>
<tbody>{unid or '<tr><td colspan="5">Nenhuma dispensa no exercício.</td></tr>'}</tbody></table>
<h2>Dispensas do exercício (para agrupamento por natureza pelo gestor)</h2>
<table><thead><tr><th class="ctr">Processo</th><th class="ctr">Unidade</th>
<th>Objeto</th><th class="num">Valor</th><th class="num">Publicação</th></tr></thead>
<tbody>{disp or '<tr><td colspan="5">Nenhuma dispensa no exercício.</td></tr>'}</tbody></table>"""
    titulo = f"{TITULOS['fracionamento']} {d['ano']} — {municipio}"
    return _pagina(titulo, corpo, municipio, uf,
                   f"Exercício {d['ano']} · uso interno", paisagem=False,
                   tema=tema)


def render_minuta_pca(d, municipio, uf, tema="pergaminho"):
    linhas = "".join(f"""<tr>
      <td class="num">{i+1}</td>
      <td class="obj">{_e(l['descricao'])}</td>
      <td class="ctr">{_e(l['categoria'])}</td>
      <td class="ctr">{_e(l['unidade'])}</td>
      <td class="num">{l['quantidade'] or 0:.2f}</td>
      <td class="num">{moeda(l['valor_unitario'])}</td>
      <td class="num">{moeda(l['valor_total'])}</td></tr>"""
      for i, l in enumerate(d["itens"]))
    p = d.get("parametros") or {}
    base = {"media": "média dos exercícios", "ultimo": "último exercício",
            "maior": "maior exercício", "soma": "soma do período"}.get(
                p.get("base"), p.get("base", "—"))
    est = {"mediana": "mediana", "media": "média", "recente": "mais recente",
           "menor": "menor"}.get(p.get("estatistica"), p.get("estatistica", "—"))
    corpo = f"""<div class="caixa-aviso"><b>Minuta para revisão.</b> Consolidação
automática do que o município já contratou, segundo os registros do PNCP.
Os itens publicados <b>não trazem código de catálogo</b> (CATMAT/CATSER),
exigido no plano oficial — a classificação, o agrupamento definitivo e a
conferência de especificação e unidade cabem ao gestor.<br>
Quantidade pela <b>{base}</b>, acrescida da margem informada; preço unitário
pela <b>{est}</b> dos valores homologados.</div>
<div class="cards">
<div class="card"><div class="n">{d['totais']['grupos']}</div><div class="l">itens no plano</div></div>
<div class="card"><div class="n">{moeda(d['totais']['valor'])}</div><div class="l">valor estimado</div></div>
<div class="card"><div class="n">{p.get('margem', '—')}%</div><div class="l">margem aplicada</div></div>
</div>
<h2>Itens da minuta</h2>
<table><thead><tr><th class="num">#</th><th>Descrição</th>
<th class="ctr">Tipo</th><th class="ctr">Unid.</th><th class="num">Quantidade</th>
<th class="num">Unitário</th><th class="num">Total</th></tr></thead>
<tbody>{linhas or '<tr><td colspan="7">Minuta vazia.</td></tr>'}</tbody></table>"""
    titulo = f"{TITULOS['minuta_pca']} {d['ano']} — {municipio}"
    return _pagina(titulo, corpo, municipio, uf, f"Exercício {d['ano']}",
                   paisagem=True, tema=tema)


def render_precos(d, municipio, uf, tema="pergaminho"):
    r = d["resumo"]
    periodo = f"Exercício {d['ano']}" if d.get("ano") else "Todo o acervo"
    if not r:
        corpo = (f'<div class="caixa-aviso">Nenhum item homologado encontrado '
                 f'para <b>{_e(d["termo"])}</b> no acervo local.</div>')
        return _pagina(f"{TITULOS['precos']} — {_e(d['termo'])}", corpo,
                       municipio, uf, periodo, paisagem=True, tema=tema)
    cards = f"""<div class="cards">
<div class="card"><div class="n">{moeda(r['minimo'])}</div><div class="l">menor unitário</div></div>
<div class="card"><div class="n">{moeda(r['mediana'])}</div><div class="l">mediana</div></div>
<div class="card"><div class="n">{moeda(r['media'])}</div><div class="l">média</div></div>
<div class="card"><div class="n">{moeda(r['maximo'])}</div><div class="l">maior unitário</div></div>
<div class="card"><div class="n">{r['n']}</div><div class="l">itens</div></div>
<div class="card"><div class="n">{r['fornecedores']}</div><div class="l">fornecedores</div></div>
</div>"""
    linhas = "".join(f"""<tr>
      <td class="obj">{_e(l['descricao'])}</td>
      <td class="ctr">{_e(l['unidade'])}</td>
      <td class="num">{l['quantidade_homologada'] or '–'}</td>
      <td class="num">{moeda(l['valor_unitario_homologado'])}</td>
      <td class="num">{moeda(l['valor_total_homologado'])}</td>
      <td class="forn">{_e(l['fornecedor_nome'])}</td>
      <td class="ctr">{_e(l['municipio_nome'])}</td>
      <td class="ctr">{_e(l['sequencial'])}/{_e(l['ano'])}</td>
      <td class="num">{data_br(l['data_resultado'])}</td></tr>"""
      for l in d["linhas"])
    corpo = f"""<div class="caixa-aviso">Levantamento de <b>preços efetivamente
homologados</b> pelo município, extraído do PNCP — subsídio à pesquisa de
preços do art. 23 da Lei 14.133/2021 (que admite contratações similares de
outros entes como parâmetro). Confira a aderência de especificação, unidade e
quantidade de cada item antes de usar como referência.
Termo pesquisado: <b>{_e(d['termo'])}</b>.</div>
{cards}
<h2>Itens homologados, do menor para o maior preço unitário</h2>
<table><thead><tr><th>Descrição</th><th class="ctr">Unid.</th>
<th class="num">Qtde</th><th class="num">Unitário</th>
<th class="num">Total</th><th class="forn">Fornecedor</th>
<th class="ctr">Município</th>
<th class="ctr">Processo</th><th class="num">Resultado</th></tr></thead>
<tbody>{linhas}</tbody></table>"""
    titulo = f"{TITULOS['precos']} — {d['termo']} — {municipio}"
    return _pagina(titulo, corpo, municipio, uf, periodo, paisagem=True,
                   tema=tema)


MESES_NOME = ["jan", "fev", "mar", "abr", "mai", "jun",
              "jul", "ago", "set", "out", "nov", "dez"]


def render_executivo(d, municipio, uf, tema="pergaminho"):
    c = d["cards"]
    desagio = f"{c['desagio']:.1f}%".replace(".", ",") \
        if c["desagio"] is not None else "–"
    cards = f"""<div class="cards">
<div class="card"><div class="n">{c['n']}</div><div class="l">contratações</div></div>
<div class="card"><div class="n">{moeda(c['homologado'])}</div><div class="l">homologado</div></div>
<div class="card"><div class="n">{desagio}</div><div class="l">deságio médio</div></div>
<div class="card"><div class="n">{c['contratos_vigentes']}</div><div class="l">contratos vigentes</div></div>
<div class="card"><div class="n">{c['atas_vigentes']}</div><div class="l">atas vigentes</div></div>
</div>"""
    mod = "".join(f"""<tr><td>{_e(m['modalidade_nome'])}</td>
      <td class="num">{m['n']}</td>
      <td class="num">{moeda(m['estimado'])}</td>
      <td class="num">{moeda(m['homologado'])}</td></tr>"""
      for m in d["modalidades"])
    maior = max((v["valor"] for v in d["meses"].values()), default=0) or 1
    meses = "".join(f"""<tr><td class="ctr">{MESES_NOME[i-1]}</td>
      <td class="num">{d['meses'].get(f'{i:02d}', {}).get('n', 0)}</td>
      <td class="num">{moeda(d['meses'].get(f'{i:02d}', {}).get('valor')) if f'{i:02d}' in d['meses'] else '–'}</td>
      <td><span class="barra" style="width:{round(d['meses'].get(f'{i:02d}', {}).get('valor', 0) / maior * 220)}px"></span></td></tr>"""
      for i in range(1, 13))
    forn = "".join(f"""<tr><td>{_e(f['fornecedor_nome'])}<br>
      <small>{_e(documento(f['fornecedor_ni']))}</small></td>
      <td class="num">{f['n']}</td><td class="num">{moeda(f['total'])}</td></tr>"""
      for f in d["fornecedores"])
    venc = "".join(f"""<tr><td class="ctr">{_e(v['tipo'])}</td>
      <td class="ctr">{_e(v['nome'])}</td>
      <td class="obj">{_e(v['objeto'])}</td>
      <td class="num">{data_br(v['vigencia_fim'])}</td>
      <td class="num">{v['dias']} dias</td></tr>"""
      for v in d["vencendo"])
    corpo = f"""{cards}
<h2>Contratações por modalidade</h2>
<table><thead><tr><th>Modalidade</th><th class="num">Qtde</th>
<th class="num">Estimado</th><th class="num">Homologado</th></tr></thead>
<tbody>{mod or '<tr><td colspan="4">Sem dados.</td></tr>'}</tbody></table>
<h2>Evolução mensal (valor homologado/estimado publicado)</h2>
<table><thead><tr><th class="ctr">Mês</th><th class="num">Processos</th>
<th class="num">Valor</th><th></th></tr></thead><tbody>{meses}</tbody></table>
<h2>Maiores fornecedores contratados no ano</h2>
<table><thead><tr><th>Fornecedor</th><th class="num">Contratos</th>
<th class="num">Valor</th></tr></thead>
<tbody>{forn or '<tr><td colspan="3">Sem contratos no ano.</td></tr>'}</tbody></table>
<h2>Vigências a vencer nos próximos 90 dias</h2>
<table><thead><tr><th class="ctr">Tipo</th><th class="ctr">Contrato/Ata</th><th>Objeto</th>
<th class="num">Fim</th><th class="num">Prazo</th></tr></thead>
<tbody>{venc or '<tr><td colspan="5">Nada vence nos próximos 90 dias.</td></tr>'}</tbody></table>"""
    titulo = f"{TITULOS['executivo']} {d['ano']} — {municipio}"
    return _pagina(titulo, corpo, municipio, uf, f"Exercício {d['ano']}",
                   paisagem=False, tema=tema)


# ── geração (HTML + CSV) ────────────────────────────────────────────────────

def gerar(db, tipo, params, municipio, uf, destino, tema="pergaminho"):
    """Gera o relatório e retorna {"html": caminho, "csv": caminho|None}."""
    params = params or {}
    ano = params.get("ano")
    vigentes = bool(params.get("vigentes"))
    orgao = params.get("orgao")
    # com filtro de órgão, o nome dele entra no cabeçalho, no título
    # (= nome do PDF) e no nome do arquivo
    if orgao and params.get("orgao_nome"):
        municipio = f"{municipio} · {params['orgao_nome']}"
    destino.mkdir(parents=True, exist_ok=True)
    if tipo == "executivo":
        if not ano:
            ano = date.today().year
        d = dados_executivo(db, ano, orgao)
        conteudo = render_executivo(d, municipio, uf, tema)
        nome = f"resumo_executivo_{ano}"
        linhas_csv = None
    elif tipo == "minuta_pca":
        import pca_builder
        if not ano:
            ano = date.today().year + 1
        itens = pca_builder.listar_minuta(db, ano, so_incluidos=True)
        cfg = db.execute("SELECT parametros FROM pca_minuta WHERE ano_alvo=?",
                         (ano,)).fetchone()
        d = {"ano": ano, "itens": itens,
             "totais": pca_builder.totais(itens),
             "parametros": json.loads(cfg[0]) if cfg else {}}
        conteudo = render_minuta_pca(d, municipio, uf, tema)
        nome = f"minuta_pca_{ano}"
        linhas_csv = [{k: i[k] for k in ("descricao", "unidade", "categoria",
                                         "quantidade", "valor_unitario",
                                         "margem", "valor_total")}
                      for i in itens]
    elif tipo == "precos":
        termo = (params.get("termo") or "").strip()
        if not termo:
            raise ValueError("informe o que pesquisar")
        d = dados_precos(db, termo, ano, orgao, params.get("excluidos"))
        conteudo = render_precos(d, municipio, uf, tema)
        limpo = re.sub(r"[^\w-]+", "_", termo.lower())[:40]
        nome = f"pesquisa_precos_{limpo}"
        linhas_csv = d["linhas"]
    elif tipo == "fracionamento":
        if not ano:
            ano = date.today().year
        d = dados_fracionamento(db, ano, orgao, params.get("limites"))
        conteudo = render_fracionamento(d, municipio, uf, tema)
        nome = f"alerta_fracionamento_{ano}"
        linhas_csv = d["dispensas"]
    else:
        periodo_txt = ("Vigentes em " + date.today().strftime("%d/%m/%Y")) \
            if vigentes else (f"Exercício {ano}" if ano else "Todo o período")
        if tipo == "contratacoes":
            d = dados_contratacoes(db, ano, params.get("modalidade"), orgao)
            conteudo = render_contratacoes(d, municipio, uf, periodo_txt, tema)
        elif tipo == "contratos":
            d = dados_contratos(db, ano, vigentes, orgao)
            conteudo = render_contratos(d, municipio, uf, periodo_txt, tema)
        elif tipo == "atas":
            d = dados_atas(db, ano, vigentes, orgao)
            conteudo = render_atas(d, municipio, uf, periodo_txt, tema)
        else:
            raise ValueError(f"tipo de relatório desconhecido: {tipo}")
        sufixo = "vigentes" if vigentes else (str(ano) if ano else "completo")
        nome = f"relacao_{tipo}_{sufixo}"
        linhas_csv = d["linhas"]
    if orgao:
        nome += f"_orgao_{orgao}"
    caminho_html = destino / f"{nome}.html"
    caminho_html.write_text(conteudo, encoding="utf-8")
    caminho_csv = None
    if linhas_csv:
        caminho_csv = destino / f"{nome}.csv"
        with open(caminho_csv, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=linhas_csv[0].keys(), delimiter=";")
            w.writeheader()
            w.writerows(linhas_csv)
    return {"html": str(caminho_html),
            "csv": str(caminho_csv) if caminho_csv else None}
