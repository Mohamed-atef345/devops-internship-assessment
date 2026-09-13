# Evidence and submission index

- Repository URL: https://github.com/Mohamed-atef345/devops-internship-assessment
- Final commit:
- Matching CI run:
- Continuous 12-18 minute video URL:
- Challenge receipt ID:
- Starting video commit:
- Later documentation-only commits, if any:

For each requirement, link: file/output -> commit -> video timestamp.
Match the final README, diagram, GitHub code and video (three instances, public port 8090).

## Evidence collected before the video

| Requirement | File/output | Commit | Video timestamp | Status |
|---|---|---|---|---|
| Bounded full-stack validation with PASS/FAIL and non-zero failure | [`validate.py`](../validate.py) and troubleshooting Entry 8 | `test: add bounded full-stack validation` | Pending | Verified locally in the two-app/port-8080 state |
| Validate all endpoints and real PostgreSQL/Redis operations | Healthy run recorded in troubleshooting Entry 8 | `test: add bounded full-stack validation` | Pending | Passed; created/retrieved a record and incremented Redis 15 to 16 |
| Prove every configured backend responds | `validate.py` configured-service discovery and `/instance` loop | `test: add bounded full-stack validation` | Pending | Passed for `app-01` and `app-02` |
| Verify prohibited host ports and network isolation | `validate.py` Docker port/network inspection | `test: add bounded full-stack validation` | Pending | Passed for the required pre-video topology |
| Measure availability while one backend is stopped | [`failure_test.sh`](../failure_test.sh) and troubleshooting Entry 9 | `test: add backend failure and recovery proof` | Pending | Passed with 20 successes, zero failures, and `app-02` observed |
| Restore the stopped backend and prove reintegration | `failure_test.sh` bounded recovery loop and troubleshooting Entry 9 | `test: add backend failure and recovery proof` | Pending | Passed; recovered `app-01` served public traffic |
| Create a real PostgreSQL logical backup | [`backup.sh`](../backup.sh) and troubleshooting Entry 10 | `feat: add postgres backup and restore workflow` | Pending | Passed; non-empty 2.1 KiB ignored SQL dump created |
| Restore the PostgreSQL backup and prove recovery | [`restore.sh`](../restore.sh) and troubleshooting Entry 10 | `feat: add postgres backup and restore workflow` | Pending | Passed; pre-backup record present and post-backup record absent |
| Run CI on push and pull request through full-stack validation | [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) and troubleshooting Entry 11 | `ci: add full-stack workflow and image scan` | Pending | Workflow complete; successful GitHub Actions run pending |
| Scan the built application image for HIGH/CRITICAL vulnerabilities | Trivy step in [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) and security Finding 10 | `ci: add full-stack workflow and image scan` | Pending | Optional scan configured; successful scan evidence pending |

Replace each pending field only with the real commit, CI link, or video timestamp after it exists. The final video must repeat validation after the live three-app/port-8090 change.
