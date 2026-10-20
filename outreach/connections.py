"""Official st.connection integration, with session-scoped HTTP transport only."""

import httpx
import streamlit as st
from streamlit.connections import BaseConnection

from outreach.services.config import Config
from outreach.services.supabase import Supabase


class SupabaseConnection(BaseConnection[httpx.Client]):
    @classmethod
    def scope(cls):
        return "session"

    def _connect(self, **kwargs) -> httpx.Client:
        # Construction does not make a network request. Never set a user's JWT
        # on this transport, or cache authenticated queries/authorization.
        return httpx.Client(timeout=20)

    def api(self, config: Config, token: str = "") -> Supabase:
        # Fresh wrapper for each run; the JWT is applied per request by Supabase.
        return Supabase(config, token, client=self._instance)

    def close(self) -> None:
        if self._raw_instance is not None:
            self._raw_instance.close()
            self._raw_instance = None

    def reset(self) -> None:
        self.close()
        super().reset()


def get_api(config: Config, token: str = "") -> Supabase:
    connection = st.connection("supabase", type=SupabaseConnection, ttl=600, max_entries=1)
    return connection.api(config, token)
