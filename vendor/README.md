# Vendored Newclid

`newclid/` is the unmodified `newclid` subproject of
https://github.com/Newclid/Newclid at commit
`ac6550732a950564cf7614d605b5bf1eadd29701` (version 3.0.1).
It includes the Python package, its packaging metadata, upstream tests and data.
`newclid.upstream.json` records every upstream Git blob hash and byte count.
Git attributes preserve the original bytes across Windows and Linux checkouts.
The upstream LICENSE and NOTICE.md remain intact. No authorship is transferred.

From the MORTRA repository root:

```sh
python -m pip install -r requirements-geometry-contracts.txt
python scripts/verify_vendored_newclid.py --output reports/newclid-origin.json
```

This changes the source of installation, not the mathematical algorithm.
NumPy, SymPy and the other upstream dependencies remain. Newclid's source is
supplied infrastructure and knowledge, not knowledge acquired by MORTRA.
The current exact solver does not enable Newclid/Yuclid deduction by vendoring it.
The optional Yuclid extra is not installed by these requirements.

The verifier checks the complete snapshot, the imported Python sources and
the installation origin. It rejects an old upstream installation even when its
source matches. `--allow-upstream-install` is only for a before/after diagnostic;
it reports but does not require local installation provenance.

Normal research tasks remain in MORTRA's frozen configurations. The upstream
test datasets are not injected into the normal solver or library acquisition.
Do not edit this snapshot to implement MORTRA-specific behavior. A future update
must separately record upstream identity, source changes and regression results.
