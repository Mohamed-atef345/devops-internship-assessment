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
| Run CI on push and pull request through full-stack validation | [`.github/workflows/ci.yml`](../.github/workflows/ci.yml), troubleshooting Entries 11-12, and [successful run #2](https://github.com/Mohamed-atef345/devops-internship-assessment/actions/runs/34765059184) | `e751d08`, fix `527f486` | Pending | Passed in 45 seconds; all required CI steps and cleanup succeeded |
| Scan the built application image for HIGH/CRITICAL vulnerabilities | Trivy step in [`.github/workflows/ci.yml`](../.github/workflows/ci.yml), security Finding 10, [failed run #1](https://github.com/Mohamed-atef345/devops-internship-assessment/actions/runs/34764720196), and [successful run #2](https://github.com/Mohamed-atef345/devops-internship-assessment/actions/runs/34765059184) | `e751d08`, fix `527f486` | Pending | Initial two HIGH PCRE2 findings remediated; blocking scan passed |
| Document final request flow, networks, storage, health relationships, and remaining single points of failure | [`architecture.png`](../architecture.png) and [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) | `docs: add final architecture diagram` | Pending | Final target documented; verify against the live three-app/port-8090 state in the video |
| Analyze and correlate all three historical logs | [`scripts/analyze_logs.py`](../scripts/analyze_logs.py), [`log_analysis.md`](../log_analysis.md), and troubleshooting Entry 14 | `docs: complete historical log analysis` | Pending | All ten questions answered with reproducible counts, timeline, and request-level evidence |

Replace each pending field only with the real commit, CI link, or video timestamp after it exists. The final video must repeat validation after the live three-app/port-8090 change.
