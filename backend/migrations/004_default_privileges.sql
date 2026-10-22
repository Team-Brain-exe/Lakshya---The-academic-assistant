-- ============================================================
-- Migration 004: Secure default privileges for new objects
--
-- Ensures that any NEW tables, sequences, or functions created in
-- the public schema after this point do NOT grant access to the
-- Supabase anon or authenticated roles by default.
--
-- Together with migration 002 (which enabled RLS and revoked
-- existing grants on current tables), this closes the gap where
-- default privileges could let anon/authenticated see rows in
-- newly created tables.
--
-- IMPORTANT: Every new table added to the public schema MUST
-- also run:  ALTER TABLE public.<new_table> ENABLE ROW LEVEL SECURITY;
-- ============================================================

-- Revoke defaults for the postgres role (always safe for this role)
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    REVOKE ALL ON TABLES FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    REVOKE ALL ON SEQUENCES FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    REVOKE ALL ON FUNCTIONS FROM anon, authenticated;

-- Revoke defaults for the supabase_admin role (guarded — may not
-- have privilege depending on the connected role)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'supabase_admin') THEN
        ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public
            REVOKE ALL ON TABLES FROM anon, authenticated;
        ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public
            REVOKE ALL ON SEQUENCES FROM anon, authenticated;
        ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public
            REVOKE ALL ON FUNCTIONS FROM anon, authenticated;
    END IF;
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'Insufficient privilege to alter default privileges for supabase_admin role; skipping.';
END $$;
