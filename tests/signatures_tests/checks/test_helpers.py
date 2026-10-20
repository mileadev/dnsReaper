from signatures.checks import helpers


## substrings_in_strings
def test_substrings_in_strings_for_single_string():
    assert helpers.substrings_in_strings("abc", "abc") == "abc"


def test_substrings_in_strings_for_single_substring():
    assert helpers.substrings_in_strings("b", "abc") == "abc"


def test_substrings_in_strings_for_multiple_substring():
    assert helpers.substrings_in_strings(["a", "b", "c"], "abc") == "abc"


def test_substrings_in_strings_returns_first_for_multiple_strings():
    assert helpers.substrings_in_strings("a", ["abc", "aed"]) == "abc"


def test_substrings_in_strings_no_subtrings():
    assert helpers.substrings_in_strings("", ["abc", "aed"]) == ""


def test_substrings_in_strings_no_strings():
    assert helpers.substrings_in_strings("a", "") == ""


def test_substrings_in_strings_nothing():
    assert helpers.substrings_in_strings("", "") == ""


## registrable_domain / same_registrable_domain / is_registrable_domain
def test_same_registrable_domain_for_different_co_uk_domains():
    assert helpers.same_registrable_domain("example.co.uk", "attacker.co.uk") == False


def test_same_registrable_domain_for_subdomains_of_the_same_co_uk_domain():
    assert (
        helpers.same_registrable_domain("foo.example.co.uk", "bar.example.co.uk")
        == True
    )


def test_is_registrable_domain_for_a_co_uk_domain():
    assert helpers.is_registrable_domain("foo.co.uk") == True


def test_is_registrable_domain_for_a_subdomain_of_a_co_uk_domain():
    assert helpers.is_registrable_domain("sub.foo.co.uk") == False
