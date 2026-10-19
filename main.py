import json
import os
import re
import sys
from pathlib import Path
from datetime import datetime, timezone

import requests

ACCOUNT = os.getenv("STEEM_ACCOUNT", "open-circle").strip().lower()
WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
API_URL = os.getenv("STEEM_API_URL", "https://api.steemit.com").strip()
STATE_PATH = Path("state.json")
HISTORY_LIMIT = 1000
TIMEOUT = 20


def rpc(method, params):
    response = requests.post(
        API_URL,
        json={"jsonrpc": "2.0", "method": method, "params": params, "id": 1},
        timeout=TIMEOUT,
        headers={"User-Agent": "OpenCircleApp/1.0"},
    )
    response.raise_for_status()
    data = response.json()
    if data.get("error"):
        raise RuntimeError(f"Steem API error for {method}: {data['error']}")
    return data.get("result")


def load_state():
    if not STATE_PATH.exists():
        return None
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def save_state(last_index):
    STATE_PATH.write_text(
        json.dumps({"last_index": int(last_index)}, indent=2) + "\n",
        encoding="utf-8",
    )


def strip_html_and_count_words(body):
    body = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", body or "")
    body = re.sub(r"(?s)<[^>]+>", " ", body)
    body = re.sub(r"!?\[[^\]]*\]\([^)]*\)", " ", body)
    body = re.sub(r"https?://\\S+", " ", body)
    return len(re.findall(r"\b[\w’'-]+\b", body, flags=re.UNICODE))


def discord_send(embed):
    if not WEBHOOK:
        raise RuntimeError("Missing DISCORD_WEBHOOK_URL secret.")
    payload = {
        "username": "Open Circle App",
        "embeds": [embed],
        "allowed_mentions": {"parse": []},
    }
    response = requests.post(WEBHOOK, json=payload, timeout=TIMEOUT)
    response.raise_for_status()


def process_vote(op_entry):
    op_index, entry = op_entry
    op_pair = entry.get("op", [None, {}])
    if not isinstance(op_pair, list) or len(op_pair) != 2 or op_pair[0] != "vote":
        return
    vote = op_pair[1]
    if vote.get("voter", "").lower() != ACCOUNT:
        return

    author = vote.get("author", "")
    permlink = vote.get("permlink", "")
    weight_raw = int(vote.get("weight", 0))
    vote_weight = weight_raw / 100.0
    timestamp = entry.get("timestamp") or "Unknown"
    post_url = f"https://steemit.com/@{author}/{permlink}"

    words = "Unavailable"
    try:
        content = rpc("condenser_api.get_content", [author, permlink])
        if content and content.get("author") == author:
            words = str(strip_html_and_count_words(content.get("body", "")))
    except Exception as exc:
        print(f"Warning: could not fetch post content for @{author}/{permlink}: {exc}")

    voting_power_label = "Unavailable"
    try:
        accounts = rpc("condenser_api.get_accounts", [[ACCOUNT]])
        if accounts:
            # This is the account's CURRENT voting power, not necessarily the value at vote time.
            current_vp = float(accounts[0].get("voting_power", 0)) / 100.0
            voting_power_label = f"{current_vp:.2f}% (current)"
    except Exception as exc:
        print(f"Warning: could not fetch current voting power: {exc}")

    embed = {
        "title": "Open Circle Vote Notification",
        "url": post_url,
        "description": f"@{ACCOUNT} cast a vote on a Steem post.",
        "color": 3447003,
        "fields": [
            {"name": "Platform", "value": "Steem", "inline": True},
            {"name": "Post Author", "value": f"@{author}", "inline": True},
            {"name": "Vote Weight", "value": f"{vote_weight:.2f}%", "inline": True},
            {"name": "Words", "value": words, "inline": True},
            {"name": "Voting Power", "value": voting_power_label, "inline": True},
            {"name": "Vote Time (UTC)", "value": str(timestamp), "inline": True},
            {"name": "History Operation", "value": str(op_index), "inline": True},
        ],
        "footer": {"text": "Open Circle App • Steem curation monitor"},
    }
    discord_send(embed)
    print(f"Sent notification for vote operation #{op_index}: @{author}/{permlink}")


def main():
    if not WEBHOOK:
        print("ERROR: Add DISCORD_WEBHOOK_URL as a GitHub Actions secret.", file=sys.stderr)
        sys.exit(2)

    history = rpc("condenser_api.get_account_history", [ACCOUNT, 100, HISTORY_LIMIT])
    if not isinstance(history, list) or not history:
        raise RuntimeError("Steem API returned no account history. Check the account/API endpoint.")

    # Condenser API entries are [operation_index, operation_data].
    history = sorted(history, key=lambda item: int(item[0]))
    latest_index = int(history[-1][0])
    state = load_state()

    if state is None or "last_index" not in state:
        save_state(latest_index)
        print(
            f"First run: saved baseline at operation #{latest_index}. "
            "No older votes were sent; new votes will be monitored on later runs."
        )
        return

    last_index = int(state["last_index"])
    new_entries = [item for item in history if int(item[0]) > last_index]

    if not new_entries and latest_index <= last_index:
        print(f"No new account operations. Last seen index: {last_index}")
        return

    # Process in chronological order. Only advance state after all new operations are handled.
    for item in new_entries:
        op_pair = item[1].get("op", [None, {}])
        if isinstance(op_pair, list) and len(op_pair) == 2 and op_pair[0] == "vote":
            process_vote(item)

    # If there was a gap larger than the returned history window, warn rather than silently claiming completeness.
    if last_index < int(history[0][0]) - 1:
        print(
            "WARNING: history gap detected. Some older operations may have fallen outside "
            f"the latest {HISTORY_LIMIT} operations. Consider increasing HISTORY_LIMIT."
        )

    save_state(max(last_index, latest_index))
    print(f"Updated last seen operation to #{max(last_index, latest_index)}")


if __name__ == "__main__":
    main()
