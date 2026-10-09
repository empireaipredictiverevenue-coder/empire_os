"""Sovereign, read-only IMAP retrieval for the founder's own mail account.

Uses stdlib TLS IMAP. Never sends mail, modifies flags, issues STORE/EXPUNGE,
infers canonical buyer intent, or saves message content to runtime storage.
Provider UID is scoped to mailbox UIDVALIDITY and must not be treated as a
verified cross-system conversation or commercial contact identity.
"""
from __future__ import annotations

from datetime import timezone
from email import policy
from email.parser import BytesParser
from email.utils import parsedate_to_datetime
import imaplib
import os
import re
import ssl
from typing import Any, Callable


FOLDER_PATTERN = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._/ -]{0,63}$')
ID_PATTERN = re.compile(r'^imap:(inbox|sent):([0-9]{1,20}):([0-9]{1,20})$')
MAX_LIST = 50
MAX_BYTES = 32768
MAX_BODY = 8000


class MailboxReadUnavailable(RuntimeError):
    """No credentials, recipient details or remote error content in errors."""


class OwnedIMAPMailboxProvider:
    """Bounded preview of own professional inbox and sent folder; no writes."""
    provider = 'owned_imap'
    suppression_evidence_complete = False

    def __init__(self, *, host: str | None = None, username: str | None = None,
                 password: str | None = None, port: int | None = None,
                 inbox_folder: str | None = None, sent_folder: str | None = None,
                 client_factory: Callable[..., Any] | None = None):
        self.host = (host if host is not None else os.getenv('EMPIRE_FOUNDER_IMAP_HOST', '')).strip()
        self.username = (username if username is not None else os.getenv('EMPIRE_FOUNDER_IMAP_USER', '')).strip()
        self._password = password if password is not None else os.getenv('EMPIRE_FOUNDER_IMAP_PASSWORD', '')
        try:
            self.port = int(port if port is not None else os.getenv('EMPIRE_FOUNDER_IMAP_PORT', '993'))
        except (ValueError, TypeError):
            self.port = 0
        self.inbox_folder = (inbox_folder if inbox_folder is not None else os.getenv('EMPIRE_FOUNDER_IMAP_INBOX', 'INBOX'))
        self.sent_folder = (sent_folder if sent_folder is not None else os.getenv('EMPIRE_FOUNDER_IMAP_SENT', 'Sent'))
        self._client_factory = client_factory

    @property
    def configured(self) -> bool:
        return (bool(self.host and self.username and self._password)
                and bool(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]{1,253}', self.host))
                and 1 <= self.port <= 65535
                and all(isinstance(folder, str) and FOLDER_PATTERN.fullmatch(folder)
                        for folder in (self.inbox_folder, self.sent_folder)))

    def _session(self):
        if not self.configured:
            raise MailboxReadUnavailable('OWN_IMAP_CONFIGURATION_INCOMPLETE')
        connection = None
        try:
            factory = self._client_factory or imaplib.IMAP4_SSL
            connection = factory(self.host, self.port, ssl_context=ssl.create_default_context(), timeout=8)
            connection.login(self.username, self._password)
            return connection
        except Exception:
            if connection is not None:
                try:
                    connection.logout()
                except Exception:
                    pass
            raise MailboxReadUnavailable('OWN_IMAP_TLS_AUTH_UNAVAILABLE') from None

    @staticmethod
    def _uidvalidity(connection) -> str:
        try:
            state, raw = connection.response('UIDVALIDITY')
            value = raw[0] if state == 'UIDVALIDITY' and raw else None
            valid = value.decode('ascii') if isinstance(value, bytes) else str(value or '')
        except Exception:
            valid = ''
        if not valid.isdigit() or not 1 <= len(valid) <= 20:
            raise MailboxReadUnavailable('OWN_IMAP_UIDVALIDITY_MISSING')
        return valid

    @staticmethod
    def _extract(raw: Any, *, identity: str, direction: str) -> dict[str, Any]:
        try:
            parsed = BytesParser(policy=policy.default).parsebytes(raw)
            plain = parsed.get_body(preferencelist=('plain',)) if parsed.is_multipart() else parsed
            body = ''
            if plain is not None and plain.get_content_type() == 'text/plain':
                value = plain.get_content()
                if isinstance(value, str):
                    body = value[:MAX_BODY]
            time = None
            if parsed.get('Date'):
                try:
                    stamp = parsedate_to_datetime(str(parsed['Date']))
                    if stamp.tzinfo is not None:
                        time = stamp.astimezone(timezone.utc).isoformat()
                except (TypeError, ValueError, OverflowError):
                    pass
            return {
                'id': identity,
                'message_id': str(parsed.get('Message-ID') or '').strip() or None,
                'from': str(parsed.get('From') or ''),
                'to': [str(v) for v in parsed.get_all('To', [])],
                'reply_to': [str(v) for v in parsed.get_all('Reply-To', [])],
                'subject': str(parsed.get('Subject') or ''),
                'text': body,
                'received_at': time if direction == 'inbox' else None,
                'created_at': time if direction == 'sent' else None,
                'status': 'sent' if direction == 'sent' else 'received',
                'last_event': 'sent' if direction == 'sent' else 'received',
                'provider': 'owned_imap',
                'canonical_contact_identity_verified': False,
                'canonical_thread_identity_verified': False,
            }
        except Exception:
            raise MailboxReadUnavailable('OWN_IMAP_MESSAGE_PARSE_FAILED') from None

    def _fetch(self, connection, *, folder_role: str, validity: str, uid: str):
        if not uid.isdigit() or not 1 <= len(uid) <= 20:
            raise MailboxReadUnavailable('OWN_IMAP_INVALID_UID')
        # BODY.PEEK with partial fetch must not change SEEN flags. No attachments
        # downloaded beyond the bounded first message bytes.
        try:
            state, data = connection.uid('FETCH', uid, f'(BODY.PEEK[]<0.{MAX_BYTES}>)')
            if state != 'OK' or not isinstance(data, list):
                raise ValueError('invalid_fetch')
            raw_parts = [item[1] for item in data
                         if isinstance(item, tuple) and len(item) == 2
                         and isinstance(item[1], bytes)]
            if len(raw_parts) != 1 or len(raw_parts[0]) > MAX_BYTES:
                raise ValueError('invalid_fetch_parts')
        except Exception:
            raise MailboxReadUnavailable('OWN_IMAP_BOUNDED_FETCH_FAILED') from None
        identity = f'imap:{folder_role}:{validity}:{uid}'
        return self._extract(raw_parts[0], identity=identity, direction=folder_role)

    def _read(self, role: str, *, limit: int, only: str | None = None):
        if type(limit) is not int or not 1 <= limit <= MAX_LIST:
            raise MailboxReadUnavailable('OWN_IMAP_ROW_BOUND_INVALID')
        if role not in ('inbox', 'sent'):
            raise MailboxReadUnavailable('OWN_IMAP_INVALID_MAILBOX')
        folder = self.inbox_folder if role == 'inbox' else self.sent_folder
        connection = self._session()
        try:
            state, _ = connection.select('"'+folder+'"', readonly=True)
            if state != 'OK':
                raise MailboxReadUnavailable('OWN_IMAP_FOLDER_UNAVAILABLE')
            validity = self._uidvalidity(connection)
            if only is not None:
                match = ID_PATTERN.fullmatch(only)
                if match is None or match[1] != role or match[2] != validity:
                    raise MailboxReadUnavailable('OWN_IMAP_MESSAGE_ID_MISMATCH')
                uids = [match[3]]
            else:
                state, data = connection.uid('SEARCH', None, 'ALL')
                if state != 'OK' or not data or not isinstance(data[0], bytes) or len(data[0]) > 262144:
                    raise MailboxReadUnavailable('OWN_IMAP_SEARCH_UNAVAILABLE')
                uids = [uid.decode('ascii') for uid in data[0].split()[-limit:]][::-1]
            items = [self._fetch(connection, folder_role=role, validity=validity, uid=uid)
                     for uid in uids]
            return items
        except MailboxReadUnavailable:
            raise
        except Exception:
            raise MailboxReadUnavailable('OWN_IMAP_READ_UNAVAILABLE') from None
        finally:
            try:
                connection.logout()
            except Exception:
                pass

    def list_received(self, *, limit: int) -> list[dict[str, Any]]:
        return self._read('inbox', limit=min(limit, MAX_LIST))

    def list_sent(self, *, limit: int) -> list[dict[str, Any]]:
        return self._read('sent', limit=min(limit, MAX_LIST))

    def list_suppressions(self, *, limit: int) -> list[dict[str, Any]]:
        # IMAP does not prove canonical opt-out/suppression coverage.
        return []

    def get_received(self, email_id: str) -> dict[str, Any]:
        rows = self._read('inbox', limit=1, only=email_id)
        if len(rows) != 1:
            raise MailboxReadUnavailable('OWN_IMAP_MESSAGE_NOT_FOUND')
        return rows[0]

    def get_sent(self, email_id: str) -> dict[str, Any]:
        rows = self._read('sent', limit=1, only=email_id)
        if len(rows) != 1:
            raise MailboxReadUnavailable('OWN_IMAP_MESSAGE_NOT_FOUND')
        return rows[0]

    def readiness(self) -> dict[str, Any]:
        return {'provider': self.provider, 'configured': self.configured,
                'read_only': True, 'tls_required': True,
                'canonical_identity_verified': False,
                'suppression_evidence_complete': False,
                'execution_authority': 'none'}
