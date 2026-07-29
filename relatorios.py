"""Relatórios do Licitarium — relações oficiais (TCE) e resumo executivo.

Gera HTML standalone timbrado (imprimível pelo navegador, título vira nome do
PDF) e CSV para as relações. Só stdlib.
"""
import csv
import html
import json
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
           "fracionamento": "Alerta de Fracionamento — Dispensas × Limites"}

# Valores do art. 75, I e II, da Lei 14.133/2021 conforme Decreto de
# atualização — parametrizáveis nas configurações (confira o decreto vigente)
LIMITE_PADRAO_OBRAS = 125279.84
LIMITE_PADRAO_COMPRAS = 62639.92


def _e(v):
    return html.escape(str(v)) if v is not None else "–"


def moeda(v):
    if v is None:
        return "–"
    inteiro, decimal = f"{v:,.2f}".split(".")
    return "R$ " + inteiro.replace(",", ".") + "," + decimal


def data_br(s):
    if not s:
        return "–"
    p = str(s)[:10].split("-")
    return f"{p[2]}/{p[1]}/{p[0]}" if len(p) == 3 else str(s)


# ── consultas ───────────────────────────────────────────────────────────────

def dados_contratacoes(db, ano=None, modalidade=None, orgao=None):
    where, args = [], []
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
           FROM contratacoes WHERE ano=?{og} GROUP BY 1
           ORDER BY COALESCE(SUM(COALESCE(valor_homologado, valor_estimado)),0)
           DESC""", [ano] + og_args)]
    meses = {r[0]: {"n": r[1], "valor": r[2] or 0} for r in db.execute(
        f"""SELECT substr(data_publicacao,6,2), COUNT(*),
                  SUM(COALESCE(valor_homologado, valor_estimado))
           FROM contratacoes WHERE ano=? AND data_publicacao IS NOT NULL{og}
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
            FROM contratacoes WHERE ano=? AND modalidade_id=8{og}
            GROUP BY 1 ORDER BY total DESC""", [ano] + og_args)]
    for u in unidades:
        u["pct"] = u["total"] / limite_compras * 100 if limite_compras else 0
    dispensas = [dict(r) for r in db.execute(
        f"""SELECT sequencial, ano, unidade, objeto,
                   COALESCE(valor_homologado, valor_estimado) valor,
                   data_publicacao
            FROM contratacoes WHERE ano=? AND modalidade_id=8{og}
            ORDER BY unidade, data_publicacao""", [ano] + og_args)]
    return {"ano": ano, "unidades": unidades, "dispensas": dispensas,
            "limite_compras": limite_compras, "limite_obras": limite_obras,
            "total": sum(d["valor"] or 0 for d in dispensas),
            "n": len(dispensas)}


# ── render ──────────────────────────────────────────────────────────────────

def _css(paisagem):
    return f"""
  @page {{
    size: A4 {"landscape" if paisagem else "portrait"}; margin: 1.6cm 1.4cm;
    @top-center {{ content: string(titulo); font-size: 8pt; color: #6f5b3e; }}
    @bottom-right {{ content: "Página " counter(page) " de " counter(pages);
                     font-size: 8pt; color: #6f5b3e; }}
  }}
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family:'Segoe UI',system-ui,sans-serif; color:#2b2115;
          background:#f5efe2; font-size:13px; line-height:1.45; }}
  .pagina {{ max-width:{1080 if paisagem else 820}px; margin:0 auto;
             padding:26px 30px 50px; }}
  header {{ display:flex; align-items:center; gap:18px; padding-bottom:14px;
            border-bottom:3px double #b08d3e; margin-bottom:16px; }}
  h1 {{ font-family:Georgia,serif; font-size:21px; font-weight:400;
        string-set: titulo content(); }}
  .meta {{ font-size:11.5px; color:#6f5b3e; margin-top:3px; }}
  h2 {{ font-family:Georgia,serif; font-size:15px; font-weight:400;
        color:#8b2e2e; margin:20px 0 8px; break-after:avoid; }}
  table {{ border-collapse:collapse; width:100%; font-size:11.5px; }}
  th, td {{ border:1px solid #d9cbaa; padding:5px 8px; text-align:left;
            vertical-align:middle; }}
  th {{ background:#efe6d2; font-size:10px; letter-spacing:.05em;
        text-transform:uppercase; }}
  tr {{ break-inside:avoid; }}
  tbody tr:nth-child(even) td {{ background:#faf6ec; }}
  /* colunas curtas (valores, datas, qtde): centro nos dois eixos */
  td.num, th.num {{ text-align:center; font-variant-numeric:tabular-nums;
                    white-space:nowrap; }}
  /* centro com quebra de linha permitida (textos curtos não-numéricos) */
  td.ctr, th.ctr {{ text-align:center; }}
  tfoot td {{ background:#efe6d2; font-weight:600; }}
  .obj {{ text-transform:uppercase; text-align:justify; hyphens:auto; }}
  .cards {{ display:flex; gap:10px; margin-bottom:6px; }}
  .card {{ background:#fbf7ee; border:1px solid #d9cbaa; border-radius:3px;
           padding:10px 12px; break-inside:avoid; flex:1 1 auto; }}
  .card .n {{ font-family:Georgia,serif; font-size:17px; color:#8b2e2e;
              white-space:nowrap; }}
  .card .l {{ font-size:9.5px; letter-spacing:.06em; text-transform:uppercase;
              color:#6f5b3e; margin-top:2px; }}
  .barra {{ background:#b08d3e; height:10px; display:inline-block;
            vertical-align:middle; border-radius:2px; }}
  .caixa-aviso {{ background:#fbf7ee; border:1px solid #d9cbaa;
                  border-left:4px solid #8b2e2e; border-radius:3px;
                  padding:10px 14px; font-size:11.5px; margin-bottom:12px;
                  break-inside:avoid; }}
  footer {{ margin-top:22px; padding-top:10px; border-top:3px double #b08d3e;
            font-size:10.5px; color:#6f5b3e; display:flex;
            justify-content:space-between; }}
  .no-print {{ position:fixed; top:14px; right:14px; }}
  .no-print button {{ font-size:14px; padding:8px 14px; cursor:pointer;
    background:#8b2e2e; color:#f5efe2; border:none; border-radius:3px; }}
  @media print {{ body {{ background:#fff; font-size:10pt; }}
    .pagina {{ max-width:none; padding:0; }} .no-print {{ display:none; }} }}
"""


def _pagina(titulo_doc, corpo, municipio, uf, periodo_txt, paisagem):
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
    return f"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8">
<title>{_e(titulo_doc)}</title><style>{_css(paisagem)}</style></head><body>
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


def render_contratacoes(d, municipio, uf, periodo_txt):
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
    return _pagina(titulo, corpo, municipio, uf, periodo_txt, paisagem=True)


def render_contratos(d, municipio, uf, periodo_txt):
    linhas = "".join(f"""<tr>
      <td class="ctr">{(_e(l['numero']) + "/" + _e(l['ano_contrato']))
                       if l['numero'] else _e(l['numero_controle'])}</td>
      <td class="ctr">{_e(l['fornecedor_nome'])}<br>
          <small>{_e(l['fornecedor_ni'])}</small></td>
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
    return _pagina(titulo, corpo, municipio, uf, periodo_txt, paisagem=True)


def render_atas(d, municipio, uf, periodo_txt):
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
    return _pagina(titulo, corpo, municipio, uf, periodo_txt, paisagem=True)


def render_fracionamento(d, municipio, uf):
    def farol(pct):
        if pct >= 100:
            return '<span style="color:#8b2e2e;font-weight:600">ACIMA DO LIMITE</span>'
        if pct >= 75:
            return '<span style="color:#8a6d1f;font-weight:600">Atenção</span>'
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
                   f"Exercício {d['ano']} · uso interno", paisagem=False)


MESES_NOME = ["jan", "fev", "mar", "abr", "mai", "jun",
              "jul", "ago", "set", "out", "nov", "dez"]


def render_executivo(d, municipio, uf):
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
      <small>{_e(f['fornecedor_ni'])}</small></td>
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
                   paisagem=False)


# ── geração (HTML + CSV) ────────────────────────────────────────────────────

def gerar(db, tipo, params, municipio, uf, destino):
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
        conteudo = render_executivo(d, municipio, uf)
        nome = f"resumo_executivo_{ano}"
        linhas_csv = None
    elif tipo == "fracionamento":
        if not ano:
            ano = date.today().year
        d = dados_fracionamento(db, ano, orgao, params.get("limites"))
        conteudo = render_fracionamento(d, municipio, uf)
        nome = f"alerta_fracionamento_{ano}"
        linhas_csv = d["dispensas"]
    else:
        periodo_txt = ("Vigentes em " + date.today().strftime("%d/%m/%Y")) \
            if vigentes else (f"Exercício {ano}" if ano else "Todo o período")
        if tipo == "contratacoes":
            d = dados_contratacoes(db, ano, params.get("modalidade"), orgao)
            conteudo = render_contratacoes(d, municipio, uf, periodo_txt)
        elif tipo == "contratos":
            d = dados_contratos(db, ano, vigentes, orgao)
            conteudo = render_contratos(d, municipio, uf, periodo_txt)
        elif tipo == "atas":
            d = dados_atas(db, ano, vigentes, orgao)
            conteudo = render_atas(d, municipio, uf, periodo_txt)
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
