"""Adicionar órgão manualmente: só entra depois de confirmado no PNCP.

Contratos/atas são baixados por CNPJ isolado (a API não filtra por
município nessa fase) — um CNPJ de outra prefeitura entraria sem
processo-mãe e contaminaria os relatórios oficiais, que confiam em
`referencia=0` para separar o que é nosso do que não é.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import licitarium
import pncp


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setattr(licitarium, "DIR_DADOS", tmp_path)
    monkeypatch.setattr(licitarium, "ARQUIVO_DB", tmp_path / "t.db")
    db = licitarium.abrir_db()
    db.execute("INSERT INTO config (chave, valor) VALUES"
               " ('municipio_nome', 'Orindiúva')")
    db.commit()
    db.close()
    return licitarium.Api()


def test_cnpj_curto_nem_chega_a_consultar_o_pncp(api, monkeypatch):
    chamou = []
    monkeypatch.setattr(pncp, "consultar_orgao",
                        lambda cnpj: chamou.append(cnpj))
    r = api.add_orgao("123", "Nome")
    assert r == {"ok": False, "erro": "CNPJ deve ter 14 dígitos"}
    assert chamou == []


def test_cnpj_que_o_pncp_nao_conhece_e_recusado(api, monkeypatch):
    monkeypatch.setattr(pncp, "consultar_orgao", lambda cnpj: None)
    r = api.add_orgao("99999999000199", "Nome")
    assert r["ok"] is False
    assert "não encontrado" in r["erro"]


def test_cnpj_da_mesma_prefeitura_entra(api, monkeypatch):
    monkeypatch.setattr(pncp, "consultar_orgao", lambda cnpj:
        {"razaoSocial": "ORINDIUVA CAMARA MUNICIPAL", "esferaId": "M"})
    r = api.add_orgao("51351716000174", "")
    assert r == {"ok": True}
    orgaos = api.listar_orgaos()
    assert any(o["cnpj"] == "51351716000174"
               and o["razao_social"] == "ORINDIUVA CAMARA MUNICIPAL"
               for o in orgaos)


def test_cnpj_de_outra_prefeitura_e_bloqueado(api, monkeypatch):
    """O caso real que motivou a checagem: CNPJ de outro município."""
    monkeypatch.setattr(pncp, "consultar_orgao", lambda cnpj:
        {"razaoSocial": "MUNICIPIO DE OLIMPIA", "esferaId": "M"})
    r = api.add_orgao("45180804000181", "")
    assert r["ok"] is False
    assert "OLIMPIA" in r["erro"] and "não parece ser de Orindiúva" in r["erro"]
    assert api.listar_orgaos() == []


def test_comparacao_ignora_acento_e_caixa(api, monkeypatch):
    """"Orindiúva" (config) vs "ORINDIUVA" (PNCP, sem acento) tem de bater."""
    monkeypatch.setattr(pncp, "consultar_orgao", lambda cnpj:
        {"razaoSocial": "FUNDO MUNICIPAL DE SAUDE DE ORINDIUVA", "esferaId": "M"})
    r = api.add_orgao("11222333000144", "")
    assert r == {"ok": True}


def test_orgao_estadual_ou_federal_e_bloqueado(api, monkeypatch):
    monkeypatch.setattr(pncp, "consultar_orgao", lambda cnpj:
        {"razaoSocial": "GOVERNO DO ESTADO DE SAO PAULO", "esferaId": "E"})
    r = api.add_orgao("12345678000199", "")
    assert r["ok"] is False
    assert "não é órgão municipal" in r["erro"]


def test_falha_de_rede_no_pncp_nao_deixa_passar_sem_checar(api, monkeypatch):
    def _estourar(cnpj):
        raise pncp.PncpErro("o PNCP não respondeu")
    monkeypatch.setattr(pncp, "consultar_orgao", _estourar)
    r = api.add_orgao("11222333000144", "")
    assert r["ok"] is False
    assert "não consegui confirmar" in r["erro"]
    assert api.listar_orgaos() == []


def test_sem_municipio_configurado_pula_a_checagem_de_nome(tmp_path, monkeypatch):
    """Acervo recém-criado, antes do wizard salvar o município: não trava."""
    monkeypatch.setattr(licitarium, "DIR_DADOS", tmp_path)
    monkeypatch.setattr(licitarium, "ARQUIVO_DB", tmp_path / "novo.db")
    licitarium.abrir_db().close()
    monkeypatch.setattr(pncp, "consultar_orgao", lambda cnpj:
        {"razaoSocial": "QUALQUER COISA", "esferaId": "M"})
    r = licitarium.Api().add_orgao("11222333000144", "")
    assert r == {"ok": True}
