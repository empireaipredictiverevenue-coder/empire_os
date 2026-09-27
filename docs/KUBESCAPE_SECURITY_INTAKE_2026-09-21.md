# Kubescape Security Intake — 2026-09-21

## Decision

**Adopt when Empire's Kubernetes deployment becomes real. Use it earlier in
CI against Kubernetes YAML/Helm assets, but do not install an in-cluster
operator on the current EmpireOS host because no Kubernetes cluster is
currently active.**

Official repository:
https://github.com/kubescape/kubescape

## Why it fits Empire

Kubescape provides:
- Kubernetes misconfiguration scanning;
- NSA-CISA / MITRE ATT&CK / CIS-aligned checks;
- container-image vulnerability scanning;
- RBAC and security-posture analysis;
- CI/CD scanning of YAML and Helm assets;
- continuous in-cluster scanning through the Kubescape Operator;
- vulnerability results for deployed images;
- machine-readable results suitable for Empire Sentinel/Daily Results.

The project is Apache-2.0 licensed and is a CNCF incubating project.

## Current Empire state

The current EmpireOS production host is systemd-based. There is no active
kubectl/k3s/Kubernetes control plane on this host. Installing the Kubescape
operator now would therefore add no production value.

## Adoption phases

### Phase A — pre-Kubernetes

When deploy/k8s or Helm assets exist:
- scan manifests in CI;
- fail only on explicitly approved high/critical policy classes;
- save JSON results under runtime/security/kubescape/;
- surface counts in Founder Daily Results;
- preserve risk-acceptance evidence for deliberate exceptions.

### Phase B — Kubernetes staging

Install Kubescape Operator via its supported Helm/ArgoCD path in staging:
- configuration scan;
- vulnerability scan;
- relevancy where supported;
- continuous scanning;
- no automatic image patching initially.

### Phase C — Kubernetes production

After staging validation:
- continuous cluster posture;
- image CVE monitoring;
- namespace/workload summaries;
- integrate new critical findings into Empire Sentinel;
- Founder Console Daily Results shows:
  - failed controls;
  - high/critical CVEs;
  - newly introduced risk;
  - accepted risk;
  - remediation status.

## Authority

Kubescape findings should initially produce incidents/recommendations only.
Automatic image patching, workload mutation or policy enforcement should be a
separate governed authority decision.
