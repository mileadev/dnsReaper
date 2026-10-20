from domain import Domain
from . import checks
from .checks import helpers
import detection_enums

from .templates.base import Base


def potential(domain: Domain, **kwargs) -> bool:
    if domain.CNAME != []:
        for cname in domain.CNAME:
            if not helpers.same_registrable_domain(domain.domain, cname):
                # does not belong to the same organisation
                return True
    return False


async def check(domain: Domain, **kwargs) -> bool:
    return await checks.WEB.status_code_404(domain, False)


INFO = """
The defined domain has a CNAME record configured but the website returns a 404 over HTTP. \
You should investigate this 404 response.
    """

test = Base(INFO, detection_enums.CONFIDENCE.UNLIKELY)
test.potential = potential
test.check = check
