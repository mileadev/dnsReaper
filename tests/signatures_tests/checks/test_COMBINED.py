from domain import Domain
from signatures.checks import COMBINED
import pytest


## macthing_ip_or_cname
@pytest.mark.asyncio
async def test_matching_ip_or_cname_single_ipv4_match():
    domain = Domain("mock.local", fetch_standard_records=False)
    domain.A = ["1.1.1.1"]
    domain.CNAME = []
    assert COMBINED.matching_ip_or_cname(domain, "", ips="1.1.1.1") == True


@pytest.mark.asyncio
async def test_matching_ip_or_cname_multiple_ipv4_match():
    domain = Domain("mock.local", fetch_standard_records=False)
    domain.A = ["2.2.2.2"]
    domain.CNAME = []
    assert COMBINED.matching_ip_or_cname(domain, "", ips=["1.1.1.1", "2.2.2.2"]) == True


@pytest.mark.asyncio
async def test_matching_ip_or_cname_single_ipv6_match():
    domain = Domain("mock.local", fetch_standard_records=False)
    domain.AAAA = ["::1"]
    domain.CNAME = []
    assert COMBINED.matching_ip_or_cname(domain, "", ips="::1") == True


@pytest.mark.asyncio
async def test_matching_ip_or_cname_multiple_ipv6_match():
    domain = Domain("mock.local", fetch_standard_records=False)
    domain.AAAA = ["::2"]
    domain.CNAME = []
    assert COMBINED.matching_ip_or_cname(domain, "", ips=["::1", "::2"]) == True


@pytest.mark.asyncio
async def test_matching_ip_or_cname_multiple_ips_match_ipv6():
    domain = Domain("mock.local", fetch_standard_records=False)
    domain.AAAA = ["::2"]
    domain.CNAME = []
    assert COMBINED.matching_ip_or_cname(domain, "", ips=["1.1.1.1", "::2"]) == True


@pytest.mark.asyncio
async def test_matching_ip_or_cname_multiple_ips_match_ipv4():
    domain = Domain("mock.local", fetch_standard_records=False)
    domain.A = ["1.1.1.1"]
    domain.CNAME = []
    assert COMBINED.matching_ip_or_cname(domain, "", ips=["1.1.1.1", "::2"]) == True


@pytest.mark.asyncio
async def test_matching_ip_or_cname_cname_match():
    domain = Domain("mock.local", fetch_standard_records=False)
    domain.A = []
    domain.CNAME = ["goose"]
    assert (
        COMBINED.matching_ip_or_cname(domain, "goose", ips=["1.1.1.1", "::1"]) == True
    )


@pytest.mark.asyncio
async def test_matching_ip_or_cname_no_match():
    domain = Domain("mock.local", fetch_standard_records=False)
    domain.A = []
    domain.AAAA = []
    domain.CNAME = []
    assert (
        COMBINED.matching_ip_or_cname(domain, "goose", ips=["1.1.1.1", "::1"]) == False
    )
