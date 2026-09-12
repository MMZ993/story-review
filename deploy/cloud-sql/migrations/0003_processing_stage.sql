-- Item F live progress: advisory marker of the pipeline step currently
-- executing for a session's in-flight flow-1/2/3 request. Written and
-- cleared by the running flow; null for every session at rest. Not part
-- of SessionRecord (live view state, not durable truth).
alter table sessions
    add column if not exists processing_stage text
    check (processing_stage is null or processing_stage in
        ('reviewing', 'synthesizing', 'facilitator', 'delegating', 'finalizing'));
