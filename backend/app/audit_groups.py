"""The audit trail's action groups (specs/features/admin-only-pages.md): what an admin filters by.

Every action the backend and the listener write, in one of six groups; an action not listed here (one
added later, or a legacy row) is shown under OTHER rather than hidden.
"""

from enum import StrEnum


class ActionGroup(StrEnum):
    SENDING = "sending"
    DRAFTING = "drafting"
    PRIVACY = "privacy"
    MAILBOX = "mailbox"
    SETTINGS = "settings"
    ADMIN = "admin"
    OTHER = "other"


_GROUPS: dict[ActionGroup, tuple[str, ...]] = {
    ActionGroup.SENDING: (
        "approve_and_send", "follow_up_sent", "send_outcome_unknown", "send_reconciled", "send_scheduled",
        "scheduled_send_cancelled", "compose_sent", "compose_send_outcome_unknown", "compose_outcome_settled",
        "holding_reply_scheduled", "holding_reply_cancelled", "holding_reply_sent", "holding_reply_outcome_unknown",
        "store_sent_message",
    ),
    ActionGroup.DRAFTING: (
        "generate_draft", "refine_draft", "translate_email", "template_used", "compose_written", "compose_refined",
        "compose_deleted",
    ),
    ActionGroup.PRIVACY: (
        "store_message", "quarantine_message", "remask_message", "drop_attachment_text", "read_attachment",
        "ocr_attachment", "skip_cloud_ocr", "fetch_message", "confirm_sender", "private_mode", "scan_reading",
    ),
    ActionGroup.MAILBOX: (
        "start_mailbox", "stop_mailbox", "setup_watch", "renew_watch", "fetch_history", "ingest_abandoned",
        "ingest_skipped", "import_inbox", "disconnect_gmail", "email_snoozed", "email_dismissed", "waiting_dismissed",
    ),
    ActionGroup.SETTINGS: (
        "quiet_hours", "todo_settings", "holding_reply_settings", "writing_style_description", "writing_style_learning",
        "writing_style_example_added", "writing_style_deleted_example", "writing_style_hid_habit",
        "writing_style_deleted", "template_saved", "template_deleted", "document_deleted", "delete_account",
    ),
    ActionGroup.ADMIN: ("admin_sign_in",),
}
_GROUP_OF: dict[str, ActionGroup] = {action: group for group, actions in _GROUPS.items() for action in actions}


def group_of(action: str) -> ActionGroup:
    return _GROUP_OF.get(action, ActionGroup.OTHER)


def actions_in(group: ActionGroup) -> list[str]:
    """The actions a group filters to; OTHER is every action not in a named group (see known_actions)."""
    return list(_GROUPS.get(group, ()))


def known_actions() -> list[str]:
    return list(_GROUP_OF)
