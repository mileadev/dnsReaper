import importlib
import json
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def providers_pkg():
    saved = {
        name: module
        for name, module in sys.modules.items()
        if name == "providers" or name.startswith("providers.")
    }
    for name in saved:
        del sys.modules[name]

    package = types.ModuleType("providers")
    package.__path__ = [str(REPO_ROOT / "providers")]
    sys.modules["providers"] = package

    yield

    for name in list(sys.modules):
        if name == "providers" or name.startswith("providers."):
            del sys.modules[name]
    sys.modules.update(saved)


def fake_response(payload=None, status_code=200, text=None):
    return types.SimpleNamespace(
        status_code=status_code,
        text=text if text is not None else json.dumps(payload),
        json=lambda: payload,
    )


def test_aws_get_zones_paginates_and_filters_private(providers_pkg):
    aws = importlib.import_module("providers.aws")

    class FakePaginator:
        def paginate(self):
            yield {
                "HostedZones": [
                    {
                        "Id": "/hostedzone/private",
                        "Name": "private.example.",
                        "Config": {"PrivateZone": True},
                    }
                ]
            }
            yield {
                "HostedZones": [
                    {
                        "Id": "/hostedzone/public",
                        "Name": "public.example.",
                        "Config": {"PrivateZone": False},
                    }
                ]
            }

    class FakeClient:
        paginator_name = None

        def get_paginator(self, name):
            self.paginator_name = name
            return FakePaginator()

    client = FakeClient()
    zones = aws.get_zones(client)

    assert client.paginator_name == "list_hosted_zones"
    assert [zone["Name"] for zone in zones] == ["public.example."]


def test_do_list_domains_follows_pages(providers_pkg):
    digitalocean = importlib.import_module("providers.digitalocean")
    api = digitalocean.DoApi("dop_v1_test")
    next_url = "https://api.digitalocean.com/v2/domains?page=2&per_page=200"
    pages = {
        "domains?per_page=200": fake_response(
            {
                "domains": [{"name": "one.example"}],
                "links": {"pages": {"next": next_url}},
            }
        ),
        next_url: fake_response(
            {"domains": [{"name": "two.example"}], "links": {"pages": {}}}
        ),
    }
    requested = []

    def fake_get(url):
        requested.append(url)
        return pages[url]

    api._get = fake_get

    assert [domain["name"] for domain in api.list_domains()] == [
        "one.example",
        "two.example",
    ]
    assert requested == ["domains?per_page=200", next_url]


def test_do_get_records_follows_pages(providers_pkg):
    digitalocean = importlib.import_module("providers.digitalocean")
    api = digitalocean.DoApi("dop_v1_test")
    next_url = "https://api.digitalocean.com/v2/domains/example.com/records?page=2&per_page=200"
    pages = {
        "domains/example.com/records?per_page=200": fake_response(
            {
                "domain_records": [{"name": "www", "type": "A", "data": "1.2.3.4"}],
                "links": {"pages": {"next": next_url}},
            }
        ),
        next_url: fake_response(
            {
                "domain_records": [{"name": "api", "type": "A", "data": "5.6.7.8"}],
                "links": {"pages": {}},
            }
        ),
    }
    api._get = pages.__getitem__

    records = api.get_records("example.com")

    assert [record["name"] for record in records] == ["www", "api"]


def test_do_fetch_domains_skips_missing_domain(providers_pkg, monkeypatch):
    digitalocean = importlib.import_module("providers.digitalocean")

    def fake_get_records(self, domain):
        if domain == "missing.example":
            raise digitalocean.DomainNotFoundError(domain)
        return [{"name": "www", "type": "A", "data": "1.2.3.4"}]

    monkeypatch.setattr(digitalocean.DoApi, "get_records", fake_get_records)

    domains = digitalocean.fetch_domains("dop_v1_test", "missing.example,good.example")

    assert [domain.domain for domain in domains] == ["www.good.example"]


def test_do_check_response_reports_dict_error_body(providers_pkg):
    digitalocean = importlib.import_module("providers.digitalocean")
    response = fake_response({"id": "server_error", "message": "boom"}, status_code=500)

    with pytest.raises(ValueError) as error:
        digitalocean.DoApi.check_response(response)

    assert "server_error" in str(error.value)


def test_pd_fetch_domains_skips_missing_domain(providers_pkg, monkeypatch):
    projectdiscovery = importlib.import_module("providers.projectdiscovery")

    def fake_get_subdomains(self, domain):
        if domain == "missing.example":
            raise projectdiscovery.DomainNotFoundError(domain)
        return fake_response({"subdomains": ["www"]})

    monkeypatch.setattr(projectdiscovery.PDApi, "get_subdomains", fake_get_subdomains)

    domains = projectdiscovery.fetch_domains("api-key", "missing.example,good.example")

    assert [domain.domain for domain in domains] == ["www.good.example"]


def test_file_provider_skips_blanks_and_comments(providers_pkg, tmp_path):
    file_provider = importlib.import_module("providers.file")
    domains_file = tmp_path / "domains.txt"
    domains_file.write_text("\n# comment\n example.com \n\n")

    domains = file_provider.fetch_domains(str(domains_file))

    assert [domain.domain for domain in domains] == ["example.com"]


def test_file_provider_missing_path_returns_no_domains(providers_pkg, tmp_path):
    file_provider = importlib.import_module("providers.file")

    assert file_provider.fetch_domains(str(tmp_path / "missing.txt")) == []


def test_godaddy_fetch_domains_skips_missing_domain(providers_pkg, monkeypatch):
    godaddy = importlib.import_module("providers.godaddy")

    def fake_get_records(self, domain):
        if domain == "missing.example":
            raise godaddy.DomainNotFoundError(domain)
        return fake_response([{"name": "www", "type": "A", "data": "1.2.3.4"}])

    monkeypatch.setattr(godaddy.GDApi, "get_records", fake_get_records)

    domains = godaddy.fetch_domains("key", "secret", "missing.example,good.example")

    assert [domain.domain for domain in domains] == ["www.good.example"]


def test_securitytrails_fetch_domains_skips_missing_domain(providers_pkg, monkeypatch):
    securitytrails = importlib.import_module("providers.securitytrails")

    def fake_get_subdomains(self, domain):
        if domain == "missing.example":
            raise securitytrails.DomainNotFoundError(domain)
        return fake_response({"subdomain_count": 1, "subdomains": ["www"]})

    monkeypatch.setattr(securitytrails.STApi, "get_subdomains", fake_get_subdomains)

    domains = securitytrails.fetch_domains("api-key", "missing.example,good.example")

    assert [domain.domain for domain in domains] == ["www.good.example"]
