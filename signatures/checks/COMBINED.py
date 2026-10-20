from . import A, AAAA, CNAME
from domain import Domain


def matching_ip_or_cname(domain: Domain, strings, ips) -> bool:
    if A.match(domain, ips):
        return True
    if AAAA.match(domain, ips):
        return True
    if CNAME.match(domain, strings):
        return True
    return False
