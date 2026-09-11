-- D19 issue catalog: turns record the facilitator-minted issue
-- descriptors stamped with the turn (catalog source at finalize).
alter table turns
    add column if not exists new_issues jsonb not null default '[]'::jsonb;
