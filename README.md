# MORTRA

MORTRA is a mathematics research and product system built around one principle:

> One structure. Many representations.

The current engineering goal is concrete: improve the certified solve rate on fixed benchmarks without increasing false positives.

## Core path

```text
Natural language / TeX / MathML
  -> Discourse IR / Problem IR
  -> Semantic Kernel
  -> MORTRA-owned CAS, proof, and geometry backends
  -> certificates
  -> Proof Scene / Visual IR
```

The active problem-generation path is `/api/mathos-generate`. When a structure is not yet executable, it may enqueue a `mathos_discovery` job for the external-LLM-free worker.

## Explicit non-dependencies

- DeepSeek is not used by the current system.
- AlphaGeometry or AlphaGeometry2 is not used as a runtime or proof backend.
- AlphaGeometry papers influenced some design ideas, such as finite vocabularies and auxiliary-construction search, but no AlphaGeometry code or DDAR engine is part of MORTRA.

Do not infer production usage from historical commits, deleted experiments, or research notes. The current runtime graph and reproducible tests are authoritative.

## Local setup

```bash
cp .env.local.example .env.local
npm install
npm run dev
```

Required application variables:

- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_KEY` for server-side migration or administration only

Optional publishing variables:

- `X_API_KEY`
- `X_API_SECRET`
- `X_ACCESS_TOKEN`
- `X_ACCESS_TOKEN_SECRET`

## Worker

```bash
cd worker
npm ci
pip install -r requirements.txt
npm test
npm run build
```

Runtime variables:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `JOB_ID` for one-shot GitHub Actions execution
- `POLL_INTERVAL_MS` for a persistent worker

## Engineering rule

A result may be called certified only when its declared verifier has run successfully. Numerical support, a concrete verified instance, and a general proof are recorded as different statuses.
