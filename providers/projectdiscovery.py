import requests, logging

from domain import Domain
from ._shared import (
    DomainNotFoundError,
    HTTP_TIMEOUT,
    check_response as _check_response,
)

description = "Scan multiple domains by fetching them from ProjectDiscovery"


class PDApi:
    def __init__(self, api_key):
        self.session = requests.session()
        self.session.headers.update(
            {"Content-Type": "application/json", "Authorization": api_key}
        )

    @staticmethod
    def check_response(response: requests.Response):
        return _check_response(response)

    def make_request(self, endpoint):
        return self.session.prepare_request(
            requests.Request("GET", "https://dns.projectdiscovery.io/dns/" + endpoint)
        )

    def list_domains(self):
        req = self.make_request("domains")

        return self.check_response(self.session.send(req, timeout=HTTP_TIMEOUT))

    def get_subdomains(self, domain):
        domain = domain.lower()
        req = self.make_request(f"{domain}/subdomains")
        res = self.session.send(req, timeout=HTTP_TIMEOUT)

        if 404 == res.status_code:
            raise DomainNotFoundError(domain)

        return self.check_response(res)


def fetch_domains(pd_api_key: str, pd_domains: str, **args):
    root_domains = []
    domains = []
    api = PDApi(pd_api_key)

    root_domains = [domain.strip(" ") for domain in pd_domains.split(",")]

    for domain in root_domains:
        if "" == domain or domain is None:
            continue

        try:
            raw_domains = api.get_subdomains(domain).json()
        except DomainNotFoundError:
            logging.warning(f"Domain not found, skipping: {domain}")
            continue

        logging.warning(f"Testing {len(raw_domains['subdomains'])} subdomains")
        domains.extend(
            [
                Domain(f"{sb}.{domain}")
                for sb in raw_domains["subdomains"]
                if "*" not in sb
            ]
        )

    return domains
