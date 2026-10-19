# Open Circle App — Steem vote notifications for Discord

This starter app monitors outgoing `vote` operations by the Steem account `@open-circle` and sends Discord embed notifications.

## Included
- Vote weight from the Steem `vote` operation
- Post author and link
- Approximate word count from the post body
- Account voting power at notification time, clearly labelled **current** (not historical vote-time power)
- Operation timestamp reported by the Steem account history API
- Duplicate prevention through `state.json`
- GitHub Actions schedule every 5 minutes (best-effort; GitHub may delay scheduled runs)

## Setup

1. Create a Discord text channel, for example `#open-circle-notifications`.
2. In that channel's settings, open **Integrations → Webhooks → New Webhook**.
3. Name it `Open Circle App`, select the channel, and copy the webhook URL. Treat it like a password.
4. Create a GitHub repository named `open-circle-app`. Upload these files and folders, keeping `.github/workflows/monitor.yml` in place.
5. In the repository, go to **Settings → Secrets and variables → Actions → New repository secret**.
   - Name: `DISCORD_WEBHOOK_URL`
   - Secret: paste the Discord webhook URL
6. Ensure Actions are enabled for the repository. Under **Settings → Actions → General**, allow workflows to read and write repository contents. The workflow commits `state.json` to prevent duplicate notifications.
7. Run **Actions → Open Circle App → Run workflow** once manually.
8. The first run records the current operation index as a baseline and does not send historical votes. This prevents a flood of old notifications.
9. After that, new votes by `@open-circle` should trigger notifications on later runs. Use **Actions → Open Circle App** to inspect logs.

## Important limitations
- GitHub scheduled workflows are best-effort, not real-time. They can be delayed, and public-repository schedules may be disabled after 60 days without repository activity.
- The monitor fetches the latest 1,000 account-history operations. If the account performs more than 1,000 operations between successful checks, some events could be missed.
- Word count is approximate and based on visible text after removing HTML/Markdown links.
- The displayed voting power is the account's current voting power when the script runs, not a historical snapshot at the exact vote time.
- A vote can be edited or removed later; this starter sends a notification when it sees a `vote` operation.
- Do not commit the Discord webhook URL, bot tokens, or other secrets.
- This app only reads public Steem data and sends Discord messages. It does not cast votes or require your Steem private keys.

## Troubleshooting
- `Missing DISCORD_WEBHOOK_URL`: add the repository secret with the exact name above.
- `403` when pushing `state.json`: enable read/write workflow permissions in repository settings.
- No notification on first run: expected; first run creates a baseline.
- API errors: check the GitHub Actions run log. You can try setting `STEEM_API_URL` to another trusted Steem API endpoint in the workflow environment.

## API reference
- Steem Condenser API: https://developers.steem.io/apidefinitions/condenser-api
- Discord Webhooks: https://support.discord.com/hc/en-us/articles/228383668-Intro-to-Webhooks
- GitHub Actions schedule: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
