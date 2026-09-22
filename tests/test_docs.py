"""Los ejemplos de la documentación se ejecutan: si la API cambia, fallan."""
import re
import warnings
from pathlib import Path

import pytest

import polyr

ROOT = Path(__file__).resolve().parent.parent
DOCS = [ROOT / "README.md", ROOT / "docs" / "tutorial.md"]


def python_blocks(path: Path) -> list[str]:
    return re.findall(r"```python\n(.*?)```", path.read_text(encoding="utf-8"), re.S)


@pytest.mark.parametrize("path", DOCS, ids=lambda p: p.name)
def test_ejemplos_de_la_documentacion(path):
    blocks = python_blocks(path)
    assert blocks, f"{path.name} no tiene ejemplos"
    namespace: dict = {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", polyr.DplyrMessage)
        for i, block in enumerate(blocks, 1):
            try:
                exec(compile(block, f"{path.name}[bloque {i}]", "exec"), namespace)
            except Exception as err:  # pragma: no cover - el mensaje ayuda a depurar
                raise AssertionError(f"Falló el bloque {i} de {path.name}:\n{block}") from err


def test_version_coincide_con_pyproject():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    version = re.search(r'^version = "(.+)"', text, re.M).group(1)
    assert polyr.__version__ == version


def test_all_exporta_nombres_existentes():
    missing = [name for name in polyr.__all__ if not hasattr(polyr, name)]
    assert not missing


def test_todo_lo_publico_tiene_docstring():
    undocumented = [name for name in polyr.__all__
                    if callable(getattr(polyr, name)) and not getattr(polyr, name).__doc__]
    assert not undocumented, undocumented


def test_referencia_al_dia():
    import importlib.util
    spec = importlib.util.spec_from_file_location("gen_reference", ROOT / "scripts" / "gen_reference.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    current = (ROOT / "docs" / "referencia.md").read_text(encoding="utf-8")
    assert current == module.render(), "Ejecuta: python scripts/gen_reference.py"
