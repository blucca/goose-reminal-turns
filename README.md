# Goose completion hooks for Reminal

Report the end of a Goose turn to the Reminal terminal session running it.
A small Open Plugins package: Goose's `Stop` and `SessionEnd` events invoke
Reminal's existing `reminal hook done` command.

## Install

With `goose` and `reminal` on your shell's PATH:

```sh
goose plugin install https://github.com/blucca/goose-reminal-turns.git
```

Start a new Goose session inside Reminal. Reminal receives the completed-turn
signal and the Goose conversation ID through the existing hook receiver.
Its screen/output detector continues to handle activity and questions.

To remove the plugin, delete its `~/.agents/plugins/reminal-turns/` directory
and start a new Goose session.

## Event scope

| Goose event | Reminal state |
| --- | --- |
| `Stop` | `done` |
| `SessionEnd` | `done` |

The plugin uses the current completion events. Explicit permission/question
notifications are being designed in [Goose #12007](https://github.com/aaif-goose/goose/issues/12007).
Reminal's current `working` hook takes precedence over a visible question until
its silence/expiry rules apply. This package preserves the existing activity
and waiting detector by subscribing to the completion events.

Reminal routes the signal using its enclosing session / `REMINAL_SESSION`.
Running Goose outside Reminal leaves the receiver idle. The hook runs as an
observation command; Reminal continues to own the attention state and terminal.

## Verification

Tested on Linux with **Goose 1.54.0** and **Reminal 3.16.9**.

```sh
python3 check.py --goose /path/to/goose --reminal /path/to/reminal \
  --work /path/to/workspace/temp/new-hook-check
```

Use a new work directory. The check starts a loopback-only deterministic
OpenAI-compatible response fixture, runs the real binaries with isolated homes,
and seeds a synthetic Reminal session with a `working` state:

| Run | State after the Goose turn | Goose conversation captured |
| --- | --- | --- |
| Baseline | `working` | false |
| Plugin installed | `done` | true |

This checks Goose plugin discovery, hook execution and Reminal's state receiver.
Terminal rendering and live permission pauses are the next consumer checks.

The completion-only choice follows Reminal's
[`resolveAttn` precedence](https://github.com/harshalgajjar/Reminal/blob/ed8f87b5522b0b10334cc2378f0992290bbff190/internal/client/attention_probe.go#L611-L669).
At that revision a fresh `working` hook is authoritative during a visible
question. An adapter adding start-of-turn hooks also needs the corresponding
waiting and resolution signals.

## Sources

- [Goose plugins](https://goose-docs.ai/docs/guides/context-engineering/plugins/)
- [Goose hooks](https://goose-docs.ai/docs/guides/context-engineering/hooks/)
- [Reminal](https://github.com/harshalgajjar/Reminal)

Built and reviewed by Codex / GPT-6 Astra, the autonomous engineering agent at
[Blucca](https://blucca.github.io/). MIT license covers this plugin and its check;
Goose and Reminal retain their own licenses.
