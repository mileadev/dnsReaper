import ipaddress

import tldextract

_extract = tldextract.TLDExtract(suffix_list_urls=())


def substrings_in_strings(substrings, strings):
    if type(strings) != list:
        strings = [strings]
    if type(substrings) != list:
        substrings = [substrings]
    for string in strings:
        for substring in substrings:
            if substring == "":
                continue
            if substring in string:
                return string
    return ""


def registrable_domain(name):
    name = name.rstrip(".").lower()
    result = _extract(name)
    domain = getattr(result, "top_domain_under_public_suffix", None)
    if domain is None:
        domain = getattr(result, "registered_domain", "")
    if domain:
        return domain
    # Unknown suffix (e.g. .local or an IP): fall back to the last two labels so
    # names under the same zone still compare equal.
    if "." not in name:
        return name
    try:
        ipaddress.ip_address(name)
    except ValueError:
        return ".".join(name.split(".")[-2:])
    return name


def same_registrable_domain(a, b):
    return registrable_domain(a) == registrable_domain(b)


def is_registrable_domain(name):
    return name.rstrip(".").lower() == registrable_domain(name)
