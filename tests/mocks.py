from collections import namedtuple
import socket
from domain import Domain
import dns.resolver
from uuid import uuid4

import aiohttp


def random_string():
    return f"a{uuid4().hex[:8]}"


def mock_web_response_with_static_value(
    domain: Domain, body: str = "", status_code: int = 0
) -> Domain:
    async def mock_fetch_web(**kwargs):
        return namedtuple("web_response", ["body", "status_code"])(body, status_code)

    domain.fetch_web = mock_fetch_web


class CustomResolver:
    def __init__(self, ip):
        self.ip = ip

    async def resolve(self, host, port=0, family=socket.AF_INET):
        return [
            {
                "hostname": host,
                "host": self.ip,
                "port": port,
                "family": family,
                "proto": socket.IPPROTO_TCP,
                "flags": 0,
            }
        ]


def generate_mock_aiohttp_session_with_forced_ip_resolution(ip):
    def mock_aiohttp_session_with_forced_resolution():
        resolver = CustomResolver(ip)
        conn = aiohttp.TCPConnector(resolver=resolver)
        return aiohttp.ClientSession(connector=conn)

    return mock_aiohttp_session_with_forced_resolution


def generate_mock_aiohttp_session_with_forced_cname_resolution(cname):
    ip = [record.to_text() for record in dns.resolver.resolve(cname)][0]

    def mock_aiohttp_session_with_forced_resolution():
        resolver = CustomResolver(ip)
        conn = aiohttp.TCPConnector(resolver=resolver)
        return aiohttp.ClientSession(connector=conn)

    return mock_aiohttp_session_with_forced_resolution
