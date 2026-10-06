-- Row-level security on every application table, with no policies.
--
-- Supabase exposes public-schema tables through its REST API to anyone holding the project's
-- publishable (anon) key, and to any signed-in user's token, unless RLS is on. With it off, that
-- key alone read stored emails, the audit log and documents (verified 2026-10-04). No policy means
-- the anon and authenticated roles see nothing; the backend (postgres role) and the listener
-- (service_role key) bypass RLS, which is what they rely on.

ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE document ENABLE ROW LEVEL SECURITY;
ALTER TABLE chunk ENABLE ROW LEVEL SECURITY;
ALTER TABLE embedding ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_profile ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_preferences ENABLE ROW LEVEL SECURITY;
ALTER TABLE sender_rule ENABLE ROW LEVEL SECURITY;
ALTER TABLE keyword_rule ENABLE ROW LEVEL SECURITY;
