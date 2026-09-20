# Impact backend conventions

- SQLite, one local database, one shared SQLAlchemy Base and Session factory. Use app/db/engine.py for connections so foreign keys and transaction behavior are consistent.
- Models live in app/modules/<feature>/models.py and must be imported in app/db/models.py for migrations.
- Routers handle HTTP/access checks. Schemas define validated API input/output. Services implement business operations. Queries provide reusable reads.
- Services may flush but never commit. The outer route/workflow commits. Check-ins and pass consumption must share a transaction and protect against duplicates/concurrent spending.
- SQLite does not provide PostgreSQL row-level FOR UPDATE locks. Use conditional writes and constraints with explicit conflict handling.
- Use reviewed Alembic migrations, configured for batch operations. Do not edit applied migrations or assume expression indexes are reflected accurately.
- Multiple roles per account; NO permissions tables and NO access_level field. Centralize allowed-role checks in app/core/auth.py.
- SchoolProfile is generic affiliation, independent of account roles. Position text grants no access and is not proof of teaching eligibility.
- Person owns photo_path. Public profile reads join Person; do not duplicate the photo field in school_profiles.
- Never accept roles in signup/account-creation payloads. Role grants/removals require admin. Self/assigned-class operations also require ownership/assignment checks.
- Authentication stub denies access. Replace only with verified sessions/tokens, never an unverified account ID.
- Keep public/private response schemas separate. Never expose password hashes/private contacts in public profiles.
- Preserve person IDs when adding accounts. Do not match/claim identities by unverified email.
- Regenerate contracts/openapi.json using python -m scripts.export_openapi. Never hand-edit generated contracts or frontend types.
- Keep SQLite/WAL files, backups, uploads and secrets out of Git. Use the backup script rather than copying a running WAL database file.
- Test meaningful integrity, authorization and workflow behavior. Add future modules only as implemented; avoid unnecessary abstractions and external services.
