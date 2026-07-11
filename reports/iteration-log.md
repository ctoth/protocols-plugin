# Iteration Log

## 001 - 2026-07-11
- Start: 0 failures in 17 focused actor-profile cases
- Target: native Codex `default` actor read-only discovery
- Result: 0 failures in 34 focused actor-profile cases; full gate passed
- Commits: included in this atomic iteration fix

## 002 - 2026-07-11
- Start: 0 failures in 7 focused installer contract tests; live Codex plugin 0.2.0 lacked the role hook
- Target: native Codex plugin refresh and independent doctor compatibility checks
- Result: 0 failures in 9 focused installer contract tests; Codex and Claude at 0.3.1; full gate passed
- Commits: included in this atomic iteration fix

## 003 - 2026-07-11
- Start: 0 failures in 9 focused installer contract tests
- Target: native Codex Windows hook execution, exact live trust, and fresh default-worker acceptance
- Result: 0 failures in 13 focused contracts; deterministic gate stages passed; live doctor correctly awaits the separate 0.3.2 refresh/trust verifier
- Commits: included in this atomic iteration fix

## 004 - 2026-07-11
- Start: 2 defects from live protocols 0.3.2 verification
- Targets: disabled/modified explicit trust upgrade and active-cache fixture isolation
- Result: 0 failures in 13 focused contracts; full Git/MSYS gate and live 0.3.2 doctor passed
- Commits: included in this atomic iteration fix
