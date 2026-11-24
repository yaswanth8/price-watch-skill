# Scheduling price checks

One recurring job checks every watch on the dashboard. Set it up once, after the first watch, and reuse it.

## The job prompt

Whatever the scheduler, the scheduled prompt is the same, with the dashboard link filled in:

```
Run my price watch check: use the price-watch skill to re-compare the top stores for
every active product on my Price Watch dashboard (<dashboard URL>). Alert me about
new lows and hits, with the store and buy link. This is an unattended
run: do not place any order; at most prepare a cart and ask.
```

The "unattended" line matters: it reminds the run that nobody is there to say yes, so a buy-mode hit stops at the confirmation summary.

## Pick a scheduler

Use the first one this session has. Look for the tools with ToolSearch before deciding one is missing.

| Environment | Tool | Notes |
|---|---|---|
| Claude Code on the web / cloud sessions | `create_trigger` (claude-code-remote) | A cron routine. Each run is a fresh session, so the prompt must carry the dashboard URL. |
| Claude Code CLI or desktop, scheduled tasks available | `CronCreate`, or the app's scheduled tasks | Runs while the app or machine is on. |
| Claude Code session that stays open | `/loop 1d <prompt>` | Only while this session lives. Fine for "check every few hours today". |
| Claude.ai / Cowork with scheduled tasks | the scheduled-task tool or the Schedule button | Same prompt. |
| None of these | Tell the user | Give them the prompt and suggest saying "check my price watch" whenever they like, or setting a calendar reminder. |

## Frequency

| Watches want | Cron (user's local time) |
|---|---|
| every 6 hours | `0 9,15,21,3 * * *` |
| daily (default) | `0 9 * * *` |
| weekly | `0 9 * * 1` |

Use the fastest any active watch asks for. Pick a minute other than :00 when the scheduler allows (for example `17 9 * * *`) so runs don't all start at once. Tell the user the schedule in their own time zone ("daily at 9:17 AM"). If the time zone is unknown and the scheduler needs one, use UTC and say so in the reply rather than asking.

Don't check more often than every few hours. Prices rarely move faster, and frequent hits on a store can get the IP or account flagged as a bot.

## Changing or stopping

- Adding a watch: no change, unless it needs a faster frequency; then update the existing job rather than creating a second.
- Last watch paused or removed: offer to delete the job.
- Before creating a job, list existing ones (`list_triggers`, `CronList`) and reuse any that already runs the price watch check.
