"""Análise estatística do banco de preços, filtro por unidade e ordenação.

A pesquisa de preços do art. 23 é assinada por alguém: os números que ela
mostra precisam ser os mesmos que uma calculadora daria, e o que o programa
chama de "fora da curva" precisa ter critério, não intuição.
"""
import statistics
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import licitarium
import relatorios

ANO = 2026
# unidades como o PNCP entrega: mesma coisa escrita de seis jeitos
ITENS = [
    # (id, descrição, unidade, quantidade, valor unitário)
    ("I1", "PAPEL SULFITE A4 75G", "CX", 2000, 219.90),
    ("I2", "PAPEL SULFITE A4 BRANCO", "Caixa", 80, 232.80),
    ("I3", "PAPEL SULFITE A4 5000 FLS", "caixa  ", 11, 275.00),
    ("I4", "PAPEL SULFITE A4 RESMA", "CAIXAS", 500, 208.04),
    ("I5", "PAPEL A4 COLORIDO", "PCT", 50, 8.60),
    ("I6", "PAPEL A4 CARBONO", "Pacote 400,00 G", 60, 52.50),
    ("I7", "FORNECIMENTO DE PAPEL A4 TIMBRADO", "Serviço", 1, 1490.00),
]


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setattr(licitarium, "DIR_DADOS", tmp_path)
    monkeypatch.setattr(licitarium, "ARQUIVO_DB", tmp_path / "t.db")
    db = licitarium.abrir_db()
    db.execute(
        "INSERT INTO contratacoes (numero_controle, ano, sequencial,"
        " orgao_cnpj, objeto, data_publicacao) VALUES ('K',?,1,'111','x',?)",
        (ANO, f"{ANO}-01-01"))
    for i, (id_, desc, unidade, qtd, valor) in enumerate(ITENS, 1):
        db.execute(
            "INSERT INTO itens (id, contratacao_controle, ano, sequencial,"
            " numero_item, descricao, unidade, quantidade,"
            " quantidade_homologada, valor_unitario_homologado,"
            " fornecedor_ni, raw)"
            " VALUES (?,'K',?,1,?,?,?,?,?,?,?,'{}')",
            (id_, ANO, i, desc, unidade, qtd, qtd, valor, f"ni{i}"))
    db.commit()
    db.close()
    return licitarium.Api()


# ── o cálculo em si ─────────────────────────────────────────────────────

def test_resumo_bate_com_a_biblioteca_padrao():
    valores = [10.0, 12.0, 13.0, 15.0, 40.0, 11.0, 14.0]
    r = relatorios.resumo_estatistico(valores)
    assert r["n"] == 7
    assert r["media"] == pytest.approx(statistics.fmean(valores))
    assert r["mediana"] == pytest.approx(statistics.median(valores))
    assert r["desvio"] == pytest.approx(statistics.stdev(valores))
    assert r["cv"] == pytest.approx(r["desvio"] / r["media"])
    assert r["minimo"] == 10.0 and r["maximo"] == 40.0
    assert r["amplitude"] == pytest.approx(30.0)


def test_quartis_por_interpolacao_linear():
    # série 1..9: Q1=3, mediana=5, Q3=7 pelo método da interpolação
    r = relatorios.resumo_estatistico([float(x) for x in range(1, 10)])
    assert (r["q1"], r["mediana"], r["q3"]) == (3.0, 5.0, 7.0)
    assert r["iqr"] == pytest.approx(4.0)
    # Tukey: 1,5 × IQR para cada lado
    assert r["limite_inf"] == pytest.approx(-3.0)
    assert r["limite_sup"] == pytest.approx(13.0)


def test_amostra_pequena_nao_ganha_quartil_nem_outlier():
    """Com quatro preços, Q1 e Q3 seriam quase o menor e o maior.

    Chamar um deles de "fora da curva" nesse tamanho seria opinião com
    aparência de estatística — a análise se cala e o resumo continua.
    """
    r = relatorios.resumo_estatistico([10.0, 12.0, 14.0, 900.0])
    assert r["n"] == 4 and r["desvio"] is not None
    assert "q1" not in r and "limite_sup" not in r


def test_um_preco_so_nao_tem_dispersao():
    r = relatorios.resumo_estatistico([42.0])
    assert r["n"] == 1 and r["media"] == r["mediana"] == 42.0
    assert "desvio" not in r


def test_serie_vazia_nao_inventa_resumo():
    assert relatorios.resumo_estatistico([]) is None


# ── na ponte: o que a tela recebe ───────────────────────────────────────

def test_estatisticas_de_preco_trazem_dispersao_e_apontam_o_extremo(api):
    s = api.estatisticas_preco("papel a4")
    valores = sorted(v for *_, v in ITENS)
    assert s["n"] == len(ITENS)
    assert s["media"] == pytest.approx(statistics.fmean(valores))
    assert s["desvio"] == pytest.approx(statistics.stdev(valores))
    # o serviço de papel timbrado (R$ 1.490,00) destoa das resmas
    assert s["fora_da_curva"] == ["I7"]
    assert s["maximo"] > s["limite_sup"]


