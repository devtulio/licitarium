"""Montagem de minuta do Plano de Contratações Anual (PCA).

Consolida os itens efetivamente contratados pelo município — que o
Licitarium já coleta do PNCP — em grupos, projeta o quantitativo do próximo
exercício e estima o preço. A saída é uma **minuta para revisão**: os itens
publicados no PNCP não trazem código de catálogo (CATMAT/CATSER), exigido no
PCA oficial, então a classificação final é sempre do gestor.
"""
import json
import re
import statistics
from datetime import datetime

# palavras que não ajudam a identificar o item
IRRELEVANTES = {"DE", "DA", "DO", "DAS", "DOS", "EM", "PARA", "COM", "E", "A",
                "O", "AS", "OS", "NA", "NO", "AO", "POR", "SEM", "SOB"}
# lotes lançados como item único não representam consumo de nada
PADRAO_LOTE = re.compile(r"TODOS\s+OS\s+ITENS|LOTE\s+[ÚU]NICO", re.IGNORECASE)
# abertura burocrática que aparece em metade dos editais e não identifica nada
PREFIXOS_VAZIOS = re.compile(
    r"^(?:(?:AQUISI[ÇC][ÃA]O|CONTRATA[ÇC][ÃA]O|PRESTA[ÇC][ÃA]O|FORNECIMENTO|"
    r"LOCA[ÇC][ÃA]O|REGISTRO)\s+(?:DE\s+)?(?:PRE[ÇC]OS?\s+(?:PARA\s+)?)?"
    r"(?:EMPRESA\s+)?(?:ESPECIALIZADA\s+)?(?:PARA\s+)?(?:A\s+)?)+")
# preço muito disperso dentro do grupo denuncia lote disfarçado de item
DISPERSAO_SUSPEITA = 10

PALAVRAS_CHAVE_PADRAO = 3
MARGEM_PADRAO = 10.0
BASES = ("media", "ultimo", "maior", "soma")
ESTATISTICAS = ("mediana", "media", "recente", "menor")


def chave_agrupamento(descricao, palavras=PALAVRAS_CHAVE_PADRAO):
    """Radical da descrição: maiúsculas, sem pontuação e sem palavras vazias.

    Prefixos de praxe ("AQUISIÇÃO DE", "CONTRATAÇÃO DE EMPRESA PARA") são
    descartados: eles abrem metade dos editais e nada dizem sobre o item.
    """
    limpo = re.sub(r"[^0-9A-ZÁÂÃÉÊÍÓÔÕÚÇ ]", " ", (descricao or "").upper())
    limpo = PREFIXOS_VAZIOS.sub("", limpo.strip(), count=1)
    termos = [t for t in limpo.split() if t not in IRRELEVANTES]
    return " ".join(termos[:palavras])


def familia(chave):
    """Primeiro termo da chave: PNEU 295 80R22 e PNEU 275 80R22 são itens
    diferentes no plano, mas o gestor revisa melhor vendo-os juntos."""
    return (chave or "").split(" ")[0] if chave else ""


def classificar_abc(itens):
    """Curva ABC por valor: A concentra 80% do total, B 15%, C o resto.

    Diz ao gestor onde vale gastar o tempo de revisão — normalmente poucos
    itens respondem pela maior parte do plano.
    """
    validos = [i for i in itens if (i.get("valor_total") or 0) > 0]
    total = sum(i["valor_total"] for i in validos)
    for i in itens:
        i["abc"] = "C"
    if not total:
        return itens
    acumulado = 0.0
    for i in sorted(validos, key=lambda x: -x["valor_total"]):
        acumulado += i["valor_total"]
        fatia = acumulado / total
        i["abc"] = "A" if fatia <= 0.8 else ("B" if fatia <= 0.95 else "C")
    return itens


def _preco(valores, datas, estatistica):
    if not valores:
        return None
    if estatistica == "media":
        return statistics.mean(valores)
    if estatistica == "menor":
        return min(valores)
    if estatistica == "recente":
        # o mais recente pelo par (data, valor); data ausente vai para o fim
        return max(zip(datas, valores), key=lambda dv: (dv[0] or ""))[1]
    return statistics.median(valores)


def _quantidade(por_ano, base):
    anos = sorted(por_ano)
    if not anos:
        return 0.0
    if base == "ultimo":
        return por_ano[anos[-1]]
    if base == "maior":
        return max(por_ano.values())
    if base == "soma":
        return sum(por_ano.values())
    return sum(por_ano.values()) / len(anos)          # média dos anos


