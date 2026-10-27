# Decisions log

Add one dated line per decision: what was decided, who decided, and the source or meeting.
Format: `- YYYY-MM-DD – <decision> (decided by <who>; source: <file or meeting>)`

- 2026-10-27 – Frontend uses Flask templates (server-rendered), not a separate JavaScript app. (decided by team; source: team decision)
- 2026-10-27 – Login is basic: register and log in with a unique e-mail and password. Password reset by e-mail is not implemented in this version, because it needs an e-mail service. Deviates from `basic_desc.txt` (password retrieval/reset), which is deferred. (decided by team; source: team decision)
- 2026-10-27 – The interface is available in both Norwegian and English. (decided by team; source: team decision, `current_IT_landscape.txt`)
- 2026-10-27 – Minimum guests per event type use placeholder values (corporate lunch 8, birthday 10, confirmation 15, christmas party 20, conference 30, wedding 50) until the product owner confirms them. (decided by team; source: `docs/diagrams/README.md`)
- 2026-10-27 – Deposits are out of scope for this version, but the design must allow adding them later. (decided by team; source: team decision; resolves the Ingrid vs Sunniva/Fjordtek tension for now)
- 2026-10-27 – Corporate accounts are included: a company account with several users ordering, and orders above the company's approval limit must be approved by the company's approver. (decided by team; source: team decision, Fjordtek interview)
- 2026-10-27 – Kitchen and driver screens are included. (decided by team; source: team decision, Mateo interview, flowcharts)
