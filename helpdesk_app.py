"""OUAI /helpdesk Slack command -> Freshservice ticket.

Typing /helpdesk in Slack opens a form (Requester shown automatically, Subject,
Priority dropdown, Details). Submitting it creates a ticket in Freshservice.

Runs in Slack Socket Mode, so it needs no public URL, only a process that stays
running. See README.md for setup.
"""

import html
import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("helpdesk")

SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"]  # xoxb-...
SLACK_APP_TOKEN = os.environ["SLACK_APP_TOKEN"]  # xapp-... (connections:write)
FRESHSERVICE_DOMAIN = os.environ["FRESHSERVICE_DOMAIN"]  # e.g. theouai.freshservice.com
FRESHSERVICE_API_KEY = os.environ["FRESHSERVICE_API_KEY"]

# Freshservice priority IDs: 1 low, 2 medium, 3 high, 4 urgent
PRIORITIES = [("Low", "1"), ("Medium", "2"), ("High", "3"), ("Urgent", "4")]
FRESHSERVICE_SOURCE_SLACK = 10  # same source ID the existing Slack tickets use
FRESHSERVICE_STATUS_OPEN = 2

app = App(token=SLACK_BOT_TOKEN)


def _option(label, value):
    return {"text": {"type": "plain_text", "text": label}, "value": value}


def form_view(user_id):
    """The modal shown when someone types /helpdesk."""
    return {
        "type": "modal",
        "callback_id": "helpdesk_ticket",
        "private_metadata": user_id,
        "title": {"type": "plain_text", "text": "New IT ticket"},
        "submit": {"type": "plain_text", "text": "Submit"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                # Native Slack people picker: lists everyone in the workspace and is
                # searchable. Starts as the person who ran /helpdesk, but can be changed
                # to file a ticket on behalf of someone else.
                "type": "input",
                "block_id": "requester_block",
                "label": {"type": "plain_text", "text": "Requester"},
                "element": {
                    "type": "users_select",
                    "action_id": "requester",
                    "initial_user": user_id,
                    "placeholder": {"type": "plain_text", "text": "Select a person"},
                },
            },
            {
                "type": "input",
                "block_id": "subject_block",
                "label": {"type": "plain_text", "text": "Subject"},
                "element": {"type": "plain_text_input", "action_id": "subject"},
            },
            {
                "type": "input",
                "block_id": "priority_block",
                "label": {"type": "plain_text", "text": "Priority"},
                "element": {
                    "type": "static_select",
                    "action_id": "priority",
                    "initial_option": _option("Medium", "2"),
                    "options": [_option(label, value) for label, value in PRIORITIES],
                },
            },
            {
                "type": "input",
                "block_id": "details_block",
                "label": {"type": "plain_text", "text": "Details"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "details",
                    "multiline": True,
                },
            },
        ],
    }


def message_view(text):
    """A simple modal with one message, used for progress and the result."""
    return {
        "type": "modal",
        "callback_id": "helpdesk_done",
        "title": {"type": "plain_text", "text": "New IT ticket"},
        "close": {"type": "plain_text", "text": "Close"},
        "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": text}}],
    }


def create_ticket(email, subject, details, priority):
    """Create the ticket in Freshservice and return its JSON."""
    response = requests.post(
        f"https://{FRESHSERVICE_DOMAIN}/api/v2/tickets",
        auth=(FRESHSERVICE_API_KEY, "X"),
        json={
            "email": email,
            "subject": subject,
            "description": html.escape(details).replace("\n", "<br>"),
            "priority": priority,
            "status": FRESHSERVICE_STATUS_OPEN,
            "source": FRESHSERVICE_SOURCE_SLACK,
        },
        timeout=20,
    )
    response.raise_for_status()
    return response.json()["ticket"]


@app.command("/helpdesk")
def open_form(ack, body, client):
    ack()
    client.views_open(trigger_id=body["trigger_id"], view=form_view(body["user_id"]))


class NoEmailError(Exception):
    """The selected Slack user has no email address (for example a bot)."""


def slack_person(client, slack_user_id):
    """Return (display name, email) for a Slack user. Email is None if missing."""
    profile = client.users_info(user=slack_user_id)["user"]["profile"]
    name = profile.get("real_name") or profile.get("display_name") or slack_user_id
    return name, profile.get("email")


@app.view("helpdesk_ticket")
def submit_form(ack, body, client, view):
    submitter_id = view["private_metadata"]  # the person who ran /helpdesk
    values = view["state"]["values"]
    requester_id = values["requester_block"]["requester"]["selected_user"]
    subject = values["subject_block"]["subject"]["value"].strip()
    priority = int(values["priority_block"]["priority"]["selected_option"]["value"])
    details = values["details_block"]["details"]["value"].strip()

    # Answer Slack right away (it only waits 3 seconds), then do the slow work.
    ack(response_action="update", view=message_view(":hourglass_flowing_sand: Creating your ticket..."))
    view_id = body["view"]["id"]

    try:
        requester_name, email = slack_person(client, requester_id)
        if not email:
            raise NoEmailError(requester_id)
        if submitter_id != requester_id:
            # Filed on someone else's behalf: record who actually submitted it.
            submitter_name, submitter_email = slack_person(client, submitter_id)
            details = (
                f"Submitted in Slack by {submitter_name} ({submitter_email or 'no email'}) "
                f"on behalf of {requester_name}.\n\n{details}"
            )
        ticket = create_ticket(email, subject, details, priority)
        ticket_id = ticket["id"]
        link = f"https://{FRESHSERVICE_DOMAIN}/support/tickets/{ticket_id}"
        client.views_update(
            view_id=view_id,
            view=message_view(
                f":white_check_mark: Ticket <{link}|#{ticket_id}> was created. "
                "IT will follow up by email."
            ),
        )
        log.info("Created ticket %s for %s", ticket_id, email)
    except NoEmailError:
        log.warning("Selected requester %s has no email in Slack", requester_id)
        client.views_update(
            view_id=view_id,
            view=message_view(
                ":warning: That person has no email address in Slack, so a ticket can't be "
                "created for them. Please pick someone else or email helpdesk@theouai.com."
            ),
        )
    except Exception:
        log.exception("Could not create ticket")
        client.views_update(
            view_id=view_id,
            view=message_view(
                ":warning: Sorry, the ticket could not be created. "
                "Please email helpdesk@theouai.com instead."
            ),
        )


def start_health_server():
    """Tiny web page so a hosting service that expects a web address (Render's free
    web service) sees the app as healthy. Only starts when the host sets PORT."""
    port = os.environ.get("PORT")
    if not port:
        return

    class Health(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"helpdesk app is running\n")

        def log_message(self, *args):  # keep the logs quiet
            pass

    server = HTTPServer(("0.0.0.0", int(port)), Health)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    log.info("Health page listening on port %s", port)


if __name__ == "__main__":
    start_health_server()
    SocketModeHandler(app, SLACK_APP_TOKEN).start()