def consolidar(db, anos=None, palavras=PALAVRAS_CHAVE_PADRAO,
               base="media", estatistica="mediana", margem=MARGEM_PADRAO,
               orgao=None, so_recorrentes=False):
    """Agrupa os itens contratados e projeta o próximo exercício."""
    where = ["valor_unitario_homologado IS NOT NULL"]
    args = []
    if anos:
        where.append("ano IN (%s)" % ",".join("?" * len(anos)))
        args += list(anos)
    if orgao:
        where.append("orgao_cnpj=?")
        args.append(orgao)
    linhas = db.execute(
        f"""SELECT descricao, unidade, material_servico, ano,
                   COALESCE(quantidade_homologada, quantidade) qtd,
                   valor_unitario_homologado unit, data_resultado
            FROM itens WHERE {' AND '.join(where)}""", args).fetchall()

    grupos = {}
    for l in linhas:
        if PADRAO_LOTE.search(l["descricao"] or ""):
            continue                      # lote inteiro como item único
        k = chave_agrupamento(l["descricao"], palavras)
        if not k:
            continue
        g = grupos.setdefault(k, {
            "chave": k, "descricoes": [], "unidades": [], "categorias": [],
            "por_ano": {}, "precos": [], "datas": [], "itens": 0})
        g["descricoes"].append(l["descricao"])
        g["unidades"].append(l["unidade"])
        g["categorias"].append(l["material_servico"])
        g["por_ano"][l["ano"]] = g["por_ano"].get(l["ano"], 0) + (l["qtd"] or 0)
        g["precos"].append(l["unit"])
        g["datas"].append(l["data_resultado"])
        g["itens"] += 1

    resultado = []
    for g in grupos.values():
        qtd_base = _quantidade(g["por_ano"], base)
        unit = _preco(g["precos"], g["datas"], estatistica)
        qtd = round(qtd_base * (1 + margem / 100.0), 2)
        # descrição mais frequente representa o grupo melhor que a primeira
        descricao = statistics.mode(g["descricoes"])
        # obra/serviço contratado uma única vez não é consumo recorrente:
        # projetar "reforma do prédio X" para o ano seguinte seria errado
        recorrente = len(g["por_ano"]) > 1 or g["itens"] > 2
        resultado.append({
            "recorrente": recorrente,
            "chave": g["chave"],
            "familia": familia(g["chave"]),
            "descricao": descricao,
            "unidade": statistics.mode(g["unidades"]) if any(g["unidades"]) else None,
            "categoria": statistics.mode(g["categorias"]) if any(g["categorias"]) else None,
            "quantidade_base": round(qtd_base, 2),
            "quantidade": qtd,
            "margem": margem,
            "valor_unitario": round(unit, 2) if unit is not None else None,
            "valor_total": round(qtd * unit, 2) if unit is not None else None,
            "itens": g["itens"],
            "anos": sorted(g["por_ano"]),
            "por_ano": g["por_ano"],
            "unidades_divergentes": len({u for u in g["unidades"] if u}) > 1,
            "preco_min": min(g["precos"]),
            "preco_max": max(g["precos"]),
            "preco_disperso": (min(g["precos"]) > 0
                               and max(g["precos"]) / min(g["precos"])
                               >= DISPERSAO_SUSPEITA),
        })
    if so_recorrentes:
        resultado = [r for r in resultado if r["recorrente"]]
    resultado.sort(key=lambda r: -(r["valor_total"] or 0))
    return resultado


# ── minuta persistida ───────────────────────────────────────────────────────

def gerar_minuta(db, ano_alvo, params, orgao=None):
    """Gera (ou regenera) a minuta do exercício, preservando o que foi editado."""
    params = dict(params or {})
    palavras = int(params.get("palavras") or PALAVRAS_CHAVE_PADRAO)
    base = params.get("base") if params.get("base") in BASES else "media"
    est = params.get("estatistica")
    est = est if est in ESTATISTICAS else "mediana"
    margem = float(params.get("margem", MARGEM_PADRAO))
    anos = params.get("anos") or None
    so_recorrentes = bool(params.get("so_recorrentes"))

    editados = {r["chave"]: r for r in db.execute(
        "SELECT * FROM pca_minuta_itens WHERE ano_alvo=? AND editado=1",
        (ano_alvo,))}
    db.execute("DELETE FROM pca_minuta_itens WHERE ano_alvo=?", (ano_alvo,))

    grupos = consolidar(db, anos, palavras, base, est, margem, orgao,
                        so_recorrentes)
    for g in grupos:
        antigo = editados.get(g["chave"])
        if antigo:   # edição manual prevalece sobre o recálculo
            db.execute(
                """INSERT INTO pca_minuta_itens
                   (ano_alvo, chave, descricao, unidade, categoria, quantidade,
                    valor_unitario, margem, incluir, editado, origem)
                   VALUES (?,?,?,?,?,?,?,?,?,1,?)""",
                (ano_alvo, g["chave"], antigo["descricao"], antigo["unidade"],
                 antigo["categoria"], antigo["quantidade"],
                 antigo["valor_unitario"], antigo["margem"], antigo["incluir"],
                 json.dumps(g, ensure_ascii=False, default=str)))
        else:
            db.execute(
                """INSERT INTO pca_minuta_itens
                   (ano_alvo, chave, descricao, unidade, categoria, quantidade,
                    valor_unitario, margem, incluir, editado, origem)
                   VALUES (?,?,?,?,?,?,?,?,1,0,?)""",
                (ano_alvo, g["chave"], g["descricao"], g["unidade"],
                 g["categoria"], g["quantidade"], g["valor_unitario"],
                 g["margem"], json.dumps(g, ensure_ascii=False, default=str)))
    db.execute(
        "INSERT OR REPLACE INTO pca_minuta (ano_alvo, parametros, gerado_em)"
        " VALUES (?,?,?)",
        (ano_alvo, json.dumps({"palavras": palavras, "base": base,
                               "estatistica": est, "margem": margem,
                               "anos": anos, "orgao": orgao,
                               "so_recorrentes": so_recorrentes},
                              ensure_ascii=False),
         datetime.now().isoformat()))
    db.commit()
    return len(grupos)


