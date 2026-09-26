# V2 failure follow-up: read-only trace audit

This package contains an actually executed audit of one published failure case,
not a new policy experiment and not a rerun of the 8-seed integration.

Source run: corcondor/mortra GitHub Actions 36273640831.
Executed-code commit: 5f8b36744a29327928c87d6db888f2f045dbea79.
Results commit: 724220d29f02b79633b0ba43adf57242ad922cb9.
Source artifact ID: 10917048485.
Artifact SHA-256: 326e01cad269f56b84b6e075a47c3e87fa3068cac73a27f2d9098b5aa9ba30ea.

The script reads the original ZIP, verifies its hash, groups recorded actions,
checks trajectory continuity, audits the saved learned graph, and performs BFS
only on recorded edges. It never calls a simulator, a policy, or an oracle.
The diagnostic includes a union with random baseline trajectories solely to
show what those already-observed trajectories contain; it is not an authorised
training dataset and is not used in the proposed online experiment.

To reproduce:

```sh
python audit_saved_failure.py /path/to/v2_failure_79020004_virtual_original.zip result.json
```

`failure_audit.json` is the executed result. `CODEX_ONLINE_FEEDBACK.md` is a
proposed small next experiment, not implemented or executed by this package.
The original archive is distributed separately. No files in the user's GitHub
repository were written or modified during this audit.