def test_relatorio_de_precos_tem_o_grafico_de_dispersao(api, tmp_path):
    """Pedido do usuário (2026-08-08): os 6 números (mín/Q1/mediana/média/
    Q3/máx) já apareciam em texto — o gráfico (caixa de Tukey) mostra a
    distância entre mediana e média num olhar só, sem obrigar a ler os
    números e fazer a conta de cabeça. I7 (R$ 1.490,00) é o extremo real
    desta fixture, então tem de acender o aviso de "fora da faixa"."""
    db = licitarium.abrir_db()
    r = relatorios.gerar(db, "precos", {"termo": "papel a4"},
                         "T", "SP", tmp_path)
    db.close()
    html = Path(r["html"]).read_text(encoding="utf-8")
    assert html.count("<svg") >= 1
    assert "faixa entre Q1 e Q3" in html
    assert "fora da faixa esperada" in html


def _linhas_y(svg, classe):
    import re
    return [float(m.group(1)) for m in re.finditer(
        rf'<text class="{classe}" x="[\d.]+" y="([\d.]+)"', svg)]


def test_grafico_de_dispersao_empilha_rotulos_que_colidem():
    """Achado do usuário (2026-08-08), com print real: mediana e média perto
    uma da outra tinham o texto sobreposto — mesma família de bug do C1 da
    agenda do Painel (design/DASHBOARD.md), resolvida empilhando em duas
    fileiras em vez de cortar (aqui não sobra caractere pra cortar)."""
    # números fixos (não vêm de resumo_estatistico) pra controlar exatamente
    # a distância entre mediana e média nos dois casos
    base = {"limite_inf": -100, "limite_sup": 200}
    perto = {**base, "minimo": 5.25, "q1": 6.00, "mediana": 6.90,
             "media": 6.96, "q3": 7.83, "maximo": 9.25}
    svg = relatorios._grafico_dispersao(perto, relatorios.moeda)
    ys = _linhas_y(svg, "rot")
    # seis rótulos, dois em fileiras diferentes — nem todos na mesma linha
    assert len(set(ys)) == 2

    longe = {**base, "minimo": 0, "q1": 20, "mediana": 40,
             "media": 70, "q3": 85, "maximo": 100}
    svg2 = relatorios._grafico_dispersao(longe, relatorios.moeda)
    ys2 = _linhas_y(svg2, "rot")
    assert len(set(ys2)) == 1   # bem espaçados, cabem numa fileira só


def test_grafico_de_dispersao_fileiras_nao_se_encostam():
    """Print real do usuário (2026-08-08): com passo de 22px entre
    fileiras, "média" (R$ 6,93) e "mediana" (R$ 6,96) ainda quase se
    sobrescreviam — 22px cabe o nome sozinho, mas não o bloco nome+valor
    inteiro (14px de vão entre as duas linhas). O vão entre o valor de uma
    fileira e o nome da próxima tem de ser pelo menos o mesmo das duas
    linhas dentro da mesma fileira, senão a segunda fileira não resolve
    nada."""
    base = {"limite_inf": -100, "limite_sup": 200}
    r = {**base, "minimo": 5.0, "q1": 6.40, "mediana": 6.96,
         "media": 6.93, "q3": 7.50, "maximo": 9.0}
    svg = relatorios._grafico_dispersao(r, relatorios.moeda)
    import re
    linhas = {(m.group(1), m.group(3)): float(m.group(2)) for m in re.finditer(
        r'<text class="(rot|val)" x="[\d.]+" y="([\d.]+)"[^>]*>([^<]+)</text>',
        svg)}
    vao_intra = linhas[("val", "R$ 6,93")] - linhas[("rot", "média")]
    vao_entre_fileiras = (linhas[("rot", "mediana")]
                          - linhas[("val", "R$ 6,93")])
    assert vao_entre_fileiras >= vao_intra


def test_item_descartado_sai_da_conta_e_refaz_a_analise(api):
    antes = api.estatisticas_preco("papel a4")
    depois = api.estatisticas_preco("papel a4", excluidos=["I7"])
    assert depois["n"] == antes["n"] - 1
    assert depois["media"] < antes["media"]
    assert depois["maximo"] == 275.00


# ── unidade de medida ───────────────────────────────────────────────────

