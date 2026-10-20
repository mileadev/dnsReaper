import asyncio
from unittest.mock import AsyncMock, patch

import dns.exception
import dns.flags
import dns.message
import dns.rcode
import dns.rrset
import pytest

import resolver
from resolver import (
    DNSException,
    NXDomainException,
    NoAnswerException,
    Resolver,
)

DEFAULT_RECORDS = {
    "A": [],
    "NS": [],
    "CNAME": [],
    "SOA": [],
    "AAAA": [],
    "MX": [],
    "NX_DOMAIN": False,
}


def make_response(qname="example.com", qtype="A", rcode=dns.rcode.NOERROR):
    query = dns.message.make_query(qname, qtype)
    response = dns.message.make_response(query)
    response.set_rcode(rcode)
    return response


@pytest.mark.asyncio
async def test_resolve_dns_collects_all_answer_rrsets():
    query = dns.message.make_query("www.example.com", "A")
    response = dns.message.make_response(query)
    response.answer.append(
        dns.rrset.from_text(
            "www.example.com.", 300, "IN", "CNAME", "target.example.com."
        )
    )
    response.answer.append(
        dns.rrset.from_text("target.example.com.", 300, "IN", "A", "192.0.2.1")
    )

    with patch("dns.asyncquery.udp", new=AsyncMock(return_value=response)):
        records = await resolver.resolve_dns("www.example.com", resolver.TYPE_A)

    assert records["CNAME"] == ["target.example.com"]
    assert records["A"] == ["192.0.2.1"]


@pytest.mark.asyncio
async def test_resolve_dns_nxdomain():
    response = make_response(rcode=dns.rcode.NXDOMAIN)
    with patch("dns.asyncquery.udp", new=AsyncMock(return_value=response)):
        with pytest.raises(NXDomainException):
            await resolver.resolve_dns("example.com", resolver.TYPE_A)


@pytest.mark.asyncio
async def test_resolve_dns_no_answer():
    response = make_response()
    with patch("dns.asyncquery.udp", new=AsyncMock(return_value=response)):
        with pytest.raises(NoAnswerException):
            await resolver.resolve_dns("example.com", resolver.TYPE_A)


@pytest.mark.asyncio
async def test_resolve_dns_servfail():
    response = make_response(rcode=dns.rcode.SERVFAIL)
    with patch("dns.asyncquery.udp", new=AsyncMock(return_value=response)):
        with pytest.raises(DNSException) as exc_info:
            await resolver.resolve_dns("example.com", resolver.TYPE_A)
    assert not isinstance(exc_info.value, (NXDomainException, NoAnswerException))


@pytest.mark.asyncio
async def test_resolve_dns_retries_truncated_udp_over_tcp():
    truncated = make_response()
    truncated.flags |= dns.flags.TC
    full = make_response()
    full.answer.append(dns.rrset.from_text("example.com.", 300, "IN", "A", "192.0.2.7"))
    udp = AsyncMock(return_value=truncated)
    tcp = AsyncMock(return_value=full)
    with patch("dns.asyncquery.udp", new=udp), patch("dns.asyncquery.tcp", new=tcp):
        records = await resolver.resolve_dns("example.com", resolver.TYPE_A)

    assert records["A"] == ["192.0.2.7"]
    tcp.assert_awaited_once()


@pytest.mark.asyncio
async def test_resolve_with_ns_propagates_timeout():
    with patch(
        "resolver.resolve_dns", new=AsyncMock(side_effect=dns.exception.Timeout)
    ):
        with pytest.raises(dns.exception.Timeout):
            await Resolver.resolve_with_ns("example.com", "8.8.8.8", "SOA")


@pytest.mark.asyncio
async def test_resolve_retries_without_deadlock():
    r = Resolver(parallelism=1)
    with patch("resolver.resolve_dns", new=AsyncMock(side_effect=TimeoutError)):
        records = await asyncio.wait_for(r.resolve("example.com", "A"), timeout=2)

    assert records == DEFAULT_RECORDS


def test_resolver_rejects_zero_parallelism():
    with pytest.raises(ValueError):
        Resolver(parallelism=0)
