# Security Policy

## Reporting

Report vulnerabilities via GitHub Private Vulnerability Reporting:

https://github.com/yolo-labz/diploma-equivalence/security/advisories/new

No PGP keys. No email. Private advisories only.

## Response

- Acknowledgement of a report: within 7 days.
- Fix or mitigation plan: within 30 days of acknowledgement.
- Disclosure: coordinated through the advisory once a fix is released.

## Scope

The FastAPI service, the ingest scripts under `src/diploma_equivalence/infrastructure/ingest/`, and the Dockerfiles. The service handles course syllabi only; it stores no personal data.

## Supply chain

Container images carry build-provenance and SBOM attestations (`gh attestation verify`). Workflow actions are pinned by commit SHA and base images by digest.
