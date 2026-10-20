from domain import Domain
from signatures import _generic_cname_found_but_unregistered
from unittest.mock import patch, AsyncMock
from .. import mocks
import pytest


@pytest.mark.asyncio
async def test_potential_success_with_a_cname_of_two_parts():
    domain = Domain("mock.local", fetch_standard_records=False)
    domain.CNAME = ["cname.tld"]
    assert _generic_cname_found_but_unregistered.test.potential(domain) == True


@pytest.mark.asyncio
async def test_potential_failure():
    domain = Domain("mock.local", fetch_standard_records=False)
    assert _generic_cname_found_but_unregistered.test.potential(domain) == False


@pytest.mark.asyncio
async def test_potential_failure_with_three_part_domain():
    domain = Domain("foo.mock.local", fetch_standard_records=False)
    domain.CNAME = ["subdomain.cname.tld"]
    assert _generic_cname_found_but_unregistered.test.potential(domain) == False


@pytest.mark.asyncio
async def test_check_success():
    domain = Domain("mock.local", fetch_standard_records=False)
    domain.CNAME = ["cname.tld"]
    registered = AsyncMock(return_value=False)
    with patch("domain.Domain.is_registered", new=property(lambda self: registered())):
        assert await _generic_cname_found_but_unregistered.test.check(domain) == True
        assert registered.await_count == 1


@pytest.mark.asyncio
async def test_check_failure():
    domain = Domain("mock.local", fetch_standard_records=False)
    domain.CNAME = ["cname.tld"]
    registered = AsyncMock(return_value=True)
    with patch("domain.Domain.is_registered", new=property(lambda self: registered())):
        assert await _generic_cname_found_but_unregistered.test.check(domain) == False
        assert registered.await_count == 1


@pytest.mark.asyncio
async def test_check_success_ACTIVE():
    test_cname = f"{mocks.random_string()}.co.uk"
    domain = Domain(f"{mocks.random_string()}.com", fetch_standard_records=False)
    domain.CNAME = [test_cname]
    print(f"Testing cname {test_cname}")
    assert await _generic_cname_found_but_unregistered.test.check(domain) == True


@pytest.mark.asyncio
async def test_potential_success_with_a_co_uk_cname():
    domain = Domain("mock.local", fetch_standard_records=False)
    domain.CNAME = ["foo.co.uk"]
    assert _generic_cname_found_but_unregistered.test.potential(domain) == True


@pytest.mark.asyncio
async def test_potential_failure_with_a_subdomain_of_a_co_uk_cname():
    domain = Domain("mock.local", fetch_standard_records=False)
    domain.CNAME = ["sub.foo.co.uk"]
    assert _generic_cname_found_but_unregistered.test.potential(domain) == False
