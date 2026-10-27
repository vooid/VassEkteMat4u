"""Outgoing e-mail.

No mail is sent in this version. Messages go to a development outbox: they are logged and stored as
:OutboxMessage nodes, and shown at /dev/outbox when DEV_OUTBOX is on. Replace `send()` when a mail service is chosen
(Ekte Mat uses Google Workspace, docs/context/02_as_is_process_and_IT/current_IT_landscape.txt).
"""
import logging

from .repositories import outbox

log = logging.getLogger(__name__)


def send(recipient: str, subject: str, body: str) -> None:
    """Never raises: a failed e-mail must not undo the action that triggered it."""
    log.info("Outbox: %s", subject)
    try:
        outbox.add(recipient, subject, body)
    except Exception:
        log.exception("Could not store e-mail in the outbox")
