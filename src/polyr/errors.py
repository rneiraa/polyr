"""Errores con el mismo formato informativo que dplyr/rlang."""
from __future__ import annotations


class ExprError(Exception):
    """Error al compilar o resolver una expresión.

    Lo lanzan las capas internas (tipos, expresiones, tidyselect). Los verbos
    lo capturan y lo convierten en un :class:`DplyrError` con contexto.
    """


class DplyrError(Exception):
    """Error de un verbo, indicando en qué argumento ocurrió.

    Imita el formato de dplyr::

        Error en `filter()`:
        ℹ En el argumento: `z > 1`.
        Causado por error:
        ! No se encontró la columna `z`.
    """

    def __init__(self, verb: str, message: str, argument: str | None = None):
        self.verb = verb
        self.argument = argument
        self.message = message
        lines = [f"Error en `{verb}()`:"]
        if argument is not None:
            lines += [f"ℹ En el argumento: `{argument}`.", "Causado por error:"]
        lines.append(f"! {message}")
        super().__init__("\n".join(lines))


class DplyrMessage(UserWarning):
    """Mensaje informativo (el equivalente de ``message()`` en dplyr).

    Se emite con :mod:`warnings`, así que se puede silenciar con::

        import warnings
        from polyr import DplyrMessage
        warnings.simplefilter("ignore", DplyrMessage)
    """


def inform(message: str) -> None:
    import warnings
    warnings.warn(message, DplyrMessage, stacklevel=4)
