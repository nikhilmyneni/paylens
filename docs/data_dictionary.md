# Synthetic compensation data dictionary

All IDs are immutable strings. All currency values are nominal amounts in the row's ISO 4217 currency. Dates are calendar dates; timestamps are UTC. Required fields are non-null unless stated otherwise. Foreign keys must resolve to an existing parent record. The tables are generated from synthetic data only.

| Entity.field | Type | Required | Allowed values / units | Uniqueness and validation |
| --- | --- | --- | --- | --- |
| `employee.id` | string(20) | Yes | `EMP-000001` format | Primary key; zero-padded positive counter. |
| `employee.display_name` | string(80) | Yes | Synthetic label | Non-empty; no real identity. |
| `employee.hire_date` | date | Yes | Calendar date | On or before first assignment. |
| `employee.status` | string(20) | Yes | `active`, `inactive` | Active employees have a current assignment. |
| `role.id` | string(30) | Yes | `ROLE-...` | Primary key. |
| `role.name` | string(80) | Yes | Job title | Unique, non-empty. |
| `role.family` | string(40) | Yes | Job family label | Non-empty. |
| `level.id` | string(20) | Yes | `L01` through `L10` | Primary key. |
| `level.rank` | integer | Yes | 1–10, ordinal | Unique, positive. |
| `location.id` | string(20) | Yes | `LOC-...` | Primary key. |
| `location.name` | string(80) | Yes | City / pay market | Non-empty. |
| `location.currency` | string(3) | Yes | ISO 4217 code | Matches generated salary currency at effective location unless a documented conversion applies. |
| `compensation_band.id` | string(90) | Yes | `BAND-<role>-<level>-<location>-2026` | Primary key; immutable. |
| `compensation_band.role_id` | FK string | Yes | `role.id` | Parent must exist. |
| `compensation_band.level_id` | FK string | Yes | `level.id` | Parent must exist. |
| `compensation_band.location_id` | FK string | Yes | `location.id` | Parent must exist. |
| `compensation_band.currency` | string(3) | Yes | ISO 4217 code | Equals location pay-market currency. |
| `compensation_band.minimum` | decimal(14,2) | Yes | Annual full-time pay | Positive and `minimum <= midpoint`. |
| `compensation_band.midpoint` | decimal(14,2) | Yes | Annual full-time pay | `minimum <= midpoint <= maximum`. |
| `compensation_band.maximum` | decimal(14,2) | Yes | Annual full-time pay | `maximum >= midpoint`. |
| `compensation_band.effective_from` | date | Yes | Inclusive date | Unique with role, level and location; ranges for same key must not overlap. |
| `compensation_band.effective_to` | date | Yes | Inclusive date | On or after `effective_from`. |
| `salary_record.id` | string(40) | Yes | `SAL-<employee-id>-YYYY-MM` | Primary key; employee/month identifies baseline record. |
| `salary_record.employee_id` | FK string | Yes | `employee.id` | Parent must exist. |
| `salary_record.effective_month` | date | Yes | First day of pay month | Falls inside a valid assignment. |
| `salary_record.monthly_amount` | decimal(14,2) | Yes | Gross base pay per month | Positive; full-time equivalent derives using FTE. |
| `salary_record.currency` | string(3) | Yes | ISO 4217 code | FX rate required when conversion is needed. |
| `salary_record.event_kind` | string(20) | Yes | `baseline`, `promotion`, `adjustment` | Append another event to change pay; do not edit history. |
| `performance_evidence.id` | string(40) | Yes | `PERF-...` | Primary key. |
| `performance_evidence.employee_id` | FK string | Yes | `employee.id` | Parent must exist. |
| `performance_evidence.period_end` | date | Yes | Review-period end | Cannot be used for a prior comparison date. |
| `performance_evidence.rating` | integer | Yes | 1–5 calibrated score | Check constraint: 1 through 5. |
| `performance_evidence.note` | string(150) | Yes | Synthetic job-related reason | Non-empty; excludes protected attributes. |
| `tenure.id` | string(40) | Yes | `TEN-...` | Primary key. |
| `tenure.employee_id` | FK string | Yes | `employee.id` | Parent must exist. |
| `tenure.as_of` | date | Yes | Snapshot date | No future information in a comparison. |
| `tenure.months_in_company` | integer | Yes | Whole months | Derived from hire date; non-negative. |
| `tenure.months_in_level` | integer | Yes | Whole months | Derived from assignment start; non-negative and <= months in company. |
| `promotion.id` | string(40) | Yes | `PROM-...` | Primary key. |
| `promotion.employee_id` | FK string | Yes | `employee.id` | Parent must exist. |
| `promotion.from_assignment_id` | FK string | Yes | `employee_assignment.id` | Same employee; assignment ends before new one begins. |
| `promotion.to_assignment_id` | FK string | Yes | `employee_assignment.id` | Same employee; changed role/level, normally higher rank. |
| `promotion.effective_date` | date | Yes | Effective date | Equals new assignment start. |
| `promotion.reason` | string(100) | Yes | Documented reason | Non-empty. |
| `adjustment_proposal.id` | string(30) | Yes | `ADJ-2026-000001` | Primary key; immutable. |
| `adjustment_proposal.comparison_id` | FK string | Yes | `comparison_result.id` | Proposal cites an immutable analysis result. |
| `adjustment_proposal.employee_id` | FK string | Yes | `employee.id` | Same employee as comparison. |
| `adjustment_proposal.proposed_annual` | decimal(14,2) | Yes | Annual full-time pay | Positive; rationale documents amount. |
| `adjustment_proposal.currency` | string(3) | Yes | ISO 4217 code | Same pay-market currency or explicit conversion. |
| `adjustment_proposal.rationale` | text | Yes | Human review reason | Non-empty. |
| `adjustment_proposal.state` | string(20) | Yes | `draft`, `submitted`, `approved`, `rejected`, `applied` | Only valid event-backed transition. |
| `adjustment_proposal.version` | integer | Yes | Positive revision number | Increments for optimistic concurrency. |
| `adjustment_proposal.created_at` | UTC timestamp | Yes | Instant | Generated on creation; immutable. |

