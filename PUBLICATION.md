# Public source preview

This repository contains experimental game/simulation source. The reachable Git history and source were reviewed for publication on 2026-10-29; no protected-data or credential blocker was identified. This is not a guarantee that every feature works or that the program is secure to deploy.

## Verification

Python syntax was checked without importing or running the game (30 current Python files). Gameplay, graphics, trained policies and dependency installation were not verified for this publication. Existing tests have not been run unless a separate validation section says otherwise.

This is a historical source snapshot. Prefer the maintained/canonical repository where available: https://github.com/MilliganCo/castle-ascii.

## Runtime boundaries

Review status: `not_safe_for_untrusted_network`.

- server/network.py:42 @dataclass with no hash is inserted into set at :137; first client fails.

- server/main.py:24 and run_server.bat:18 bind all interfaces; receive buffer/command queue lack bounds.

Run network prototypes only on a trusted local machine/LAN. They have not been reviewed for Internet exposure. Load only your own trusted pickle/model checkpoints; such files can execute code. Keep generated saves, models, credentials and personal data outside Git.
