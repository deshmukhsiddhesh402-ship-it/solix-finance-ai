# Security Reporting and Financial Data Handling

## Reporting a vulnerability

Please do not disclose suspected vulnerabilities in a public issue. Report them privately to the repository maintainers with:

- a concise description of the affected component;
- reproducible steps or a minimal proof of concept;
- the security impact and affected data or tenant boundary;
- the first known commit, branch, or deployment where the issue appears; and
- any suggested mitigation or workaround.

Do not include production credentials, API keys, customer data, or other secrets in the report.

## Financial data handling

Solix Finance AI is intended to support accounting and finance workflows, but generated explanations and imported documents are not a substitute for professional review. Before relying on an output for a filing, posting, payment, tax position, or management decision:

1. verify the source document and the relevant period;
2. confirm tenant, organization, and user context;
3. review calculations and rounding using authoritative records;
4. obtain required approval from an authorized human reviewer; and
5. preserve the supporting evidence and audit trail.

Never paste secrets, payment credentials, or unnecessary personal data into AI prompts, issue reports, screenshots, or test fixtures.

## Safe disclosure expectations

Maintainers should acknowledge reports, reproduce them in a non-production environment, avoid exposing sensitive details in public discussion, and document the remediation and regression coverage before release.
