import requests

from domain import Domain

HTTP_TIMEOUT = 30


class DomainNotFoundError(Exception):
    def __init__(self, domain):
        self.message = "Domain not found: " + domain
        super().__init__(self.message)


def check_response(response, forbidden_message=None):
    if response.status_code == 401:
        raise ValueError("Invalid API key specified.")

    if response.status_code == 403 and forbidden_message is not None:
        raise ValueError(forbidden_message)

    if response.status_code < 200 or response.status_code >= 300:
        raise ValueError("Invalid response received from API: " + response.text)

    return response


def make_request(session, url):
    return session.prepare_request(requests.Request("GET", url))


def convert_records_to_domains(records, root_domain, replace_at_in_cname=False):
    buf = {}
    for record in records:
        if "@" == record["name"]:
            continue

        record_name = f"{record['name']}.{root_domain}"

        if record_name not in buf.keys():
            buf[record_name] = {}

        if record["type"] not in buf[record_name].keys():
            buf[record_name][record["type"]] = []

        if "data" in record.keys():
            buf[record_name][record["type"]].append(record["data"])

    def extract_records(subdomain, desired_type):
        return [r.rstrip(".") for r in buf[subdomain][desired_type]]

    for subdomain in buf.keys():
        domain = Domain(subdomain.rstrip("."), fetch_standard_records=False)

        if "A" in buf[subdomain].keys():
            domain.A = extract_records(subdomain, "A")
        if "AAAA" in buf[subdomain].keys():
            domain.AAAA = extract_records(subdomain, "AAAA")
        if "CNAME" in buf[subdomain].keys():
            domain.CNAME = extract_records(subdomain, "CNAME")
            if replace_at_in_cname:
                domain.CNAME = [x.replace("@", root_domain) for x in domain.CNAME]
        if "NS" in buf[subdomain].keys():
            domain.NS = extract_records(subdomain, "NS")

        yield domain
