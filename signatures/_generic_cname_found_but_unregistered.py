from domain import Domain
from . import checks
from .checks import helpers

from .templates.base import Base


def potential(domain: Domain, **kwargs) -> bool:
    if domain.CNAME != []:
        for cname in domain.CNAME:
            if helpers.is_registrable_domain(cname):
                return True
    return False


async def check(domain: Domain, **kwargs) -> bool:
    return await checks.CNAME.is_unregistered(domain)


INFO = """
The defined domain has a CNAME record configured but the CNAME is not registered. \
You should look to see if you can register this CNAME.
    """

test = Base(INFO)
test.potential = potential
test.check = check