@pytest.mark.parametrize("texto, grupo", [
    ("CX", "Caixa"), ("Caixa", "Caixa"), ("caixa  ", "Caixa"),
    ("CAIXAS", "Caixa"), ("UN", "Unidade"), ("Unidade ", "Unidade"),
    ("UND", "Unidade"), ("KG", "Quilograma"), ("Quilograma", "Quilograma"),
    ("SERVIÇO", "Serviço"), ("SV", "Serviço"), ("PÇ", "Peça"),
    # achado do usuário (2026-08-08): MAÇO e MÇ eram grupos diferentes —
    # "Maço" não estava no mapa de sinônimos
    ("MAÇO", "Maço"), ("MÇ", "Maço"), ("Maço", "Maço"), ("MACOS", "Maço"),
    # o PNCP cola a quantidade na unidade; o grupo é a palavra
    ("Embalagem 1,00 KG", "Embalagem"), ("Pacote 400,00 G", "Pacote"),
    ("Frasco 10,00 ML", "Frasco"),
    # o que não está no mapa continua legível, não vira "outros"
    ("BANDEJA", "Bandeja"), ("", None), (None, None),
])
def test_unidade_canonica(texto, grupo):
    assert licitarium._unidade_canonica(texto) == grupo


def test_filtro_por_unidade_junta_as_grafias(api):
    r = api.listar("itens", {"busca": "papel a4", "unidade": "Caixa"})
    assert r["total"] == 4          # CX, Caixa, "caixa  " e CAIXAS
    assert {i["id"] for i in r["itens"]} == {"I1", "I2", "I3", "I4"}
    # e o item continua exibindo a unidade que o órgão publicou
    assert {i["unidade"] for i in r["itens"]} == {"CX", "Caixa", "caixa  ",
                                                 "CAIXAS"}


def test_lista_de_unidades_vem_agrupada_e_pela_frequencia(api):
    unidades = api.filtros_disponiveis()["unidades"]
    assert [u["nome"] for u in unidades][:1] == ["Caixa"]
    assert {u["nome"]: u["n"] for u in unidades} == {
        "Caixa": 4, "Pacote": 2, "Serviço": 1}


def test_classificar_por_unidade_marca_so_a_escolhida(api):
    """Pedido do usuário (2026-08-08): buscar "alface" mistura maço, quilo
    e unidade — escolher uma unidade tem de marcar só os itens dela, sobre
    a pesquisa inteira (não só a página que a tela mostra no momento). A
    busca já abre com tudo desmarcado (mesmo pedido), então "os outros" só
    precisam ficar de fora — não precisam mais de justificativa."""
    r = api.classificar_por_unidade("papel a4", "Caixa")
    assert r == {"ok": True, "n": 4}       # só I1-I4 (Caixa)

    assert set(api.selecionados("papel a4")) == {"I1", "I2", "I3", "I4"}
    assert api.descartes("papel a4") == []  # nada precisou de justificativa

    s = api.estatisticas_preco("papel a4",
                               incluidos=api.selecionados("papel a4"))
    assert s["n"] == 4


def test_classificar_por_unidade_acumula_em_vez_de_substituir(api):
    """Pedido do usuário (2026-08-08): escolher "Maço" e depois "Unidade"
    tem de deixar as duas dentro — trocar de unidade não pode apagar a
    escolha anterior."""
    api.classificar_por_unidade("papel a4", "Caixa")
    api.classificar_por_unidade("papel a4", "Pacote")
    # Caixa (I1-I4) continua, Pacote (I5, I6) se soma
    assert set(api.selecionados("papel a4")) == \
        {"I1", "I2", "I3", "I4", "I5", "I6"}
    assert api.descartes("papel a4") == []


# ── seleção da pesquisa de preços ───────────────────────────────────────
# Pedido do usuário (2026-08-08): a busca abria com tudo marcado; agora
# abre com tudo desmarcado — marcar é ato positivo, sem justificativa.

def test_busca_nova_nao_tem_nada_selecionado(api):
    assert api.selecionados("papel a4") == []
    s = api.estatisticas_preco("papel a4", incluidos=[])
    # total conta a busca inteira (pro contador "X de Y"), mesmo sem nada
    # selecionado ainda
    assert s == {"n": 0, "nada_selecionado": True, "total": 7}


def test_selecionar_e_desselecionar_um_item(api):
    api.selecionar_preco("papel a4", "I1")
    assert api.selecionados("papel a4") == ["I1"]
    s = api.estatisticas_preco("papel a4", incluidos=["I1"])
    assert s["n"] == 1 and s["maximo"] == 219.90

    api.desselecionar_preco("papel a4", "I1")
    assert api.selecionados("papel a4") == []


def test_selecionar_desfaz_descarte_anterior(api):
    """Reconsiderar depois de ter tirado é o caminho normal — não deve
    sobrar um descarte fantasma pra um item que voltou a ser escolhido."""
    api.descartar_preco("papel a4", "I1", "nao_comparavel")
    api.selecionar_preco("papel a4", "I1")
    assert api.selecionados("papel a4") == ["I1"]
    assert api.descartes("papel a4") == []


