from domain import Domain
from signatures.checks import NS
from unittest.mock import patch
import resolver
import pytest


@pytest.mark.asyncio
async def test_match_for_single_string():
    domain = Domain("mock.local", fetch_standard_records=False)
    domain.NS = ["abc", "def"]
    assert NS.match(domain, "abc") == True


@pytest.mark.asyncio
async def test_match_for_single_substring():
    domain = Domain("mock.local", fetch_standard_records=False)
    domain.NS = ["abc", "def"]
    assert NS.match(domain, "b") == True


@pytest.mark.asyncio
async def test_match_where_ns_is_subtring_of_string():
    domain = Domain("mock.local", fetch_standard_records=False)
    domain.NS = ["abc", "def"]
    assert NS.match(domain, "abcd") == False


@pytest.mark.asyncio
async def test_match_for_multiple_string():
    domain = Domain("mock.local", fetch_standard_records=False)
    domain.NS = ["abc", "def"]
    assert NS.match(domain, ["abc", "def"]) == True


@pytest.mark.asyncio
async def test_match_for_one_of_multiple_string():
    domain = Domain("mock.local", fetch_standard_records=False)
    domain.NS = ["abc", "hij"]
    assert NS.match(domain, ["abc", "def"]) == True


@pytest.mark.asyncio
async def test_match_for_one_of_multiple_substring():
    domain = Domain("mock.local", fetch_standard_records=False)
    domain.NS = ["abc", "hij"]
    assert NS.match(domain, ["def", "h"]) == True


@pytest.mark.asyncio
async def test_match_for_none_of_multiple_string():
    domain = Domain("mock.local", fetch_standard_records=False)
    domain.NS = ["abc", "def"]
    assert NS.match(domain, ["hij", "klm"]) == False


@pytest.mark.asyncio
async def test_match_for_none_matching_string():
    domain = Domain("mock.local", fetch_standard_records=False)
    domain.NS = ["abc", "def"]
    assert NS.match(domain, "hij") == False


@pytest.mark.asyncio
async def test_match_with_no_ns_records():
    domain = Domain("mock.local", fetch_standard_records=False)
    domain.NS = []
    assert NS.match(domain, "abc") == False


@pytest.mark.asyncio
async def test_match_multiple_with_no_ns_records():
    domain = Domain("mock.local", fetch_standard_records=False)
    domain.NS = []
    assert NS.match(domain, ["abc", "def"]) == False


@pytest.mark.asyncio
async def test_no_SOA_detected_on_NS_with_matching_nameservers():
    domain = Domain("mock.local", fetch_standard_records=False)
    domain.NS = ["ns"]
    with patch("resolver.Resolver.resolve_with_ns", return_value={"SOA": []}):
        with patch("domain.Domain.query", return_value=["10.10.10.10"]):
            assert (await NS.no_SOA_detected(domain)) == True


@pytest.mark.asyncio
async def test_no_SOA_detected_on_NS_with_no_matching_nameservers():
    domain = Domain("mock.local", fetch_standard_records=False)
    domain.NS = ["ns"]

    with patch(
        "resolver.Resolver.resolve_with_ns", return_value={"SOA": ["SOA RECORD HERE"]}
    ):
        with patch("domain.Domain.query", return_value=["10.10.10.10"]):
            assert (await NS.no_SOA_detected(domain)) == False


@pytest.mark.asyncio
async def test_no_SOA_detected_on_NS_with_no_nameservers():
    domain = Domain("mock.local", fetch_standard_records=False)
    domain.NS = []
    assert (await NS.no_SOA_detected(domain)) == False


@pytest.mark.asyncio
async def test_no_SOA_detected_returns_false_when_a_later_ns_has_the_zone():
    domain = Domain("mock.local", fetch_standard_records=False)
    domain.NS = ["ns1", "ns2"]
    with patch("domain.Domain.query", return_value=["10.10.10.10"]):
        with patch(
            "resolver.Resolver.resolve_with_ns",
            side_effect=[{"SOA": []}, {"SOA": ["SOA RECORD HERE"]}],
        ):
            assert (await NS.no_SOA_detected(domain)) == False


@pytest.mark.asyncio
async def test_no_SOA_detected_returns_false_on_a_transport_error():
    domain = Domain("mock.local", fetch_standard_records=False)
    domain.NS = ["ns1", "ns2"]
    with patch("domain.Domain.query", return_value=["10.10.10.10"]):
        with patch(
            "resolver.Resolver.resolve_with_ns",
            side_effect=[{"SOA": []}, TimeoutError()],
        ):
            assert (await NS.no_SOA_detected(domain)) == False


@pytest.mark.asyncio
async def test_no_SOA_detected_returns_true_when_every_ns_has_no_soa():
    domain = Domain("mock.local", fetch_standard_records=False)
    domain.NS = ["ns1", "ns2"]
    with patch("domain.Domain.query", return_value=["10.10.10.10"]):
        with patch(
            "resolver.Resolver.resolve_with_ns",
            side_effect=[{"SOA": []}, {"SOA": []}],
        ) as resolve:
            assert (await NS.no_SOA_detected(domain)) == True
            assert resolve.await_count == 2


@pytest.mark.asyncio
async def test_no_SOA_detected_returns_false_when_the_ns_has_no_a_record():
    domain = Domain("mock.local", fetch_standard_records=False)
    domain.NS = ["ns1"]
    with patch("domain.Domain.query", return_value=[]):
        with patch(
            "resolver.Resolver.resolve_with_ns", return_value={"SOA": []}
        ) as resolve:
            assert (await NS.no_SOA_detected(domain)) == False
            assert resolve.await_count == 0


@pytest.mark.asyncio
async def test_no_SOA_detected_treats_nxdomain_as_no_soa():
    domain = Domain("mock.local", fetch_standard_records=False)
    domain.NS = ["ns1", "ns2"]
    with patch("domain.Domain.query", return_value=["10.10.10.10"]):
        with patch(
            "resolver.Resolver.resolve_with_ns",
            side_effect=[resolver.NXDomainException(), {"SOA": []}],
        ):
            assert (await NS.no_SOA_detected(domain)) == True
