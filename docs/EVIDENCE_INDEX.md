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

Replace each pending field only with the real commit, CI link, or video timestamp after it exists. The final video must repeat validation after the live three-app/port-8090 change.
