import logging

import requests

from ._shared import (
    DomainNotFoundError,
    check_response as _check_response,
    convert_records_to_domains,
    make_request,
    HTTP_TIMEOUT,
)

description = "Scan multiple domains by fetching them from Digital Ocean"

API_URL = "https://api.digitalocean.com/v2/"


class DoApi:
    def __init__(self, api_key):
        self.session = requests.session()
        self.session.headers.update(
            {"Content-Type": "application/json", "Authorization": "Bearer " + api_key}
        )

    @staticmethod
    def check_response(response: requests.Response):
        return _check_response(response)

    def _get(self, url):
        if not url.startswith("http"):
            url = API_URL + url
        return self.session.send(make_request(self.session, url), timeout=HTTP_TIMEOUT)

    def list_domains(self):
        url = "domains?per_page=200"
        while url:
            data = self.check_response(self._get(url)).json()
            yield from data["domains"]
            url = data.get("links", {}).get("pages", {}).get("next")

    def get_records(self, domain):
        url = f"domains/{domain}/records?per_page=200"
        records = []
        while url:
            res = self._get(url)
            if 404 == res.status_code:
                raise DomainNotFoundError(domain)

            data = self.check_response(res).json()
            records.extend(data["domain_records"])
            url = data.get("links", {}).get("pages", {}).get("next")
        return records


def validate_args(do_api_key: str):
    if not do_api_key.startswith("dop_v1"):
        raise ValueError("DigitalOcean: Invalid API key specified")


def fetch_domains(do_api_key: str, do_domains: str = None, **args):  # NOSONAR
    validate_args(do_api_key)
    root_domains = []
    domains = []
    api = DoApi(do_api_key)

    if do_domains is not None and len(do_domains):
        root_domains = [domain.strip(" ") for domain in do_domains.split(",")]
    else:
        root_domains = [domain["name"] for domain in api.list_domains()]

    for domain in root_domains:
        if "" == domain or domain is None:
            continue

        try:
            records = api.get_records(domain)
        except DomainNotFoundError:
            logging.warning(f"Domain not found, skipping: {domain}")
            continue

        domains.extend(convert_records_to_domains(records, domain))

    return domains
