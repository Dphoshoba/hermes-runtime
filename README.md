# Hermes Runtime v0.1

Minimal, read-only EVOS governance validation runtime.

## One-shot validation

```bash
python3 -m hermes_v01 --repo /Users/david/EVOS --output-dir ./hermes-report
```

It writes `verification-report.json` and `verification-report.md`.

## Persistent supervisor

```bash
python3 -m hermes_v01.supervisor_cli \
  --repo /Users/david/EVOS \
  --output-dir ./hermes-report \
  --interval 60
```

Useful controls:

```bash
# Run exactly three cycles
python3 -m hermes_v01.supervisor_cli \
  --repo /Users/david/EVOS \
  --output-dir ./hermes-report \
  --interval 1 \
  --max-cycles 3

# Request a graceful stop
mkdir -p ./hermes-report && touch ./hermes-report/STOP
```

The supervisor persists `supervisor-state.json` atomically and writes each cycle beneath `hermes-report/cycles/`.

## Safety boundary

Hermes never modifies the inspected repository, approves governance, changes lifecycle state, or infers repository facts. Reports and supervisor state are written only beneath the configured output directory.

## Canonical runtime status

Project the supervisor's persisted state into a stable Program III runtime view:

```bash
python3 -m hermes_v01.status_cli \
  --supervisor-state ./hermes-report/supervisor-state.json \
  --milestone "Runtime State Manager" \
  --write-state ./hermes-report/runtime-state.json
```

The command prints JSON and returns exit code `2` when a concrete blocker is present.

## Work Queue Manager

`hermes_v01.work_queue` provides a deterministic, restart-safe Program III work queue.
It derives `READY`/`BLOCKED` state from explicit dependencies, prevents duplicate
or replayed dispatch, persists atomically, and keeps `VERIFIED` behind an explicit
independent-review method.

## Immutable execution evidence

Program III includes an Evidence Recorder that executes one command and publishes one immutable execution record. The recorder captures literal command data, UTC timestamps, the numeric process exit code, stdout and stderr files, supplied artifact paths, file digests, and the repository revision when Git metadata is available. It does not interpret a non-zero exit code as an evidence-integrity failure and never promotes independent-review state.

```bash
hermes-record \
  --evidence-dir "$HOME/.hermes/runtime/evidence" \
  --cwd /path/to/workspace \
  --repository /path/to/repository \
  --artifact /path/to/generated/artifact.json \
  -- python3 -m pytest -q
```

Each execution is stored beneath its unique execution ID:

```text
evidence/
└── exec-<UTC>-<random>/
    ├── execution-record.json
    ├── stdout.log
    └── stderr.log
```

Published evidence files are made read-only. A second publication to the same record path fails rather than overwriting the original evidence.

## Independent Reviewer

Review one immutable execution record without re-running the command or modifying its evidence:

```bash
hermes-review \
  --record "$HOME/.hermes/runtime/evidence/exec-.../execution-record.json" \
  --output-dir "$HOME/.hermes/runtime/reviews"
```

The reviewer validates the evidence schema, execution ID, timestamps, numeric exit code,
artifact existence, recorded sizes and SHA-256 hashes, execution-record digest, and repository
revision format when present. It publishes immutable `review.json` and `review.md` artifacts.
Outcomes are exactly `REVIEW_PASSED`, `REVIEW_FAILED`, or `REVIEW_INCOMPLETE`.
