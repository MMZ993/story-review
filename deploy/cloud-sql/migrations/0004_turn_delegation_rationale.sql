-- Item G / D21: the pre-delegation facilitator reply of a delegated
-- turn (audit material; not shown to the PO — facilitator_reply stays
-- the final post-delegation summary reply).
alter table turns
    add column if not exists delegation_rationale_reply text;
