import ipaddress
from collections import namedtuple
from typing import Optional

import logging
import collections

collections.Iterable = collections.abc.Iterable
collections.Mapping = collections.abc.Mapping

import asyncwhois
import aiohttp
import ssl

from resolver import Resolver


class _SharedSession:
    """Context manager that does not close the shared ClientSession on exit."""

    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *exc_info):
        return False


class Domain:
    resolver = Resolver()

    @property
    async def NX_DOMAIN(self):
        return (await self.resolver.resolve(self.domain, "A"))["NX_DOMAIN"]

    async def query(self, type):
        try:
            resp = await self.resolver.resolve(self.domain, type)
            return resp[type]
        except Exception:
            return []

    async def fetch_std_records(self):
        # TODO: is this recursive?
        self.CNAME = await self.query("CNAME")
        self.A = await self.query("A")
        self.AAAA = await self.query("AAAA")
        if self.CNAME or self.A or self.AAAA:
            # return early if we get a CNAME otherwise we get records for the cname aswell
            # this is actually desirable for A/AAAA but not NS as the next zone
            # will be queried based on the CNAME value, not the original domain
            return
        self.NS = await self.query("NS")

    async def fetch_external_records(self):
        for cname in self.CNAME:
            split_cname = cname.split(".", 1)
            if len(split_cname) == 1:
                continue  # This cname has no zone to assess
            if self.base_domain == split_cname[1]:
                continue  # Same zone, dont fetch
            d = Domain(cname)
            await d.fetch_std_records()
            self.A += d.A
            self.AAAA += d.AAAA
            self.CNAME += d.CNAME
        for ns in self.NS:
            try:
                d = Domain(self.domain)
                await d.set_resolver_nameserver(ns)
                await d.fetch_std_records()
                self.A += d.A
                self.AAAA += d.AAAA
                self.CNAME += d.CNAME
            except Exception:
                logging.debug(
                    f"We could not resolve the provided NS record '{ns}' to an ip"
                )

    async def set_resolver_nameserver(self, ns: Optional[str] = None):
        if ns is None:
            self.resolver = Domain.resolver
            return

        if type(ns) != str:
            logging.error(f"Cannot set custom NS as {ns} not a string")

            raise RuntimeError(f"Invalid NS type - expected str got {type(ns)}")

        try:
            ipaddress.ip_address(ns)
            nameservers = [ns]
        except ValueError:
            # if ns isn't a valid IP address, attempt to resolve it
            try:
                bootstrap = (
                    Domain.resolver
                    if isinstance(Domain.resolver, Resolver)
                    else Resolver()
                )
                nameservers = (await bootstrap.resolve(ns.rstrip("."), "A"))["A"]
            except Exception:
                nameservers = []

        self.resolver = Resolver(nameservers=nameservers, parallelism=1)

    def set_base_domain(self):
        split_domain = self.domain.split(".", 1)
        if len(split_domain) > 1:
            self.base_domain = split_domain[1]
        else:
            self.base_domain = "."

    def __init__(self, domain, fetch_standard_records=True):
        self.domain = domain.rstrip(".")
        self.NS = []
        self.A = []
        self.AAAA = []
        self.CNAME = []
        self.set_base_domain()
        self.should_fetch_std_records = fetch_standard_records

    _session = None

    @classmethod
    def get_session(cls):
        if cls._session is None or cls._session.closed:
            cls._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=5, sock_connect=3)
            )
        return _SharedSession(cls._session)

    @classmethod
    async def close_session(cls):
        if cls._session is not None:
            await cls._session.close()
            cls._session = None

    async def fetch_web(self, uri="", https=True):
        protocol = "https" if https else "http"
        url = f"{protocol}://{self.domain}/{uri}"

        # We must disable SSL validation because vulnerable domains probably won't have a valid cert on the other end
        # e.g. github
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        }
        try:
            async with self.get_session() as session:
                async with session.get(url, ssl=ssl_context, headers=headers) as resp:
                    web_status = resp.status
                    body_parts = []
                    remaining = 1024 * 1024
                    while remaining:
                        chunk = await resp.content.read(remaining)
                        if not chunk:
                            break
                        body_parts.append(chunk)
                        remaining -= len(chunk)
                    body = b"".join(body_parts)
                    try:
                        web_body = body.decode(
                            resp.charset or "utf-8", errors="replace"
                        )
                    except LookupError:
                        web_body = body.decode("utf-8", errors="replace")
        except Exception as exc:
            logging.debug(f"Web request to '{url}' failed: {exc}")
            web_status = 0
            web_body = ""
        return namedtuple("web_response", ["status_code", "body"])(web_status, web_body)

    @property
    async def is_registered(self):
        try:
            await asyncwhois.aio_whois(self.domain)
            return True
        except asyncwhois.NotFoundError:
            return False
        except Exception:
            return True

    def __repr__(self):
        return self.domain
