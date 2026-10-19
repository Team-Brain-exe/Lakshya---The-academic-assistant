-- Lock the tables away from Supabase's public REST API (PostgREST).
-- Our FastAPI backend connects directly as the postgres role, which bypasses RLS,
-- so nothing in the app changes. Anyone using the public anon key gets nothing.
-- Safe to re-run. Run it again after adding new tables (or add the table to a migration).

DO $$
DECLARE t text;
BEGIN
    FOR t IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);
    END LOOP;

    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON ALL TABLES IN SCHEMA public FROM anon;
        REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL ON ALL TABLES IN SCHEMA public FROM authenticated;
        REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM authenticated;
    END IF;
END $$;
