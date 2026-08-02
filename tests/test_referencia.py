"""Blindagem do município de referência.

Município de referência alimenta **apenas o banco de preços**. Se um registro
dele vazar para a aba Contratações, para os KPIs, para o PCA ou — pior — para
um relatório entregue ao Tribunal de Contas, o documento sai errado.

Estes testes existem para que esse vazamento quebre o build, e não a
credibilidade de um processo. Ver design/BRIEFING-precos-referencia.md.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import licitarium
import pca_builder
import relatorios

ANO = 2026


@pytest.fixture
def api(tmp_path, monkeypatch):
    """Acervo com um processo do município e um de referência, lado a lado."""
    monkeypatch.setattr(licitarium, "DIR_DADOS", tmp_path)
    monkeypatch.setattr(licitarium, "ARQUIVO_DB", tmp_path / "t.db")
    db = licitarium.abrir_db()
    for controle, ref, valor in (("MEU-1", 0, 1000.0), ("REF-1", 1, 9999.0)):
        db.execute(
            "INSERT INTO contratacoes (numero_controle, ano, sequencial,"
            " orgao_cnpj, modalidade_id, modalidade_nome, situacao, objeto,"
            " valor_estimado, valor_homologado, data_publicacao,"
            " data_encerramento_proposta, referencia, raw)"
            " VALUES (?,?,1,'111',8,?,?,?,?,?,?,"
            " datetime('now','+10 day'),?,'{}')",
            (controle, ANO, f"Dispensa {controle}", f"Situacao {controle}",
             f"Objeto {controle}", valor, valor, f"{ANO}-02-01", ref))
        db.execute(
            "INSERT INTO itens (id, contratacao_controle, ano, sequencial,"
            " numero_item, descricao, unidade, quantidade,"
            " quantidade_homologada, valor_unitario_homologado,"
            " fornecedor_ni, data_resultado, referencia, raw)"
            " VALUES (?,?,?,1,1,'PAPEL SULFITE A4','RESMA',10,10,?,?,?,?,'{}')",
            (f"{controle}#1", controle, ANO, valor, f"ni{ref}",
             f"{ANO}-02-10", ref))
    db.commit()
    db.close()
    return licitarium.Api()


def _db():
    return licitarium.abrir_db()


# ── o que NÃO pode enxergar a referência ────────────────────────────────

def test_kpis_contam_so_o_municipio(api):
    k = api.get_estado()["kpis"]
    assert k["contratacoes"] == 1
    assert k["homologado_ano"] == 1000.0       # 9999 é de fora
    assert k["propostas_abertas"] == 1


def test_aba_contratacoes_nao_lista_referencia(api):
    r = api.listar("contratacoes", {})
    assert r["total"] == 1
    assert [i["numero_controle"] for i in r["itens"]] == ["MEU-1"]


def test_filtros_do_acervo_nao_oferecem_opcao_de_fora(api):
    f = api.filtros_disponiveis()
    assert all("REF-1" not in s for s in f["situacoes"])
    assert any("MEU-1" in s for s in f["situacoes"])


def test_relatorios_oficiais_nao_trazem_referencia(api):
    db = _db()
    try:
        d = relatorios.dados_contratacoes(db, ano=ANO)
        assert d["totais"]["n"] == 1
        assert d["totais"]["homologado"] == 1000.0

        e = relatorios.dados_executivo(db, ANO)
        assert sum(m["n"] for m in e["modalidades"]) == 1
        assert all("REF-1" not in (m["modalidade_nome"] or "")
                   for m in e["modalidades"])

        fr = relatorios.dados_fracionamento(db, ANO)
        assert sum(u["total"] for u in fr["unidades"]) == 1000.0
    finally:
        db.close()


def test_relatorio_gerado_nao_menciona_a_referencia(api, tmp_path):
    """A prova final: o HTML entregue ao TCE não pode citar processo alheio."""
    db = _db()
    try:
        for tipo in ("contratacoes", "executivo"):
            r = relatorios.gerar(db, tipo, {"ano": ANO}, "Orindiúva", "SP",
                                 tmp_path / "rel")
            html = Path(r["html"]).read_text(encoding="utf-8")
            assert "MEU-1" in html or "Objeto MEU-1" in html
            assert "REF-1" not in html, tipo
    finally:
        db.close()


def test_pca_projeta_so_as_compras_do_proprio_orgao(api):
    db = _db()
    try:
        grupos = pca_builder.consolidar(db)
        # um único grupo (mesma descrição), alimentado só pelo item de casa
        assert len(grupos) == 1
        g = grupos[0]
        # 10 unidades + a margem padrão de 10%; se somasse o item de fora
        # seriam 20 unidades e o preço unitário mudaria
        assert g["quantidade"] == 11.0
        assert g["valor_unitario"] == 1000.0
    finally:
        db.close()


# ── o que PRECISA enxergar a referência ─────────────────────────────────

def test_banco_de_precos_soma_os_dois(api):
    """O ponto do recurso: mais preços para a pesquisa do art. 23."""
    s = api.estatisticas_preco("papel sulfite")
    assert s["n"] == 2
    assert s["minimo"] == 1000.0 and s["maximo"] == 9999.0
    assert s["fornecedores"] == 2
    assert api.listar("itens", {"so_homologados": True})["total"] == 2


def test_relatorio_de_precos_usa_os_dois(api):
    db = _db()
    try:
        d = relatorios.dados_precos(db, "papel sulfite")
        assert len(d["linhas"]) == 2
    finally:
        db.close()


def test_banco_antigo_ganha_a_coluna_como_municipio_proprio(api):
    """Migração: acervo já baixado é todo do município do usuário."""
    db = _db()
    try:
        db.execute("ALTER TABLE contratacoes DROP COLUMN referencia")
        db.execute("INSERT INTO contratacoes (numero_controle, ano, raw)"
                   " VALUES ('ANTIGO', ?, '{}')", (ANO,))
        db.commit()
    finally:
        db.close()
    db = _db()                                    # reabre: migra
    try:
        assert db.execute("SELECT referencia FROM contratacoes"
                          " WHERE numero_controle='ANTIGO'").fetchone()[0] == 0
    finally:
        db.close()


# ── ciclo completo: adicionar, sincronizar, remover ─────────────────────

def test_sync_de_referencia_marca_origem_e_nao_cria_orgao(api, monkeypatch):
    """Fase 1 do município de referência: entra marcado e sem virar órgão."""
    import pncp
    from datetime import date
    api.adicionar_municipio_referencia("3536604", "Paulo de Faria", "SP")

    def fake_get(caminho, params, base=None, **kw):
        if base == pncp.BASE_PNCP:
            return None                       # sem itens neste teste
        if "contratacoes" not in caminho or params.get("pagina") != 1:
            return None
        ibge = params.get("codigoMunicipioIbge")
        if ibge != "3536604" or params["codigoModalidadeContratacao"] != 8:
            return None
        return {"data": [{"numeroControlePNCP": "PF-1", "anoCompra": ANO,
                          "sequencialCompra": 9,
                          "orgaoEntidade": {"cnpj": "999",
                                            "razaoSocial": "PREF PAULO DE FARIA"},
                          "objetoCompra": "Papel de outro municipio",
                          "valorTotalHomologado": 50.0,
                          "dataAtualizacao": "2026-03-01"}], "totalPaginas": 1}
    monkeypatch.setattr(pncp, "_get", fake_get)

    db = _db()
    try:
        pncp.sincronizar_tudo(db, "3534203")
        linha = db.execute("SELECT referencia, municipio_ibge FROM contratacoes"
                           " WHERE numero_controle='PF-1'").fetchone()
        assert (linha["referencia"], linha["municipio_ibge"]) == (1, "3536604")
        # o órgão de fora não pode entrar no filtro de órgãos do acervo
        assert not db.execute("SELECT 1 FROM orgaos WHERE cnpj='999'").fetchone()
    finally:
        db.close()
    # e continua fora da aba Contratações
    assert all(i["numero_controle"] != "PF-1"
               for i in api.listar("contratacoes", {})["itens"])


def test_remover_referencia_leva_os_dados_junto(api):
    api.adicionar_municipio_referencia("3536604", "Paulo de Faria", "SP")
    db = _db()
    try:
        db.execute("UPDATE contratacoes SET municipio_ibge='3536604'"
                   " WHERE referencia=1")
        db.execute("UPDATE itens SET municipio_ibge='3536604'"
                   " WHERE referencia=1")
        db.commit()
    finally:
        db.close()
    assert api.estatisticas_preco("papel sulfite")["n"] == 2

    assert api.remover_municipio_referencia("3536604")["ok"]
    assert api.listar_municipios_referencia() == []
    # o preço de fora sai do banco; o de casa fica intacto
    s = api.estatisticas_preco("papel sulfite")
    assert s["n"] == 1 and s["maximo"] == 1000.0
    assert api.listar("contratacoes", {})["total"] == 1


def test_nao_aceita_o_proprio_municipio_como_referencia(api):
    db = _db()
    try:
        import pncp
        pncp._config(db, "municipio_ibge", "3534203")
    finally:
        db.close()
    r = api.adicionar_municipio_referencia("3534203", "Orindiúva", "SP")
    assert r["ok"] is False
    assert api.listar_municipios_referencia() == []


def test_ordenacao_por_municipio_usa_o_nome_e_nao_o_codigo(api):
    """A tabela guarda o código IBGE; a ordem tem de ser a que se lê.

    Aqui o próprio município ("Orindiúva", vindo da config) vem depois do de
    referência no alfabeto, mas o código dele (3534203) é menor — ordenar
    pelo código daria a ordem inversa da esperada.
    """
    db = _db()
    try:
        import pncp
        pncp._config(db, "municipio_ibge", "3534203")
        pncp._config(db, "municipio_nome", "Orindiúva")
        db.execute("INSERT INTO municipios_referencia (ibge, nome, uf)"
                   " VALUES ('3505500', 'Barretos', 'SP')")
        db.execute("UPDATE itens SET municipio_ibge='3534203' WHERE referencia=0")
        db.execute("UPDATE itens SET municipio_ibge='3505500' WHERE referencia=1")
        db.commit()
    finally:
        db.close()

    asc = api.listar("itens", {"so_homologados": True,
                               "ord": "municipio", "dir": "asc"})["itens"]
    assert [i["municipio_nome"] for i in asc] == ["Barretos", "Orindiúva"]
    desc = api.listar("itens", {"so_homologados": True,
                                "ord": "municipio", "dir": "desc"})["itens"]
    assert [i["municipio_nome"] for i in desc] == ["Orindiúva", "Barretos"]


def test_descarte_de_item_nao_entra_no_resumo_nem_no_relatorio(api, tmp_path):
    """A pesquisa do art. 23 só vale sobre itens comparáveis.

    Buscar "papel higiênico" traz suporte de papel e locação de banheiro
    químico; quem julga a aderência é o usuário, e o que ele descarta não
    pode continuar puxando a média do documento.
    """
    s = api.estatisticas_preco("papel sulfite")
    assert (s["n"], s["maximo"]) == (2, 9999.0)

    s = api.estatisticas_preco("papel sulfite", excluidos=["REF-1#1"])
    assert (s["n"], s["maximo"]) == (1, 1000.0)

    db = _db()
    try:
        d = relatorios.dados_precos(db, "papel sulfite",
                                    excluidos=["REF-1#1"])
        assert len(d["linhas"]) == 1
        r = relatorios.gerar(db, "precos",
                             {"termo": "papel sulfite",
                              "excluidos": ["REF-1#1"]},
                             "Orindiúva", "SP", tmp_path / "rel")
        html = Path(r["html"]).read_text(encoding="utf-8")
        assert "9.999,00" not in html
    finally:
        db.close()


def test_descarte_vazio_nao_muda_nada(api):
    """Lista vazia ou nula não pode virar um NOT IN () inválido."""
    base = api.estatisticas_preco("papel sulfite")
    for vazio in (None, [], ["", None]):
        assert api.estatisticas_preco("papel sulfite", excluidos=vazio) == base
