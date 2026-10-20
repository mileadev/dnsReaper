import asyncio

import pytest
from aiohttp import web

from domain import Domain
from resolver import Resolver


def test_base_domain_for_subdomain():
    assert (
        Domain("foo.example.com", fetch_standard_records=False).base_domain
        == "example.com"
    )


def test_base_domain_for_single_label():
    assert Domain("example", fetch_standard_records=False).base_domain == "."


def test_base_domain_ignores_trailing_dot():
    assert (
        Domain("foo.example.com.", fetch_standard_records=False).base_domain
        == "example.com"
    )


@pytest.mark.asyncio
async def test_ns_branch_calls_fetch_std_records(monkeypatch):
    async def fake_set_resolver_nameserver(self, ns=None):
        return None

    async def fake_fetch_std_records(self):
        self.A = ["1.2.3.4"]
        self.CNAME = ["target.example.net"]

    monkeypatch.setattr(Domain, "set_resolver_nameserver", fake_set_resolver_nameserver)
    monkeypatch.setattr(Domain, "fetch_std_records", fake_fetch_std_records)

    domain = Domain("example.com", fetch_standard_records=False)
    domain.NS = ["ns1.example.com"]
    domain.CNAME = []

    await domain.fetch_external_records()

    assert "1.2.3.4" in domain.A
    assert "target.example.net" in domain.CNAME


@pytest.mark.asyncio
async def test_custom_nameserver_query_uses_resolver_dict(monkeypatch):
    async def fake_resolve(self, fqdn, type=None, retry=3):
        return {
            "A": ["1.2.3.4"],
            "NS": [],
            "CNAME": [],
            "SOA": [],
            "AAAA": [],
            "MX": [],
            "NX_DOMAIN": False,
        }

    monkeypatch.setattr(Resolver, "resolve", fake_resolve)

    domain = Domain("example.com", fetch_standard_records=False)
    await domain.set_resolver_nameserver("ns1.example.com")

    assert isinstance(domain.resolver, Resolver)
    assert await domain.query("A") == ["1.2.3.4"]


@pytest.mark.asyncio
async def test_query_does_not_swallow_cancellation(monkeypatch):
    async def cancelled(self, fqdn, type=None, retry=3):
        raise asyncio.CancelledError

    monkeypatch.setattr(Resolver, "resolve", cancelled)
    domain = Domain("example.com", fetch_standard_records=False)

    with pytest.raises(asyncio.CancelledError):
        await domain.query("A")


@pytest.mark.asyncio
async def test_shared_session_timeout_and_close():
    session = None
    try:
        async with Domain.get_session() as session:
            assert session is Domain._session
            assert session.timeout.total == 5
            assert session.timeout.sock_connect == 3
            assert not session.closed
        # Leaving the context manager must not close the shared session.
        assert not session.closed
    finally:
        await Domain.close_session()

    assert Domain._session is None
    assert session.closed


@pytest.mark.asyncio
async def test_fetch_web_caps_body_at_one_mib():
    async def huge(_request):
        return web.Response(body=b"x" * (1024 * 1024 + 1))

    app = web.Application()
    app.router.add_get("/", huge)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]

    try:
        domain = Domain(f"127.0.0.1:{port}", fetch_standard_records=False)
        response = await domain.fetch_web(uri="", https=False)
        assert response.status_code == 200
        assert len(response.body) == 1024 * 1024
    finally:
        await runner.cleanup()
        await Domain.close_session()


@pytest.mark.asyncio
async def test_fetch_web_reads_body_past_first_chunk():
    async def streamed(request):
        response = web.StreamResponse()
        await response.prepare(request)
        await response.write(b"a" * 4096)
        await response.write(b"b" * 4096)
        await response.write_eof()
        return response

    app = web.Application()
    app.router.add_get("/", streamed)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]

    try:
        domain = Domain(f"127.0.0.1:{port}", fetch_standard_records=False)
        response = await domain.fetch_web(uri="", https=False)
        assert response.body == "a" * 4096 + "b" * 4096
    finally:
        await runner.cleanup()
        await Domain.close_session()