def listar_minuta(db, ano_alvo, so_incluidos=False):
    sql = "SELECT * FROM pca_minuta_itens WHERE ano_alvo=?"
    if so_incluidos:
        sql += " AND incluir=1"
    sql += " ORDER BY (quantidade * COALESCE(valor_unitario,0)) DESC"
    itens = []
    for r in db.execute(sql, (ano_alvo,)):
        d = dict(r)
        d["origem"] = json.loads(d["origem"]) if d.get("origem") else {}
        d["valor_total"] = round((d["quantidade"] or 0)
                                 * (d["valor_unitario"] or 0), 2)
        d["familia"] = d["origem"].get("familia") or familia(d["chave"])
        d["mesclado"] = bool(d.get("mesclado_de"))
        itens.append(d)
    return classificar_abc(itens)


def resumo_familias(itens):
    """Agrupa a minuta por família para a revisão em dois níveis."""
    familias = {}
    for i in itens:
        f = familias.setdefault(i["familia"] or "—",
                                {"familia": i["familia"] or "—",
                                 "itens": 0, "valor": 0.0, "excluidos": 0})
        f["itens"] += 1
        if i.get("incluir", 1):
            f["valor"] += i["valor_total"]
        else:
            f["excluidos"] += 1
    return sorted(familias.values(), key=lambda f: -f["valor"])


def mesclar(db, ano_alvo, ids):
    """Funde itens num só: soma quantidades e pondera o preço pelo volume."""
    if len(ids) < 2:
        return {"ok": False, "erro": "selecione ao menos dois itens"}
    marcas = ",".join("?" * len(ids))
    linhas = [dict(r) for r in db.execute(
        f"SELECT * FROM pca_minuta_itens WHERE ano_alvo=? AND id IN ({marcas})",
        [ano_alvo] + list(ids))]
    if len(linhas) < 2:
        return {"ok": False, "erro": "itens não encontrados"}
    qtd = sum(l["quantidade"] or 0 for l in linhas)
    valor = sum((l["quantidade"] or 0) * (l["valor_unitario"] or 0)
                for l in linhas)
    unit = (valor / qtd) if qtd else max(
        (l["valor_unitario"] or 0) for l in linhas)
    principal = max(linhas, key=lambda l: (l["quantidade"] or 0)
                    * (l["valor_unitario"] or 0))
    db.execute(f"DELETE FROM pca_minuta_itens WHERE id IN ({marcas})", list(ids))
    db.execute(
        """INSERT INTO pca_minuta_itens
           (ano_alvo, chave, descricao, unidade, categoria, quantidade,
            valor_unitario, margem, incluir, editado, origem, mesclado_de)
           VALUES (?,?,?,?,?,?,?,?,1,1,?,?)""",
        (ano_alvo, principal["chave"], principal["descricao"],
         principal["unidade"], principal["categoria"], round(qtd, 2),
         round(unit, 2), principal["margem"], principal["origem"],
         json.dumps(linhas, ensure_ascii=False, default=str)))
    db.commit()
    return {"ok": True, "itens": len(linhas)}


def dividir(db, item_id):
    """Desfaz uma mesclagem, devolvendo os itens como estavam."""
    linha = db.execute("SELECT * FROM pca_minuta_itens WHERE id=?",
                       (item_id,)).fetchone()
    if not linha or not linha["mesclado_de"]:
        return {"ok": False, "erro": "este item não veio de uma mesclagem"}
    originais = json.loads(linha["mesclado_de"])
    db.execute("DELETE FROM pca_minuta_itens WHERE id=?", (item_id,))
    for o in originais:
        db.execute(
            """INSERT INTO pca_minuta_itens
               (ano_alvo, chave, descricao, unidade, categoria, quantidade,
                valor_unitario, margem, incluir, editado, origem, mesclado_de)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (o["ano_alvo"], o["chave"], o["descricao"], o["unidade"],
             o["categoria"], o["quantidade"], o["valor_unitario"], o["margem"],
             o["incluir"], o["editado"], o["origem"], o.get("mesclado_de")))
    db.commit()
    return {"ok": True, "itens": len(originais)}


def totais(itens):
    incluidos = [i for i in itens if i.get("incluir", 1)]
    return {"grupos": len(incluidos),
            "valor": round(sum(i["valor_total"] for i in incluidos), 2),
            "excluidos": len(itens) - len(incluidos)}
