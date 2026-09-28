import socket
import pytest

@pytest.fixture(autouse=True)
def offline(monkeypatch):
    """Tests never load .env and fail immediately on accidental live networking."""
    def denied(*a,**k):raise AssertionError('Network forbidden in offline tests')
    monkeypatch.setattr(socket.socket,'connect',denied)
    monkeypatch.setattr(socket,'create_connection',denied)
