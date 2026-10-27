# VassEkteMat4u – Ekte Mat digital ordering & event booking (INFO212)

> All case material is **synthetic**, created for INFO212 Lab 7. All persons and companies are fictional.

## The case
Ekte Mat AS is a small catering company in Bergen. Today, orders come in by e-mail and phone, get
copied into an Excel sheet ("Bestillinger"), and are printed and pinned on the kitchen board.
Inquiries get lost (≈60 000 NOK of julebord requests found in spam), replies take 1–7 days, and
changes and allergies are sometimes forgotten.

**Goal (kick-off 12 Aug 2026):** replace e-mail/phone/Excel ordering with an online ordering and
event-booking system.

## Repository layout
| Path | Contents |
|---|---|
| [`docs/context/`](docs/context/) | Case material: interviews, as-is process, IT landscape, data, vision, constraints, reference. Treat as read-only source of truth. |
| [`docs/requirements/`](docs/requirements/) | User stories with acceptance criteria |
| [`docs/diagrams/`](docs/diagrams/) | UML diagrams as PlantUML/Mermaid source |
| [`docs/decisions.md`](docs/decisions.md) | Dated decisions log |
| [`backend/`](backend/) | Flask + Neo4j API skeleton (see its README to run it) |
| `docker-compose.yml` | Local Neo4j for development |

## Key facts
| Topic | Fact | Source |
|---|---|---|
| Budget | 450 000 NOK incl. 12 months hosting; running cost < 3 000 NOK/month | [budget_and_constraints](docs/context/04_vision_scope_constraints/budget_and_constraints.txt) |
| Deadline | Go-live 1 March 2027 (hard); wedding season from May 2027 | [budget_and_constraints](docs/context/04_vision_scope_constraints/budget_and_constraints.txt) |
| Team | 3 student developers, 2-week sprints; product owner Ingrid (Tue 09–10) | [budget_and_constraints](docs/context/04_vision_scope_constraints/budget_and_constraints.txt) |
| Integrations | Fiken (accounting, REST API, EHF), Vipps (private payments), Google Workspace | [current_IT_landscape](docs/context/02_as_is_process_and_IT/current_IT_landscape.txt) |
| Capacity | ~400 covers/day; 250 if a served wedding dinner that day | [Sunniva interview](docs/context/01_stakeholder_interviews/2_Sunniva_event_coordinator_2026-08-15.txt) |
| Customer groups | Corporate (weekly lunches), private (parties), weddings, health-conscious | [kick-off notes](docs/context/02_as_is_process_and_IT/kickoff_meeting_notes_2026-08-12.txt) |
| Data | Data must stay in EU/EEA; UI in Norwegian and English | [current_IT_landscape](docs/context/02_as_is_process_and_IT/current_IT_landscape.txt) |

## Stakeholders
- **Ingrid Solheim** – owner and product owner. Wants self-service booking, a kitchen overview, a 30 % deposit, Vipps and Fiken, and food origin shown on menus.
- **Sunniva Berg** – event coordinator. Wants a capacity calendar, automatic 7-day reminders about final guest numbers, and allergies per guest group confirmed by the kitchen.
- **Mateo Rinaldi** – head chef. Wants a kitchen tablet with PIN login, daily portions and allergies in red, a menu editor, ingredient-to-supplier links, a 3-day prep list, offline tolerance and fast pages.
- **Henrik Aas (Fjordtek)** – corporate customer. Wants a company login, standing orders, copy last week's order, changes until 10:00 the day before, approval above 15 000 NOK, a monthly EHF invoice with cost-centre codes, EU data storage and deletion on exit.

## Known tensions / open questions
1. **Deposit:** Ingrid wants "no deposit, no booking". Sunniva and Fjordtek say corporate clients can't or won't prepay. Possible resolution: deposit for weddings and private customers, monthly invoicing for corporate.
2. **Allergies vs GDPR:** allergy data about named persons can be health data (art. 9). Store it per guest group, not per named guest (matches Sunniva's need).
3. **Retention:** order data kept 5 years (Bookkeeping Act); other personal data shorter; customers can request access and deletion.
4. **Build vs buy:** build our own system, or configure an off-the-shelf catering SaaS? (Open since kick-off.)
5. **Offline:** the kitchen must still see today's orders when the internet is down.

## Data available
- [`orders_2024_2025_export.xlsx`](docs/context/03_data/orders_2024_2025_export.xlsx): ~820 historical orders (customer type, channel, menu package, guests, price, dietary notes, status, reply time).
- [`customer_emails_export.csv`](docs/context/03_data/customer_emails_export.csv): 30 customer e-mails in Norwegian and English.

## How we work
See [`docs/context/PROJECT_INSTRUCTIONS.txt`](docs/context/PROJECT_INSTRUCTIONS.txt). In short:
- Cite the source file for every requirement or fact; when stakeholders disagree, say so.
- Model-driven: UML (use case, activity, class, sequence, state) in PlantUML or Mermaid, user stories with acceptance criteria.
- Respect the constraints: go-live 1 March 2027, 450k NOK, < 3 000 NOK/month, EU/EEA data, NO/EN UI, GDPR.
- Work on a branch, open a pull request, get one teammate to review before merging to `main`.
- Record decisions as dated lines in [`docs/decisions.md`](docs/decisions.md).

## Sprint 0
- [x] Set up Git repo
- [ ] Set up Jira/Trello board
- [ ] Agree on a Definition of Done