## Supporting entities

| Entity.field | Type | Required | Allowed values / units | Uniqueness and validation |
| --- | --- | --- | --- | --- |
| `employee_assignment.id` | string(32) | Yes | `ASN-...` | Primary key. |
| `employee_assignment.employee_id` | FK string | Yes | `employee.id` | Parent must exist. |
| `employee_assignment.role_id` | FK string | Yes | `role.id` | Parent must exist. |
| `employee_assignment.level_id` | FK string | Yes | `level.id` | Parent must exist. |
| `employee_assignment.location_id` | FK string | Yes | `location.id` | Parent must exist. |
| `employee_assignment.effective_from` | date | Yes | Inclusive date | No overlap for one employee. |
| `employee_assignment.effective_to` | date | No | Inclusive date | Null means currently open; otherwise >= start. |
| `employee_assignment.fte` | decimal(4,3) | Yes | Fraction of full-time, (0,1] | Database check constraint. |
| `fx_rate.id` | string(30) | Yes | `FX-<currency>-<year>` | Primary key. |
| `fx_rate.currency` | string(3) | Yes | ISO 4217 code | Unique with effective start; no overlapping ranges. |
| `fx_rate.usd_per_unit` | decimal(16,8) | Yes | USD per one unit of source currency | Positive. |
| `fx_rate.effective_from` | date | Yes | Inclusive date | No overlap for currency. |
| `fx_rate.effective_to` | date | Yes | Inclusive date | >= effective start. |
| `analysis_run.id` | string(40) | Yes | `RUN-...` | Primary key; includes as-of date and ruleset. |
| `analysis_run.as_of` | date | Yes | Comparison date | Source data used must be effective on/before date. |
| `analysis_run.ruleset` | string(30) | Yes | Versioned rule ID | Non-empty. |
| `analysis_run.created_at` | UTC timestamp | Yes | Instant | Fixed in generated data for reproducibility. |
| `comparison_result.id` | string(50) | Yes | `CMP-...` | Primary key; one employee per run. |
| `comparison_result.run_id` | FK string | Yes | `analysis_run.id` | Parent must exist. |
| `comparison_result.employee_id` | FK string | Yes | `employee.id` | Parent must exist. |
| `comparison_result.salary_id` | FK string | Yes | `salary_record.id` | Employee and date must match comparison. |
| `comparison_result.band_id` | FK string | No | `compensation_band.id` | Null only for missing/ambiguous effective band. |
| `comparison_result.group_key` | string(80) | Yes | Role, level, location key | Derived from assignment. |
| `comparison_result.peer_count` | integer | Yes | Count of comparable employees | Non-negative; derived, not randomized. |
| `comparison_result.annual_fte` | decimal(14,2) | Yes | Annual FTE pay in salary currency | Derived from monthly pay and FTE. |
| `comparison_result.compa_ratio` | decimal(8,4) | No | Ratio to band midpoint | Null if no valid band; calculated from source amounts. |
| `comparison_result.band_position` | decimal(8,4) | No | Relative position in band | Null if no valid band; may be outside [0,1] for out-of-band pay. |
| `comparison_result.expected_annual` | decimal(14,2) | No | Annual FTE pay in band currency | Derived from ruleset and job factors. |
| `comparison_result.residual_pct` | decimal(8,4) | No | Fractional difference from expected pay | Derived; negative means below expectation. |
| `comparison_result.outcome` | string(40) | Yes | Review or exception code | Must match documented ruleset outcome. |
| `comparison_result.explanation` | text | Yes | Calculation rationale | Non-empty; preserves why result was produced. |
| `source_decision.id` | string(40) | Yes | `DEC-...` | Primary key. |
| `source_decision.employee_id` | FK string | Yes | `employee.id` | Parent must exist. |
| `source_decision.salary_id` | FK string | Yes | `salary_record.id` | Same employee. |
| `source_decision.reported_band_id` | FK string | No | `compensation_band.id` | May reference a real but expired band; engine checks effective date. |
| `source_decision.reported_fte` | decimal(4,3) | No | Fraction of full-time | Compared to effective assignment. |
| `source_decision.reported_fx` | decimal(16,8) | No | USD per currency unit | Missing value can be an input exception. |
| `source_decision.reported_group_key` | string(80) | No | Role, level, location key | Must match defensible comparable group or include rationale. |
| `source_decision.applied_proposal_id` | FK string | No | `adjustment_proposal.id` | Application requires an approved proposal event. |
| `source_decision.occurred_at` | UTC timestamp | Yes | Instant | Input-event time. |
| `proposal_event.id` | string(40) | Yes | `PEV-...` | Primary key. |
| `proposal_event.proposal_id` | FK string | Yes | `adjustment_proposal.id` | Parent must exist. |
| `proposal_event.prior_state` | string(20) | No | Proposal state | Null only for creation event. |
| `proposal_event.next_state` | string(20) | Yes | Proposal state | Must follow valid transition graph. |
| `proposal_event.actor` | string(80) | Yes | Authorized reviewer label | Non-empty. |
| `proposal_event.reason` | text | Yes | Decision rationale | Non-empty. |
| `proposal_event.occurred_at` | UTC timestamp | Yes | Instant | Append-only; chronological per proposal. |
| `audit_event.id` | string(40) | Yes | `AUD-...` | Primary key. |
| `audit_event.actor` | string(80) | Yes | Actor label | Non-empty. |
| `audit_event.action` | string(80) | Yes | Action code | Non-empty. |
| `audit_event.subject_id` | string(80) | Yes | Referenced business ID | Non-empty; ID may span entity types. |
| `audit_event.detail` | text | Yes | Reason or context | Avoid real personal information. |
| `audit_event.occurred_at` | UTC timestamp | Yes | Instant | Append-only. |

