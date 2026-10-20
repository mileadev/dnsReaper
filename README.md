[![Maintenance](https://img.shields.io/badge/Maintained%3F-yes-green.svg)](https://GitHub.com/punk-security/secret-magpie-cli/graphs/commit-activity)
[![Maintainer](https://img.shields.io/badge/maintainer-PunkSecurity-blue)](https://www.punksecurity.co.uk)
[![Docker Pulls](https://img.shields.io/docker/pulls/punksecurity/dnsreaper)](https://hub.docker.com/r/punksecurity/dnsreaper)
[![Lines of Code](https://sonarcloud.io/api/project_badges/measure?project=punk-security_dnsReaper&metric=ncloc)](https://sonarcloud.io/summary/new_code?id=punk-security_dnsReaper)
[![Vulnerabilities](https://sonarcloud.io/api/project_badges/measure?project=punk-security_dnsReaper&metric=vulnerabilities)](https://sonarcloud.io/summary/new_code?id=punk-security_dnsReaper)
[![Bugs](https://sonarcloud.io/api/project_badges/measure?project=punk-security_dnsReaper&metric=bugs)](https://sonarcloud.io/summary/new_code?id=punk-security_dnsReaper)

# DNS Reaper

DNS Reaper is a sub-domain takeover scanner with an emphasis on accuracy, speed and
the number of signatures it checks. It can scan a domain list, a BIND zone file, or
the records held by a DNS provider, and it can run as a command-line tool, in a
container, or as an AWS Lambda service.

Use it only against domains you own or have written permission to test.

![DNS Reaper detects a broken CNAME record](docs/reaper_detection.png "DNS Reaper detects a domain with a broken CNAME record")

## Requirements

- **Python 3.11 or newer** for a source install. The container uses Python 3.11.
  Python 3.9 and 3.10 are not supported by the current dependency set.
- **Docker 20.10+** for the container image. The Lambda build also requires Docker.
- Outbound DNS (UDP and TCP port 53) and HTTPS (port 443) access.
- Read-only DNS provider credentials when using a provider.
- For the Lambda deployment: Terraform 1.5+, AWS credentials, and Docker.

## Quick start with Docker

Build the image from this checkout. Replace `dnsreaper:local` if you use a different
tag. The official image published by the upstream project is
`punksecurity/dnsreaper`; build locally if you need the changes in this repository.

```shell
docker build -t dnsreaper:local .
docker run --rm dnsreaper:local --help
```

Scan one domain and print JSON findings on stdout:

```shell
docker run --rm dnsreaper:local \
  single --domain example.com --out stdout --out-format json
```

The banner and log messages go to stderr, so JSON on stdout can be piped or parsed
directly. Add `2>/dev/null` only when you do not need the logs.

### Docker with files and a host output directory

The image runs as the unprivileged `app` user. To write a bind-mounted output
directory, run with your own user ID and a writable temporary home:

```shell
mkdir -p out
printf '%s\n' example.com > domains.txt

docker run --rm \
  --user "$(id -u):$(id -g)" \
  --read-only --tmpfs /tmp \
  -e HOME=/tmp \
  -v "$PWD/domains.txt:/work/domains.txt:ro" \
  -v "$PWD/out:/work/out" \
  dnsreaper:local \
  file --filename /work/domains.txt \
  --out /work/out/results.json --out-format json --pipeline
```

Notes:

- The source `domains.txt` can contain one domain per line. Empty lines and comments
  are ignored by the `file` provider.
- The output directory must already exist and be writable by the user in `--user`.
- `--read-only` and `--tmpfs /tmp` harden the container. `HOME=/tmp` lets Python and
  `tldextract` write their temporary cache there.
- Without `--user`, the image writes to `/app` as the `app` user. That is fine for a
  short-lived container, but the output is lost when the container is removed unless
  you mount a writable directory.

### Docker Compose

The repository includes a production-oriented `compose.yaml` for a file-based scan.
It uses a read-only root filesystem, drops Linux capabilities, runs as your UID/GID,
and writes JSON to `out/results.json`.

```shell
mkdir -p out
printf '%s\n' example.com > domains.txt
docker compose build
DOCKER_UID="$(id -u)" DOCKER_GID="$(id -g)" docker compose run --rm dnsreaper
```

`DOCKER_UID` and `DOCKER_GID` are used instead of `UID`/`GID` because some shells
(for example bash) make `UID` read-only.

`docker compose run` returns the scanner exit code. Set `SCAN_TIMEOUT` in the
environment to change the default one-hour scan limit. To use a provider instead of
the file provider, override the command:

```shell
DOCKER_UID="$(id -u)" DOCKER_GID="$(id -g)" docker compose run --rm dnsreaper \
  single --domain example.com --out /work/out/results.json --out-format json
```

## Install and run from source

```shell
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main.py --help
```

Scan a file, a single domain, or a provider:

```shell
# File of domains; write CSV by default
python main.py file --filename domains.txt

# JSON on stdout, non-zero exit when findings exist
python main.py file --filename domains.txt \
  --out stdout --out-format json --pipeline

# One domain
python main.py single --domain example.com --out results.json --out-format json

# AWS Route53 using the normal boto3 credential chain
python main.py aws

# Increase concurrency (default 30)
python main.py file --filename domains.txt --parallelism 80
```

Run `python main.py PROVIDER --help` for the exact arguments for a provider.

## Output and exit codes

- The default output file is `results.csv` (`results.json` with
  `--out-format json`).
- `--out stdout` streams findings to stdout. The banner and diagnostics remain on
  stderr.
- JSON output is a valid array, including `[]` when there are no findings. CSV output
  has a header only when at least one finding is written; use JSON for automation.
- `SCAN_TIMEOUT` controls the scan limit in seconds. The default is `3600`. An invalid
  or non-positive value is logged and replaced with `3600`.
- `--pipeline` makes the process useful in CI:
  - `0`: scan completed, no findings.
  - `1`: scan completed, at least one finding.
  - `3`: scan timed out. The output contains only the findings completed before the
    timeout.
- Other exit codes: `2` for invalid arguments and `255` when the selected provider
  returns no domains to scan.
- Without `--pipeline`, a completed scan returns `0`; a timeout returns `3`.

The CSV and JSON records contain the affected domain, signature, confidence, A/AAAA/
CNAME/NS records and a link to more information. Output paths must be writable by the
process; create parent directories first.

## Providers

Credentials are read when the provider fetches records. Use read-only credentials and
keep them in a secret manager or environment file. Command-line secrets can appear in
shell history and process listings; prefer the AWS credential chain or a wrapper that
injects secrets at runtime.

| Provider | Required arguments | Notes |
| --- | --- | --- |
| `aws` | none | Uses boto3's credential chain. Optional `--aws-access-key-id`, `--aws-access-key-secret`, `--aws-session-token`. Needs Route53 list/get permissions. |
| `azure` | `--az-subscription-id`, `--az-tenant-id`, `--az-client-id`, `--az-client-secret` | Service principal with Reader access to the DNS zones. |
| `bind` | `--bind-zone-file` | A BIND zone file, or a directory containing only zone files. |
| `cloudflare` | `--cloudflare-token` | Token needs read access to the zones and DNS records. |
| `digitalocean` | `--do-api-key` | Optional `--do-domains` limits the scan to a comma-separated list. |
| `file` | `--filename` | File or directory of domains, one per line. |
| `godaddy` | `--gd-api-key`, `--gd-api-secret` | Optional `--gd-domains` limits the scan. |
| `googlecloud` | `--project-id` | Set `GOOGLE_APPLICATION_CREDENTIALS` to a JSON service-account file with DNS Reader. |
| `projectdiscovery` | `--pd-api-key`, `--pd-domains` | Queries the ProjectDiscovery/Chaos API for subdomains. |
| `securitytrails` | `--st-api-key`, `--st-domains` | Queries the SecurityTrails API. |
| `single` | `--domain` | Scans one domain. |
| `zonetransfer` | `--zonetransfer-nameserver`, `--zonetransfer-domain` | Requires TCP port 53 and an AXFR allow-list entry on the nameserver. |

Provider-specific setup, including the minimum cloud permissions, is in
[`docs/`](docs/README.md). The AWS policy in [`docs/aws.md`](docs/aws.md) is a good
starting point for a read-only role.

## CLI options

These options apply after the provider arguments:

| Option | Purpose |
| --- | --- |
| `--out PATH` | Output file. Default `results.<format>`. Use `stdout` to stream. |
| `--out-format {csv,json}` | Output format. Default `csv`. |
| `--resolver ADDRESSES` | Comma-separated DNS resolvers, or `''` to use the system resolver. A public resolver list is used by default. |
| `--parallelism N` | Number of domains scanned concurrently. Must be at least 1; default 30. |
| `--disable-probable` | Skip probable findings. |
| `--enable-unlikely` | Include unlikely findings; expect more false positives. |
| `--signature NAME` | Run only the named signature. Repeatable. |
| `--exclude-signature NAME` | Skip the named signature. Repeatable. |
| `--pipeline` | Return `1` when findings exist and `3` on timeout. |
| `-v`, `-vv` | More log detail. |
| `--nocolour` | Disable ANSI colour in logs. |

## Production container notes

- The runtime image is based on `python:3.11-alpine`, installs only
  `requirements.txt`, excludes tests and repository tooling via `.dockerignore`, and
  runs as the non-root `app` user.
- The base image tag is a moving tag so rebuilds pick up Alpine and Python security
  fixes. Rebuild the image regularly, or pin a digest if you need byte-for-byte
  reproducibility.
- The image never contains `pdkey`, `.env`, Terraform state, test files or scan output.
  Keep it that way when adding files to the build context.
- To build the Lambda package locally:

  ```shell
  docker build -t dnsreaper-lambda:local --target lambda .
  ```

- To build the multi-architecture release image with Buildx/Bake:

  ```shell
  VERSION=local docker buildx bake release --push=false
  ```

- The GitHub Actions release/nightly workflows push to Docker Hub. They expect a
  `DOCKER_ACCESS_TOKEN` secret and the `punksecurity` Docker Hub account. Fork users
  must change the login user or use a local build.

## AWS Lambda and Terraform

The Lambda code is an AWS API Gateway/Mangum service backed by DynamoDB. Terraform
builds the deployment zip with Docker and uploads it to Lambda.

### Deploy

1. Install Docker, Terraform 1.5+, and configure AWS credentials with permission to
   manage Lambda, IAM, DynamoDB, CloudWatch Logs and (if you add an API) API Gateway.
2. Create the ProjectDiscovery key file. Terraform reads this file and passes its
   contents to the Lambda environment:

   ```shell
   printf '%s' "$PD_API_KEY" > pdkey
   chmod 600 pdkey
   ```

3. Initialize, review and apply:

   ```shell
   terraform init
   terraform plan
   terraform apply
   ```

4. Terraform outputs the Lambda function name and DynamoDB table name. The deployment
   uses a 30-second Lambda timeout, a 20-second internal scan budget, 256 MB of memory,
   a 2,000-domain cap, 14-day log retention, and a DynamoDB TTL of 24 hours.
   `lambda_reserved_concurrency` defaults to 10 and can be changed with
   `-var="lambda_reserved_concurrency=..."`.

The Lambda package is rebuilt when Python sources, `requirements.txt`,
`lambda-requirements.txt`, `Dockerfile` or `.dockerignore` change. The build uses the
local Docker daemon. It uses Buildx when available, otherwise it falls back to the
legacy builder, and it fails if the resulting image is not `linux/amd64`. Install the
Buildx plugin on ARM hosts if the legacy builder cannot produce an amd64 image.

### HTTP endpoints

The FastAPI app exposes:

- `GET /` — health message.
- `GET /check?domain=example.com` — scan without storing results.
- `GET /scan?domain=example.com` — scan and store results; returns a GUID.
- `GET /result?id=GUID` — read a stored result.

The repository does **not** create a public HTTP endpoint, API Gateway, authorizer or
rate limit. Before exposing it:

- Put API Gateway (or another authenticated proxy) in front of the Lambda. Require
  IAM, Cognito, JWT or another strong authorizer.
- Add per-client throttling, request-size limits, WAF rules and alarms. The scan
  endpoint accepts a comma-separated domain list and can consume significant DNS
  traffic.
- Do **not** create a Lambda Function URL with `AuthType: NONE`.
- Keep the `pdkey` out of logs, Terraform state in an encrypted remote backend, and
  restrict `lambda:InvokeFunction` to the proxy role.
- Use a VPC/egress design that allows DNS and HTTPS to the provider APIs and public
  resolvers the scanner needs.

### Destroy

```shell
terraform destroy
```

Terraform state contains the ProjectDiscovery key through the Lambda environment.
Store state in an encrypted backend with restricted access, and do not commit
`terraform.tfstate*`, `pdkey`, or `.env`.

## Security and operations

- Scan only assets you are authorized to test. The scanner sends DNS queries and HTTP
  requests to targets from your infrastructure.
- Use read-only provider credentials. Rotate them after accidental exposure and avoid
  passing secrets as command-line arguments where a credential chain is available.
- The container defaults to a non-root user. Use a read-only root filesystem, drop
  capabilities and mount only the files needed for a run, as shown above.
- Pin and audit dependencies. The runtime and test pins are checked with
  `pip-audit`; rerun it and rebuild images when advisories change.
- Findings can contain internal hostnames and DNS records. Treat output, CloudWatch
  logs and DynamoDB records as potentially sensitive.
- The active/live tests make real DNS and HTTPS requests. They can be affected by
  third-party outages and should not gate a deployment by themselves.

## Development and tests

```shell
python -m pip install -r requirements.txt -r test-requirements.txt
python -m pytest -q -k "not active"       # offline suite
python -m pytest -q -k "active"           # live network checks (optional)
python -m pip install black==26.10.1
black --check .
python -m compileall -q .
```

The offline suite is the release gate. CI runs it on supported Python versions and
builds the container. The active network tests are reported separately because they
depend on external DNS and HTTP services.

For Terraform changes:

```shell
terraform fmt -check
terraform init -backend=false
terraform validate
```

## License

See [LICENSE](LICENSE). Use of this tool is subject to the license and to the
authorization requirements above.
