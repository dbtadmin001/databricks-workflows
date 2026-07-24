# Verified Data Sources — Chess.com Grandmaster and User Analytics

## Source decision

**Default executable source:** Chess.com Published Data API

This is the cleanest no-key public API project. Conditional GET handling is a central acceptance criterion.

## Verified source registry

| Source | Status | Documentation or endpoint | Authentication | Intended use | Constraints and decision |
|---|---|---|---|---|---|
| Chess.com Published Data API (PubAPI) | PRIMARY_EXECUTABLE | `https://support.chess.com/en/articles/9650547-what-is-the-pubapi-and-how-do-i-use-it` | No authentication | Player profiles, titled players, monthly game archives, PGN, tournaments, clubs and leaderboards. | Use ETag and Last-Modified conditional requests, a descriptive User-Agent, bounded concurrency and 429 backoff. |
| Monthly PGN archives | PRIMARY_EXECUTABLE | `https://api.chess.com/pub/player/{username}/games/{YYYY}/{MM}/pgn` | No authentication | Bulk monthly game retrieval for parsing and large-scale analytics. | Store raw PGN before parsing; checksum and WAP-gate publication. |
| Deterministic local fixtures | MANDATORY_FALLBACK | `tests/fixtures/05_chess_grandmaster/` | None | Offline ETag, PGN parsing, SCD2 and WAP tests. | Include unchanged ETag, changed archive, malformed PGN and profile-history cases. |

## Environment and secret references

- `CHESS_USER_AGENT` — store the value locally in an ignored `.env` or in an approved secret manager/GitHub Environment; never commit it.
- `CHESS_CONTACT_EMAIL` — store the value locally in an ignored `.env` or in an approved secret manager/GitHub Environment; never commit it.

The configuration stores only variable names or secret references. Values must be supplied through local ignored environment files, Databricks secret facilities, cloud secret managers, or GitHub Environments.

## Required implementation files

The project implementation must create:

- `config/sources.yml` with `fixture`, `dev_live`, and optional paid/approved profiles;
- `src/<project_package>/sources/` with one adapter per enabled source;
- `tests/fixtures/` containing deterministic responses;
- `tests/contract/` validating response-to-Bronze contracts;
- `artifacts/source-probes/` for redacted connectivity evidence;
- `SOURCE_PROBE.md` documenting the exact non-destructive probe command and expected result.

## Executable source acceptance criteria

1. The fixture profile runs without internet access or secrets.
2. The live development profile fails clearly when a required variable is absent.
3. A non-destructive source probe receives a valid response and stores only redacted metadata.
4. Retries honor `429` and transient failures with bounded exponential backoff.
5. Raw responses are retained in Bronze or a landing volume with source timestamp, ingestion timestamp, request/run ID, endpoint identifier, and response checksum.
6. Source-specific schema drift is detected before promotion to Silver.
7. CI never calls paid or rate-limited live sources by default.
8. Terms, licensing, authentication and availability limitations are documented before enabling a source.

## Source switching contract

```yaml
source:
  profile: fixture          # fixture | dev_live | approved_paid
  provider: chess_com_published_data_api
  enabled: true
  request_timeout_seconds: 20
  max_retries: 3
  cache_raw_response: true
```

A provider may be switched through configuration only when its adapter implements the same project-level Bronze contract. Provider-specific fields must remain in the raw payload or namespaced metadata until explicitly mapped.
