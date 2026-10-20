import logging

import requests

from ._shared import (
    DomainNotFoundError,
    check_response as _check_response,
    convert_records_to_domains,
    make_request,
    HTTP_TIMEOUT,
)

description = "Scan multiple domains by fetching them from GoDaddy"

API_URL = "https://api.godaddy.com/v1/"


class GDApi:
    def __init__(self, api_key, api_secret):
        self.session = requests.session()
        self.session.headers.update(
            {
                "Content-Type": "application/json",
                "Authorization": "sso-key " + api_key + ":" + api_secret,
            }
        )

    @staticmethod
    def check_response(response: requests.Response):
        return _check_response(
            response,
            "API key valid but access denied. GoDaddy now block API access unless you have at least 10 domains",
        )

    def make_request(self, endpoint):
        return make_request(self.session, API_URL + endpoint)

    def list_domains(self):
        req = self.make_request("domains")

        return self.check_response(self.session.send(req, timeout=HTTP_TIMEOUT))

    def get_records(self, domain):
        req = self.make_request(f"domains/{domain}/records")
        res = self.session.send(req, timeout=HTTP_TIMEOUT)

        if 404 == res.status_code:
            raise DomainNotFoundError(domain)

        return self.check_response(res)


def fetch_domains(gd_api_key: str, gd_api_secret: str, gd_domains: str = None, **args):
    root_domains = []
    domains = []
    api = GDApi(gd_api_key, gd_api_secret)

    if gd_domains is not None and len(gd_domains):
        root_domains = [domain.strip(" ") for domain in gd_domains.split(",")]
    else:
        resp_data = api.list_domains().json()
        root_domains = [domain["domain"] for domain in resp_data]

    for domain in root_domains:
        if "" == domain or domain is None:
            continue

        try:
            records = api.get_records(domain).json()
        except DomainNotFoundError:
            logging.warning(f"Domain not found, skipping: {domain}")
            continue

        domains.extend(
            convert_records_to_domains(records, domain, replace_at_in_cname=True)
        )

    return domains
