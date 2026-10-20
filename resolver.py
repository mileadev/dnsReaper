import asyncio
import logging
import os
import random
import time

import dns.asyncquery
import dns.flags
import dns.message
import dns.rcode
import dns.rdatatype

# DNS query types
TYPE_A = 1
TYPE_NS = 2
TYPE_CNAME = 5
TYPE_SOA = 6
TYPE_AAAA = 28
TYPE_MX = 15

QUERY_TYPES = {
    "A": TYPE_A,
    "NS": TYPE_NS,
    "CNAME": TYPE_CNAME,
    "SOA": TYPE_SOA,
    "AAAA": TYPE_AAAA,
    "MX": TYPE_MX,
}

QUERY_TIMEOUT = 2.0


class DNSException(Exception):
    pass


class NXDomainException(DNSException):
    pass


class NoAnswerException(DNSException):
    pass


def _default_records():
    return {
        "A": [],
        "NS": [],
        "CNAME": [],
        "SOA": [],
        "AAAA": [],
        "MX": [],
        "NX_DOMAIN": False,
    }


async def resolve_dns(domain, qtype, server="8.8.8.8", port=53):
    query = dns.message.make_query(domain, qtype)
    response = await dns.asyncquery.udp(query, server, timeout=QUERY_TIMEOUT, port=port)
    if response.flags & dns.flags.TC:
        response = await dns.asyncquery.tcp(
            query, server, timeout=QUERY_TIMEOUT, port=port
        )

    rcode = response.rcode()
    if rcode == dns.rcode.NXDOMAIN:
        raise NXDomainException("The domain does not exist (NXDOMAIN)")
    if rcode != dns.rcode.NOERROR:
        raise DNSException(f"DNS server returned {dns.rcode.to_text(rcode)}")

    if not response.answer:
        raise NoAnswerException("No answer found in the DNS response")

    records = _default_records()
    for rrset in response.answer:
        if rrset.rdtype == dns.rdatatype.A:
            records["A"].extend(rdata.address for rdata in rrset)
        elif rrset.rdtype == dns.rdatatype.AAAA:
            records["AAAA"].extend(rdata.address for rdata in rrset)
        elif rrset.rdtype == dns.rdatatype.CNAME:
            records["CNAME"].extend(
                rdata.target.to_text(omit_final_dot=True) for rdata in rrset
            )
        elif rrset.rdtype == dns.rdatatype.NS:
            records["NS"].extend(
                rdata.target.to_text(omit_final_dot=True) for rdata in rrset
            )
        elif rrset.rdtype == dns.rdatatype.SOA:
            for rdata in rrset:
                records["SOA"].append(
                    {
                        "mname": rdata.mname.to_text(omit_final_dot=True),
                        "rname": rdata.rname.to_text(omit_final_dot=True),
                        "serial": rdata.serial,
                        "refresh": rdata.refresh,
                        "retry": rdata.retry,
                        "expire": rdata.expire,
                        "minimum": rdata.minimum,
                    }
                )
        elif rrset.rdtype == dns.rdatatype.MX:
            records["MX"].extend(
                (rdata.preference, rdata.exchange.to_text(omit_final_dot=True))
                for rdata in rrset
            )
    return records


class Resolver:
    attempted_resolutions = 0
    resolutions = 0
    errors = 0
    no_records = 0
    nx_domains = 0

    def __init__(self, parallelism=200, nameservers=None):
        if parallelism < 1:
            raise ValueError("parallelism must be at least 1")
        self.nameservers = nameservers if nameservers is not None else ["8.8.8.8"]
        self.semaphore = asyncio.Semaphore(parallelism)

    async def resolve(self, fqdn, type=None, retry=3):
        qtype = QUERY_TYPES[type if type is not None else "A"]
        async with self.semaphore:
            if self.attempted_resolutions == 0:
                write_when_on_warn("\nDNS Resolving: (Feedback per 100 resolves)\n")
                write_when_on_warn(
                    "[ . = success, + = non-existent domain, x = error (likely rate-limiting)]\n"
                )
            self.attempted_resolutions += 1
            start = time.time()
            resp = _default_records()

            for attempt in range(retry + 1):
                try:
                    resp = await resolve_dns(
                        fqdn, qtype, random.choice(self.nameservers)
                    )
                    if self.resolutions % 100 == 99:
                        write_when_on_warn(".")
                    self.resolutions += 1
                    break
                except NoAnswerException:
                    if self.resolutions % 100 == 99:
                        write_when_on_warn(".")
                    self.resolutions += 1
                    break
                except NXDomainException:
                    if self.nx_domains % 100 == 99:
                        write_when_on_warn("+")
                    self.nx_domains += 1
                    resp["NX_DOMAIN"] = True
                    break
                except Exception:
                    if self.errors % 100 == 99:
                        write_when_on_warn("x")
                    self.errors += 1
                    if attempt < retry:
                        await asyncio.sleep(0.1)

            time_delta = time.time() - start
            if time_delta < 0.125:
                await asyncio.sleep(0.125 - time_delta)
            return resp

    @staticmethod
    async def resolve_with_ns(fqdn, ns, type=None):
        return await resolve_dns(
            fqdn, QUERY_TYPES[type if type is not None else "A"], ns
        )


def write_when_on_warn(msg):
    if logging.root.level == logging.WARN:
        # Only in warning, as we need a clean output
        os.write(2, msg.encode())
