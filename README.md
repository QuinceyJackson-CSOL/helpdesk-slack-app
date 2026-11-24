# /helpdesk: create Freshservice tickets from Slack

Typing `/helpdesk` in Slack opens a pop-up form. Submitting it creates a ticket in Freshservice and shows the ticket number in the same window.

Form fields:
- Requester: a searchable dropdown of everyone in Slack. It starts as the person who ran the command, and can be changed to file a ticket on someone else's behalf. When it is someone else, the ticket description starts with "Submitted in Slack by X on behalf of Y."
- Subject
- Priority: Low, Medium, High, Urgent
- Details

## How it works

1. `/helpdesk` calls Slack's `views.open` right away, so the form always opens inside Slack's 3 second limit. (Zapier took 4 to 5 seconds, which is why it was replaced by this small app.)
2. On submit, the app looks up the requester's Slack email and creates the Freshservice ticket with that email as the requester, priority 1 to 4, status Open and source 10 (Slack).
3. The form window updates to show the ticket link, or a friendly error (for example if the chosen person has no email in Slack).

The app uses Slack Socket Mode. It opens its own connection to Slack, so it needs no public web address, only a process that stays running. It uses Slack's official `slack_bolt` toolkit and `requests`.

## Settings the app needs

Environment variables (never commit real values):
- SLACK_BOT_TOKEN: starts with xoxb-. Slack app, Install App page.
- SLACK_APP_TOKEN: starts with xapp-. Slack app, Basic Information, App-Level Tokens, scope connections:write.
- FRESHSERVICE_DOMAIN: theouai.freshservice.com
- FRESHSERVICE_API_KEY: Freshservice, Profile Settings. A service account's key is better if one exists.

Slack app (Helpdesk, OUAI workspace): Socket Mode on, Interactivity on, slash command /helpdesk, bot scopes commands, users:read and users:read.email.

## Run it on a computer (for testing)

```
pip install -r requirements.txt
export SLACK_BOT_TOKEN=...
export SLACK_APP_TOKEN=...
export FRESHSERVICE_DOMAIN=theouai.freshservice.com
export FRESHSERVICE_API_KEY=...
python helpdesk_app.py
```

## Where it runs now: Render (temporary)

For testing it runs as a free Render web service connected to this repository.
- Build command: `pip install -r requirements.txt`
- Start command: `python helpdesk_app.py`
- Python version comes from `.python-version` (3.12)
- The four settings above are entered in Render under Environment.
- Render's free plan needs a web address, so when Render sets a PORT the app also serves a tiny "helpdesk app is running" page. It does nothing when run locally.
- Limitation: a free Render service sleeps after about 15 minutes without web traffic. The first `/helpdesk` after a sleep can fail. Opening the service address in a browser wakes it in about a minute.

## Planned: move to AWS

Render is temporary. The app only needs an always-on machine with Python 3 and outbound internet access. No inbound ports are needed. Move the same four settings to the new host's secret store and run `python helpdesk_app.py`. The PORT health page can be ignored there.
