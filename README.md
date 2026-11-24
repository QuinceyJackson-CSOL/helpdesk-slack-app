# /helpdesk: create Freshservice tickets from Slack

Typing `/helpdesk` opens a form with Requester (filled in automatically), Subject,
a Priority dropdown (Low, Medium, High, Urgent) and Details. Submitting it creates
a ticket in Freshservice and shows the ticket number in the same window.

It runs in Slack Socket Mode, so no public web address is needed. It does need a
machine or service where `python helpdesk_app.py` can stay running.

## 1. Slack app settings (Helpdesk app, OUAI workspace)

Open the Helpdesk app, then **App Manifest**, switch to JSON and replace the contents with:

```json
{
  "display_information": {
    "name": "Helpdesk",
    "description": "Create Freshservice tickets with /helpdesk"
  },
  "features": {
    "bot_user": { "display_name": "Helpdesk", "always_online": false },
    "slash_commands": [
      {
        "command": "/helpdesk",
        "description": "Create a Freshservice ticket",
        "should_escape": false
      }
    ]
  },
  "oauth_config": {
    "scopes": { "bot": ["commands", "users:read", "users:read.email"] }
  },
  "settings": {
    "interactivity": { "is_enabled": true },
    "org_deploy_enabled": false,
    "socket_mode_enabled": true,
    "token_rotation_enabled": false
  }
}
```

Save. This turns on Socket Mode and removes the Zapier web addresses. No new
permissions are requested, so no reinstall or admin approval should be needed.

Then **Basic Information > App-Level Tokens > Generate Token and Scopes**. Name it
`socket`, add the scope `connections:write`, generate it, and copy the `xapp-` token.

## 2. Freshservice

Profile picture (top right) > **Profile Settings** > copy your **API Key**.
Use a dedicated service account's key if one exists, so tickets are not tied to one person.

## 3. Run it

```
pip install -r requirements.txt
export SLACK_BOT_TOKEN=xoxb-...        # Slack app > Install App > Bot User OAuth Token
export SLACK_APP_TOKEN=xapp-...        # from step 1
export FRESHSERVICE_DOMAIN=theouai.freshservice.com
export FRESHSERVICE_API_KEY=...
python helpdesk_app.py
```

Keep the values in the host's secret store or a `.env` file that is not committed.

## 4. Clean up Zapier

Once `/helpdesk` works, turn off or delete the two draft/test Zaps ("OUAI Helpdesk:
Slack Ticket Form" and the untitled Catch Hook Zap), since they are no longer used.

## How it works

1. `/helpdesk` calls Slack's `views.open` instantly, so the form always opens in time.
2. On submit, the app looks up the person's Slack email and creates the ticket with
   that email as the requester, priority 1 to 4, status Open, source 10 (Slack).
3. The form window updates to show the ticket link, or an error asking them to email
   helpdesk@theouai.com.
