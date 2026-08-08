"""Brasão do município: upload via diálogo nativo (não `<input type="file">`
— é app desktop), guardado como Data URL no `config`, sem tabela nova."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import licitarium


class JanelaFalsa:
    """Responde ao diálogo de arquivo como o usuário responderia."""

    def __init__(self, resposta=None):
        self.resposta = resposta
        self.pedidos = []

    def create_file_dialog(self, tipo, **kwargs):
        self.pedidos.append({"tipo": tipo, **kwargs})
        return self.resposta


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setattr(licitarium, "DIR_DADOS", tmp_path)
    monkeypatch.setattr(licitarium, "ARQUIVO_DB", tmp_path / "t.db")
    licitarium.abrir_db().close()
    api = licitarium.Api()
    api._janela = JanelaFalsa()
    return api


def test_carregar_brasao_com_sucesso(api, tmp_path):
    imagem = tmp_path / "brasao.png"
    imagem.write_bytes(b"\x89PNG conteudo qualquer")
    api._janela.resposta = str(imagem)

    r = api.carregar_brasao()
    assert r == {"ok": True}
    dado = api.brasao()
    assert dado["dataurl"].startswith("data:image/png;base64,")


def test_carregar_brasao_aceita_jpg(api, tmp_path):
    imagem = tmp_path / "brasao.jpg"
    imagem.write_bytes(b"conteudo jpg qualquer")
    api._janela.resposta = str(imagem)

    r = api.carregar_brasao()
    assert r == {"ok": True}
    assert api.brasao()["dataurl"].startswith("data:image/jpeg;base64,")


def test_carregar_brasao_recusa_arquivo_grande_demais(api, tmp_path):
    imagem = tmp_path / "brasao.png"
    imagem.write_bytes(b"0" * (3 * 1024 * 1024 + 1))
    api._janela.resposta = str(imagem)

    r = api.carregar_brasao()
    assert r["ok"] is False
    assert "grande" in r["erro"]
    assert api.brasao()["dataurl"] is None


def test_carregar_brasao_recusa_formato_nao_suportado(api, tmp_path):
    arquivo = tmp_path / "brasao.gif"
    arquivo.write_bytes(b"gif89a")
    api._janela.resposta = str(arquivo)

    r = api.carregar_brasao()
    assert r["ok"] is False
    assert "formato" in r["erro"]
    assert api.brasao()["dataurl"] is None


def test_carregar_brasao_dialogo_cancelado_nao_e_erro(api):
    api._janela.resposta = None
    r = api.carregar_brasao()
    assert r == {"ok": False, "erro": None}


def test_sem_upload_brasao_devolve_none(api):
    assert api.brasao() == {"dataurl": None}


def test_remover_brasao_limpa_a_chave(api, tmp_path):
    imagem = tmp_path / "brasao.png"
    imagem.write_bytes(b"conteudo")
    api._janela.resposta = str(imagem)
    api.carregar_brasao()
    assert api.brasao()["dataurl"] is not None

    r = api.remover_brasao()
    assert r == {"ok": True}
    assert api.brasao() == {"dataurl": None}


def test_carregar_brasao_substitui_o_anterior(api, tmp_path):
    primeira = tmp_path / "a.png"
    primeira.write_bytes(b"primeira imagem")
    api._janela.resposta = str(primeira)
    api.carregar_brasao()
    anterior = api.brasao()["dataurl"]

    segunda = tmp_path / "b.png"
    segunda.write_bytes(b"segunda imagem, bem diferente")
    api._janela.resposta = str(segunda)
    api.carregar_brasao()
    atual = api.brasao()["dataurl"]

    assert atual != anterior
