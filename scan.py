from finding import Finding

import logging


def pipeline_exit_code(findings):
    return 1 if findings else 0


def scan_exit_code(findings, timed_out=False, pipeline=False):
    if timed_out:
        return 3
    return pipeline_exit_code(findings) if pipeline else 0


async def scan_domain(domain, signatures, findings, output_handler):
    if domain.should_fetch_std_records:
        await domain.fetch_std_records()
    else:
        await domain.fetch_external_records()
    for signature in signatures:
        logging.debug(
            f"Testing domain '{domain.domain}' with signature '{signature.__name__}'"
        )
        if signature.test.potential(domain=domain):
            logging.debug(
                f"Potential takeover found on DOMAIN '{domain}' using signature '{signature.__name__}'"
            )
            if await signature.test.check(domain=domain):
                status = signature.test.CONFIDENCE.value
                logging.info(
                    f"Takeover {status} on {domain} using signature '{signature.__name__}'"
                )
                finding = Finding(
                    domain=domain,
                    signature=signature.__name__,
                    info=signature.test.INFO,
                    confidence=signature.test.CONFIDENCE,
                    more_info_url=signature.test.more_info_url,
                )
                findings.append(finding)
                output_handler.write(finding)
            else:
                logging.debug(
                    f"Takeover not possible on DOMAIN '{domain}' using signature '{signature.__name__}'"
                )
