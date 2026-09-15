# tests/test_database_url.py
"""Tests for SQL Server URL builder and engine resolution helpers."""

from db.database import build_sqlserver_url, resolve_database_url


def test_build_sqlserver_url_basic():
    url = build_sqlserver_url({
        "server": "sql01",
        "port": 1433,
        "database": "iMat",
        "username": "sa",
        "password": "Secret!",
        "trusted_connection": False,
        "encrypt": True,
        "trust_server_certificate": True,
        "driver": "ODBC Driver 17 for SQL Server",
    })
    assert url.startswith("mssql+pyodbc://")
    assert "sql01:1433" in url
    assert "iMat" in url
    assert "sa:" in url
    assert "Encrypt=yes" in url


def test_build_sqlserver_url_trusted():
    url = build_sqlserver_url({
        "server": "sql01",
        "database": "iMat",
        "trusted_connection": True,
    })
    assert "Trusted_Connection=yes" in url
    assert "@sql01" in url or "sql01" in url


def test_resolve_explicit_url():
    assert resolve_database_url("sqlite:///:memory:") == "sqlite:///:memory:"
