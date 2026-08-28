import time


class Deadline:
    """Orcamento de tempo por execucao. GitHub Actions mata o job apos 6h;
    paramos de pedir mais paginas/itens antes disso e retomamos na proxima
    execucao a partir do checkpoint salvo, em vez de sermos mortos no meio
    de uma escrita."""

    def __init__(self, max_seconds: int):
        self._start = time.monotonic()
        self._max_seconds = max_seconds

    def expired(self) -> bool:
        return (time.monotonic() - self._start) >= self._max_seconds
