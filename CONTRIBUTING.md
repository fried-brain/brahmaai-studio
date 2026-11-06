# Contributing to BrahmaAI Studio

Thanks for considering a contribution. This project is an early-stage architectural planning tool; correctness, transparent limitations, and safe handling of user layouts matter more than adding features quickly.

## Development setup

1. Install Python 3.11+ and Node.js 20+.
2. Follow the Docker and local-development instructions in `README.md`.
3. Install backend test dependencies with `cd backend && pip install -e '.[test]'`.
4. Run backend tests with `cd backend && pytest -q -o addopts=''`.
5. Run frontend unit tests with `cd frontend && node --test tests/*.test.mjs`.

## Change guidelines

- Keep dimensions in canonical millimetres in backend contracts and persisted geometry.
- Keep geometric calculations deterministic and covered by focused tests.
- Do not silently move, resize, delete, or apply a user's saved design.
- Treat optimization and clearance outputs as planning heuristics, not building-code or engineering certification.
- Preserve project ownership checks and CSRF protection on mutating authenticated endpoints.
- Add or update Alembic migrations for persistent schema changes; test upgrade and downgrade paths.
- Keep secrets out of source control. Update `.env.example` when adding configuration, using safe placeholders only.

## Pull requests

- Explain the user-visible behavior and relevant design constraints.
- Include focused tests for new behavior and regression tests for fixes.
- Document known limitations and any unverified runtime assumptions.
- Do not claim production readiness or code compliance without evidence.
