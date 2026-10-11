"""Supabase sign-in errors: a misconfigured key is the server's problem, a refused code the user's."""

import httpx
import pytest

from app.core import supabase_auth


def test_an_invalid_supabase_key_is_a_server_problem_not_a_bad_sign_in():
    response = httpx.Response(401, json={"message": "Invalid API key"})
    with pytest.raises(supabase_auth.SupabaseNotConfiguredError):
        supabase_auth.session_from(response)


def test_a_refused_code_is_still_a_bad_sign_in():
    response = httpx.Response(400, json={"error": "invalid_grant"})
    with pytest.raises(supabase_auth.InvalidGrantError):
        supabase_auth.session_from(response)
