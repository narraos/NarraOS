# NarraOS

**Autonomous AI Media Operating System.**

NarraOS researches, generates, edits, packages, publishes, and continuously
improves digital content through modular AI agents. YouTube is the first
supported platform; the architecture is platform-agnostic by design.

This is **not** a YouTube automation script. See `AI_CONTEXT.md` for the
required reading order across the full architecture, and
`PROJECT_ARCHITECTURE.md` for the system design.

## Status

Architecture approved for Core Infrastructure. See
`ARCHITECTURE_APPROVAL_CERTIFICATE.md` and `CURRENT_STATE.md` for the
authoritative current status -- do not rely on this README for that.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

Install the optional `media` extra (FAISS, Whisper, ffmpeg, MoviePy, OpenCV)
only when working on media-generation stages:

```bash
pip install -e ".[dev,media]"
```

## Documentation

Every architecture document lives at the repository root and under `docs/`.
Start with `AI_CONTEXT.md`.

## License

Apache License