`source_decision` captures potentially flawed source decisions as raw facts; its failure labels are exported only in `ground_truth.csv`. `proposal_event` records every state transition with actor and reason. `audit_event` records sensitive reads and writes.

## Cardinality and state rules

- Role, level and location each have one-to-many relationships with assignments and bands. Employee has one-to-many assignments, salaries, evidence, tenure snapshots, promotions and proposals.
- A comparison belongs to one run and one employee; a run has many comparisons. A proposal belongs to one comparison and has many proposal events.
- Peer groups are derived from role, level, location and as-of period. If materialized, use a `peer_group_member` bridge for its many-to-many relationship to employees across runs.
- Proposal transitions: `draft -> submitted -> approved -> applied` or `submitted -> rejected`. Reject all other transitions, including `draft -> applied`.
- Date intervals are inclusive. Assignments and bands for the same logical key must not overlap. A promotion must point to adjacent valid assignments, and salary records must use valid parent IDs.

## Derived measures

`annual_fte = monthly_amount * 12 / assignment.fte`. Convert using the effective-dated FX rate only when comparing across currencies. `compa_ratio = annual_fte / band.midpoint`. `band_position = (annual_fte - band.minimum) / (band.maximum - band.minimum)`. These values, tenure, and rule-based ground-truth labels must be calculated from source records; they are never independently randomized.
