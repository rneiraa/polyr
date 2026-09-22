"""Revisa que el repositorio no exponga secretos ni datos personales.

Uso:
    python scripts/revisar_secretos.py           # archivos versionados
    python scripts/revisar_secretos.py --historial   # además, autores y mensajes

Se ejecuta en la CI y en el hook `pre-push` de `.githooks/`. Devuelve 1 y
nombra el archivo y la línea si encuentra algo.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

# Correos que sí pueden aparecer. Cualquier otro se trata como dato personal.
CORREOS_PERMITIDOS = {
    "polyr@users.noreply.github.com",
    "noreply@anthropic.com",
}

PATRONES = [
    ("token de GitHub", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}")),
    ("token de GitHub (fino)", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}")),
    ("clave de AWS", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("clave de OpenAI o similar", re.compile(r"\bsk-[A-Za-z0-9]{20,}")),
    ("clave privada", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----")),
    ("credencial asignada", re.compile(
        r"(?i)\b(api[_-]?key|secret|passwd|password|token)\b\s*[:=]\s*[\"'][^\"'\s]{8,}[\"']")),
    ("cadena de conexión con credenciales", re.compile(r"[a-z+]+://[^/\s:@]+:[^/\s@]+@")),
]

CORREO = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
BINARIOS = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".whl", ".ico"}
SIN_REVISAR = {"scripts/revisar_secretos.py"}   # contiene los patrones mismos


def versionados() -> list[str]:
    salida = subprocess.run(["git", "ls-files"], cwd=RAIZ, capture_output=True, text=True)
    return [linea for linea in salida.stdout.splitlines() if linea]


def revisar_texto(origen: str, texto: str) -> list[str]:
    hallazgos = []
    for numero, linea in enumerate(texto.splitlines(), 1):
        for nombre, patron in PATRONES:
            if patron.search(linea):
                hallazgos.append(f"{origen}:{numero}: posible {nombre}")
        for correo in CORREO.findall(linea):
            if correo.lower() not in CORREOS_PERMITIDOS:
                hallazgos.append(f"{origen}:{numero}: correo no permitido `{correo}`")
    return hallazgos


def revisar_archivos() -> list[str]:
    hallazgos = []
    for ruta in versionados():
        if ruta in SIN_REVISAR or Path(ruta).suffix.lower() in BINARIOS:
            continue
        try:
            texto = (RAIZ / ruta).read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError):
            continue
        hallazgos += revisar_texto(ruta, texto)
    return hallazgos


def revisar_historial() -> list[str]:
    salida = subprocess.run(
        ["git", "log", "--all", "--format=%H%n%an <%ae>%n%cn <%ce>%n%B%n---FIN---"],
        cwd=RAIZ, capture_output=True, text=True)
    return revisar_texto("historial", salida.stdout)


def main() -> int:
    hallazgos = revisar_archivos()
    if "--historial" in sys.argv:
        hallazgos += revisar_historial()
    if hallazgos:
        print("Revisión de seguridad: se encontró contenido que no debería publicarse.\n")
        for h in hallazgos:
            print(f"  ✖ {h}")
        print("\nCorrige o, si es un falso positivo, ajusta scripts/revisar_secretos.py.")
        return 1
    print("Revisión de seguridad: sin hallazgos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
