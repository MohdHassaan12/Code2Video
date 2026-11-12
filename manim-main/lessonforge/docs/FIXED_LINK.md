# A link that keeps its address

`scripts/public_link.sh` starts a Cloudflare quick tunnel, whose address changes every time it starts (a restart,
a reboot, a link that stopped answering). A **named tunnel** keeps one address for good, costs nothing, and the
server stays on this machine with its GPUs, voices and the improver. The other way, the same server on Render, is in
[`DEPLOY_RENDER.md`](DEPLOY_RENDER.md) (paid, about 27.50 USD a month).

## What you need

- A domain on your Cloudflare account (the free plan is enough), for example `example.com`.
- `cloudflared` on this machine (already there for the quick tunnel).

## Set it up (once)

```bash
cd lessonforge
bash scripts/fixed_link_setup.sh lessons.example.com
bash scripts/public_link.sh --new
```

The first command opens a Cloudflare sign-in page once (on a machine with no browser, open the printed link on
any other device), creates the tunnel `lessonforge`, points `lessons.example.com` at it, writes its own config to
`<workspace>/tunnel/config.yml`, and adds `LESSONFORGE_TUNNEL_CONFIG` and `LESSONFORGE_PUBLIC_URL` to `.env`. The
second replaces the running quick tunnel with the named one. From then on the link is always
`https://lessons.example.com/app/?token=<access token>`.

## After that

`public_link.sh` works as before (`--restart` still refuses while a lesson is being made), but its link no longer
changes, and `--new` restarts the tunnel without giving it a new address. To go back to quick tunnels, delete the two
lines from `.env`.

The machine's own `cloudflared` service (`/etc/cloudflared`) is a different tunnel: the setup and the link script
use their own config file and never read or change it.
