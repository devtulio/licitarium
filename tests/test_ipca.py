"""Correção monetária pelo IPCA.

O acervo do piloto tem preços de 2022 a 2026 na mesma pesquisa, e a inflação
do período passa de 20%: comparar reais de 2022 com reais de 2026 subestima o
preço atual. A série mensal vem do Banco Central (SGS 433) e fica no banco.

O índice sai com semanas de atraso — em 2026-08-05 o último publicado era o de
junho. O programa corrige até onde o índice vai e declara isso, em vez de
projetar um número que ninguém publicou.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import licitarium
import relatorios

# variação mensal (%) de uma série curta e redonda, para conferir na mão
SERIE = [("2024-01", 1.0), ("2024-02", 1.0), ("2024-03", 0.0),
         ("2024-04", 2.0)]


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setattr(licitarium, "DIR_DADOS", tmp_path)
    monkeypatch.setattr(licitarium, "ARQUIVO_DB", tmp_path / "t.db")
    db = licitarium.abrir_db()
    db.executemany("INSERT INTO ipca (competencia, variacao) VALUES (?,?)",
                   SERIE)
    db.execute("INSERT INTO contratacoes (numero_controle, ano, sequencial,"
               " orgao_cnpj, objeto, data_publicacao)"
               " VALUES ('K',2024,9,'111','x','2024-01-10')")
    itens = [
        # (id, valor, data do resultado)
        ("I1", 100.0, "2024-01-20"),   # corrige por fev, mar e abr
        ("I2", 100.0, "2024-03-05"),   # corrige só por abr
        ("I3", 100.0, None),           # sem data própria: usa a publicação
    ]
    for id_, valor, data in itens:
        db.execute(
            "INSERT INTO itens (id, contratacao_controle, ano, sequencial,"
            " numero_item, descricao, unidade, quantidade,"
            " quantidade_homologada, valor_unitario_homologado,"
            " data_resultado, fornecedor_ni, raw)"
            " VALUES (?,'K',2024,9,1,'PAPEL A4','CX',1,1,?,?,'ni1','{}')",
            (id_, valor, data))
    db.commit()
    db.close()
    return licitarium.Api()


def _db():
    return licitarium.abrir_db()


# ── o cálculo ───────────────────────────────────────────────────────────

def test_fator_acumula_os_meses_seguintes_ao_da_compra(api):
    """O índice do mês da compra já está no preço pago."""
    db = _db()
    try:
        ipca = relatorios.fatores_ipca(db)
    finally:
        db.close()
    assert ipca["ate"] == "2024-04"
    # jan: fev(1%) × mar(0%) × abr(2%) = 1,0302
    assert ipca["fatores"]["2024-01"] == pytest.approx(1.0302)
    assert ipca["fatores"]["2024-03"] == pytest.approx(1.02)
    assert ipca["fatores"]["2024-04"] == pytest.approx(1.0)   # último mês


def test_corrige_pelo_mes_do_preco(api):
    db = _db()
    try:
        ipca = relatorios.fatores_ipca(db)
    finally:
        db.close()
    assert relatorios.corrigir(100.0, "2024-01-20", ipca) \
        == pytest.approx(103.02)
    assert relatorios.corrigir(100.0, "2024-03-05", ipca) \
        == pytest.approx(102.0)


def test_preco_posterior_ao_indice_nao_e_corrigido(api):
    db = _db()
    try:
        ipca = relatorios.fatores_ipca(db)
    finally:
        db.close()
    # maio ainda não tem índice publicado: corrigir seria inventar
    assert relatorios.corrigir(100.0, "2024-05-02", ipca) is None
    assert relatorios.corrigir(100.0, None, ipca) is None
    assert relatorios.corrigir(None, "2024-01-01", ipca) is None


def test_preco_anterior_a_serie_corrige_desde_o_primeiro_mes(api):
    db = _db()
    try:
        ipca = relatorios.fatores_ipca(db)
    finally:
        db.close()
    # a série começa em jan/2024; um preço de 2019 corrige ao menos por ela
    assert relatorios.corrigir(100.0, "2019-07-01", ipca) \
        == pytest.approx(103.02)


def test_sem_serie_no_banco_nao_corrige_nada(tmp_path, monkeypatch):
    monkeypatch.setattr(licitarium, "DIR_DADOS", tmp_path)
    monkeypatch.setattr(licitarium, "ARQUIVO_DB", tmp_path / "v.db")
    db = licitarium.abrir_db()
    try:
        ipca = relatorios.fatores_ipca(db)
    finally:
        db.close()
    assert ipca == {"ate": None, "fatores": {}}
    assert relatorios.corrigir(100.0, "2024-01-01", ipca) is None


def test_mes_por_extenso():
    assert relatorios.mes_por_extenso("2026-06") == "jun/2026"
    assert relatorios.mes_por_extenso(None) is None


# ── na ponte ────────────────────────────────────────────────────────────

def test_resumo_corrigido_declara_ate_quando(api):
    s = api.estatisticas_preco("papel a4", corrigir=True)
    assert s["corrigido"] and s["ipca_ate"] == "2024-04"
    assert s["ipca_ate_extenso"] == "abr/2024"
    assert s["n"] == 3 and s["sem_indice"] == 0
    # I2 corrigiu 2%, I1 e I3 (data da publicação, jan) corrigiram 3,02%
    assert s["minimo"] == pytest.approx(102.0)
    assert s["maximo"] == pytest.approx(103.02)


def test_resumo_sem_correcao_continua_com_o_preco_pago(api):
    s = api.estatisticas_preco("papel a4")
    assert not s.get("corrigido")
    assert s["minimo"] == s["maximo"] == 100.0


def test_item_sem_data_utilizavel_fica_de_fora_e_e_contado(api):
    db = _db()
    try:
        db.execute("UPDATE contratacoes SET data_publicacao=NULL")
        db.execute("UPDATE itens SET data_resultado=NULL WHERE id='I3'")
        db.commit()
    finally:
        db.close()
    s = api.estatisticas_preco("papel a4", corrigir=True)
    assert s["n"] == 2 and s["sem_indice"] == 1
    # 1 de 3 é um terço da série: a composição mudou, e isso tem de aparecer
    assert s["amostra_reduzida"] is True


def test_serie_inteira_corrigida_nao_acusa_amostra_reduzida(api):
    s = api.estatisticas_preco("papel a4", corrigir=True)
    assert s["sem_indice"] == 0 and s["amostra_reduzida"] is False


@pytest.mark.parametrize("n, sem_indice, esperado", [
    (100, 0, False),
    (100, 10, False),    # 9,1% da série original: abaixo do limiar
    (90, 10, True),      # 10% cravado
    (254, 76, True),     # o caso real de "instalação manutenção"
    (0, 5, True),        # nada sobrou: é o aviso mais necessário de todos
])
def test_limiar_da_amostra_reduzida(n, sem_indice, esperado):
    """A conta é sobre a série ORIGINAL — n é o que sobrou, não o total."""
    r = relatorios.marcar_amostra_reduzida({"n": n}, sem_indice)
    assert r["amostra_reduzida"] is esperado


def test_documento_explica_que_a_diferenca_nao_e_so_inflacao(api):
    """No papel, o alerta precisa estar escrito — ninguém vê o resumo depois.

    Sem esta frase, a mediana maior lê como inflação, quando pode ser o
    efeito de os preços recentes terem saído da série.
    """
    db = _db()
    try:
        db.execute("UPDATE contratacoes SET data_publicacao=NULL")
        db.execute("UPDATE itens SET data_resultado=NULL WHERE id='I3'")
        db.commit()
    finally:
        db.close()
    d = relatorios.dados_precos(db_aberto := _db(), "papel a4",
                                corrigir_ipca=True)
    db_aberto.close()
    assert d["resumo"]["amostra_reduzida"] is True
    html = relatorios.render_precos(d, "Orindiúva", "SP")
    assert "não decorre apenas da correção monetária" in html
    assert "33% dos coletados" in html


def test_lista_traz_o_valor_corrigido_de_cada_item(api):
    itens = {i["id"]: i for i in
             api.listar("itens", {"corrigir": True})["itens"]}
    assert itens["I1"]["corrigido"] == pytest.approx(103.02)
    assert itens["I3"]["corrigido"] == pytest.approx(103.02)  # data do processo
    # sem pedir correção, a chave nem aparece
    assert "corrigido" not in api.listar("itens", {})["itens"][0]


def test_por_conteudo_usa_o_valor_ja_corrigido(api):
    db = _db()
    try:
        db.execute("UPDATE itens SET descricao='PAPEL A4 C/100 FLS'")
        db.commit()
    finally:
        db.close()
    i = {x["id"]: x for x in
         api.listar("itens", {"corrigir": True})["itens"]}["I1"]
    # 103,02 / 100 folhas — e não 100,00 / 100, que divergiria do resumo
    assert i["por_conteudo"]["valor"] == pytest.approx(1.0302)


# ── no documento ────────────────────────────────────────────────────────

def test_documento_corrigido_declara_indice_e_data(api, tmp_path, selecionar_tudo):
    db = _db()
    try:
        selecionar_tudo(db, "papel a4")
        r = relatorios.gerar(db, "precos",
                             {"termo": "papel a4", "corrigir_ipca": True},
                             "Orindiúva", "SP", tmp_path / "rel")
        html = Path(r["html"]).read_text(encoding="utf-8")
    finally:
        db.close()
    assert "Correção monetária" in html
    assert "preços de abr/2024" in html
    assert "série 433 do Banco Central" in html
    assert "R$ 103,02" in html
    assert ">Corrigido</th>" in html


def test_documento_normal_nao_menciona_correcao(api, tmp_path, selecionar_tudo):
    db = _db()
    try:
        selecionar_tudo(db, "papel a4")
        r = relatorios.gerar(db, "precos", {"termo": "papel a4"},
                             "Orindiúva", "SP", tmp_path / "rel")
        html = Path(r["html"]).read_text(encoding="utf-8")
    finally:
        db.close()
    assert "Correção monetária" not in html
    assert "R$ 100,00" in html
