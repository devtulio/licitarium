"""Auxiliares compartilhados pelos testes."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import relatorios


@pytest.fixture
def selecionar_tudo():
    """Marca como selecionados todos os itens que um termo encontra.

    Desde a auditoria de 2026-08-09, gerar o documento de pesquisa de preços
    sem seleção nenhuma é erro — antes saía um relatório sobre a busca
    inteira, com mediana de uma série que ninguém curou. Os testes que
    exercitam o CONTEÚDO do documento (correção pelo IPCA, preço por
    conteúdo, seção de descartes, gráfico de dispersão) precisam então
    passar pela seleção primeiro, como o usuário passa na tela.
    """
    def marcar(db, termo):
        chave = relatorios.chave_termo(termo)
        ids = [r[0] for r in db.execute(
            "SELECT id FROM itens WHERE valor_unitario_homologado IS NOT NULL")]
        db.executemany(
            "INSERT OR IGNORE INTO precos_selecionados (termo, item_id,"
            " criado_em) VALUES (?,?,'2026-01-01')",
            [(chave, i) for i in ids])
        db.commit()
        return ids
    return marcar