def test_selecionar_todos_marca_a_pesquisa_inteira(api):
    r = api.selecionar_todos_precos("papel a4")
    assert r == {"ok": True, "n": 7}
    assert set(api.selecionados("papel a4")) == {f"I{i}" for i in range(1, 8)}
    assert api.descartes("papel a4") == []
    s = api.estatisticas_preco("papel a4",
                               incluidos=api.selecionados("papel a4"))
    assert s["n"] == 7


def test_selecionar_todos_limpa_descartes_anteriores(api):
    api.descartar_preco("papel a4", "I1", "nao_comparavel")
    api.selecionar_todos_precos("papel a4")
    assert api.descartes("papel a4") == []
    assert "I1" in api.selecionados("papel a4")


def test_desselecionar_todos_zera_a_selecao(api):
    api.selecionar_todos_precos("papel a4")
    api.desselecionar_preco("papel a4")
    assert api.selecionados("papel a4") == []


def test_relatorio_de_precos_segue_a_selecao_da_tela(api, tmp_path):
    """O documento tem de sair sobre a mesma seleção que a tela mostrava —
    não sobre tudo que a busca trouxe (achado do usuário, 2026-08-08)."""
    api.classificar_por_unidade("papel a4", "Caixa")
    db = licitarium.abrir_db()
    r = relatorios.gerar(db, "precos", {"termo": "papel a4"},
                         "T", "SP", tmp_path)
    db.close()
    from pathlib import Path as _Path
    html = _Path(r["html"]).read_text(encoding="utf-8")
    assert "5000 FLS" in html                       # I3 (Caixa), presente
    assert "TIMBRADO" not in html                   # I7 (Serviço), fora


# ── filtros que selecionam (2026-08-08, propostos e pedidos pelo usuário) ──
# unidade, fornecedor, faixa de valor e texto contido acumulam na seleção,
# nunca substituem — a mesma regra do achado 2 acima.

def test_total_conta_a_busca_inteira_mesmo_sem_selecao(api):
    """Pro contador "X de Y selecionados" da tela: total não olha seleção
    nem descarte, sempre a busca inteira."""
    s = api.estatisticas_preco("papel a4", incluidos=[])
    assert s["total"] == 7
    api.selecionar_preco("papel a4", "I1")
    s = api.estatisticas_preco("papel a4", incluidos=["I1"])
    assert s["n"] == 1 and s["total"] == 7


def test_fornecedores_da_pesquisa_vem_do_mais_frequente(api):
    fornecedores = api.fornecedores_pesquisa_precos("papel a4")
    assert len(fornecedores) == 7          # um fornecedor por item, nesta fixture
    assert {f["ni"] for f in fornecedores} == {f"ni{i}" for i in range(1, 8)}


def test_selecionar_por_fornecedor_acumula(api):
    api.classificar_por_unidade("papel a4", "Caixa")     # I1-I4
    r = api.selecionar_por_fornecedor("papel a4", "ni7")  # I7 (Serviço)
    assert r == {"ok": True, "n": 1}
    assert set(api.selecionados("papel a4")) == {"I1", "I2", "I3", "I4", "I7"}


def test_selecionar_por_faixa_de_valor(api):
    r = api.selecionar_por_faixa("papel a4", minimo=200, maximo=280)
    assert r["ok"] and r["n"] == 4           # I1, I2, I3, I4
    assert set(api.selecionados("papel a4")) == {"I1", "I2", "I3", "I4"}


def test_selecionar_por_faixa_aceita_so_um_lado(api):
    api.selecionar_por_faixa("papel a4", minimo=1000)
    assert api.selecionados("papel a4") == ["I7"]   # só o de R$ 1.490,00


def test_selecionar_por_texto_contido(api):
    r = api.selecionar_por_texto("papel a4", "SULFITE")
    assert r["ok"] and r["n"] == 4           # I1-I4 têm "SULFITE" na descrição
    assert set(api.selecionados("papel a4")) == {"I1", "I2", "I3", "I4"}


def test_selecionar_por_texto_acumula_sobre_selecao_existente(api):
    api.selecionar_por_faixa("papel a4", minimo=1000)      # I7
    api.selecionar_por_texto("papel a4", "SULFITE")        # I1-I4
    assert set(api.selecionados("papel a4")) == \
        {"I1", "I2", "I3", "I4", "I7"}


# ── ordenação ───────────────────────────────────────────────────────────

def test_coluna_quantidade_ordena(api):
    r = api.listar("itens", {"ord": "quantidade", "dir": "desc"})
    assert [i["id"] for i in r["itens"]][:3] == ["I1", "I4", "I2"]
    r = api.listar("itens", {"ord": "quantidade", "dir": "asc"})
    assert [i["id"] for i in r["itens"]][:3] == ["I7", "I3", "I5"]
