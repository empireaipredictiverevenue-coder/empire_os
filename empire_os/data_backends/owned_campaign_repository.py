"""Dedicated, bounded EmpireDB intake transport; no generic runtime fallback."""
import os

from empire_os.data_backends.postgres import PostgresConnectionConfig, PostgresConnector


class OwnedCampaignRepository:
    def __init__(self, connector):
        self.connector = connector

    @classmethod
    def from_environment(cls):
        if os.environ.get('EMPIRE_DATA_BACKEND') != 'empiredb':
            raise RuntimeError('canonical backend unavailable')
        dsn = os.environ.get('EMPIRE_OWNED_CAMPAIGN_DSN', '')
        return cls(PostgresConnector(PostgresConnectionConfig(
            dsn=dsn, application_name='empire-owned-campaign-intake', statement_timeout_ms=3000)))

    def _record(self, kind, payload):
        # Function identifiers are constants; all browser values are parameters.
        query = {'event': 'SELECT public.record_owned_campaign_event(%s::jsonb)',
                 'enquiry': 'SELECT public.record_owned_campaign_enquiry(%s::jsonb)'}[kind]
        import json
        conn = self.connector._open_connection()
        try:
            conn.execute('SET LOCAL ROLE empire_owned_campaign_ingest')
            role = conn.execute('SELECT current_user').fetchone()[0]
            if role != 'empire_owned_campaign_ingest':
                raise RuntimeError('dedicated intake role required')
            receipt = conn.execute(query, (json.dumps(payload),)).fetchone()[0]
            conn.commit()
            return str(receipt)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def event(self, payload):
        return self._record('event', payload)

    def enquiry(self, payload):
        return self._record('enquiry', payload)
