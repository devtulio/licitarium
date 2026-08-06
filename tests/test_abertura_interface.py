"""Quando a interface não sobe, o programa precisa dizer isso.

A interface é publicada num servidor local (127.0.0.1) pelo pywebview e lida
pela janela do WebView2. Se essa conversa interna é bloqueada — antivírus,
firewall, proxy sem exceção para endereço local —, o usuário via apenas a
página de erro do navegador, que fala de proxy e não menciona o Licitarium.
E o executável é compilado sem console: a falha não deixava rastro nenhum.
"""
import socket
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import licitarium


@pytest.fixture(autouse=True)
def dados(tmp_path, monkeypatch):
    monkeypatch.setattr(licitarium, "DIR_DADOS", tmp_path)
    return tmp_path


def _servidor():
    """Sobe um servidor que aceita conexão e devolve uma resposta HTTP."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    s.listen(1)

    def atender():
        try:
            conexao, _ = s.accept()
            conexao.recv(1024)
            conexao.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\noi")
            conexao.close()
        except OSError:
            pass

    threading.Thread(target=atender, daemon=True).start()
    return s, s.getsockname()[1]


def test_interface_no_ar_quando_o_servidor_responde():
    s, porta = _servidor()
    try:
        assert licitarium._interface_no_ar(f"http://127.0.0.1:{porta}/") is True
    finally:
        s.close()


def test_interface_fora_do_ar_quando_ninguem_atende():
    # porta fechada: é o cenário do ERR_CONNECTION_REFUSED
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    porta = s.getsockname()[1]
    s.close()
    assert licitarium._interface_no_ar(f"http://127.0.0.1:{porta}/",
                                       tentativas=2) is False


def test_arquivo_local_nao_precisa_de_servidor():
    """Sem servidor no meio não há o que esperar."""
    assert licitarium._interface_no_ar("C:/app/ui/index.html") is True
    assert licitarium._interface_no_ar("") is True


def test_falha_fica_registrada_em_arquivo(dados):
    try:
        raise ValueError("porta recusada")
    except ValueError as e:
        licitarium.registrar_falha("interface não respondeu", e)

    log = dados / licitarium.ARQUIVO_LOG
    texto = log.read_text(encoding="utf-8")
    assert "interface não respondeu" in texto
    assert "porta recusada" in texto
    assert licitarium.VERSAO in texto
    assert "Traceback" in texto          # o rastro completo, para diagnóstico


def test_conferir_interface_avisa_o_usuario(dados, monkeypatch):
    avisos = []
    monkeypatch.setattr(licitarium, "_avisar",
                        lambda texto, titulo="Licitarium": avisos.append(texto))
    monkeypatch.setattr(licitarium, "_interface_no_ar", lambda url, **k: False)

    class JanelaFalsa:
        original_url = "http://127.0.0.1:54321/index.html"

    licitarium._conferir_interface(JanelaFalsa())

    assert len(avisos) == 1
    texto = avisos[0]
    # a mensagem tem de nomear o programa, a causa e o que fazer
    assert "Licitarium" in texto and "127.0.0.1" in texto
    assert "antivírus" in texto and "proxy" in texto
    assert str(dados / licitarium.ARQUIVO_LOG) in texto
    assert (dados / licitarium.ARQUIVO_LOG).exists()


def test_interface_no_ar_nao_avisa_ninguem(dados, monkeypatch):
    avisos = []
    monkeypatch.setattr(licitarium, "_avisar",
                        lambda *a, **k: avisos.append(a))
    monkeypatch.setattr(licitarium, "_interface_no_ar", lambda url, **k: True)

    class JanelaFalsa:
        original_url = "http://127.0.0.1:54321/index.html"

    licitarium._conferir_interface(JanelaFalsa())
    assert not avisos
    assert not (dados / licitarium.ARQUIVO_LOG).exists()
