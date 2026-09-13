# Evidence and submission index

- Repository URL: https://github.com/Mohamed-atef345/devops-internship-assessment
- Final implementation/evidence commit: [`6dcc0f9`](https://github.com/Mohamed-atef345/devops-internship-assessment/commit/6dcc0f9036b83fa284ddb5e60b64022aaa79850c)
- Matching CI run: [run 34779348679](https://github.com/Mohamed-atef345/devops-internship-assessment/actions/runs/34779348679) - passed
- Continuous video URL: [Google Drive recording](https://drive.google.com/file/d/1ZL6gZt2dGmtx_k22hOOTwhABO-RUpAr2/view?usp=sharing) (approximately 19 minutes)
- Challenge receipt ID: `f061e5604de9443a9f19148f2ce60bb6`
- Starting video commit: [`fad818d`](https://github.com/Mohamed-atef345/devops-internship-assessment/commit/fad818d536b51a55869598622b86ece6d4383181)
- Later documentation-only commit: `docs: add final video evidence` (this timestamp/link update)

For each requirement, link: file/output -> commit -> video timestamp.
Match the final README, diagram, GitHub code and video (three instances, public port 8090).

## Requirement evidence

| Requirement | File/output | Commit | Video timestamp | Status |
|---|---|---|---|---|
| Bounded full-stack validation with PASS/FAIL and non-zero failure | [`validate.py`](../validate.py) and troubleshooting Entry 8 | `45bab6b` | [06:52-08:05](https://drive.google.com/file/d/1ZL6gZt2dGmtx_k22hOOTwhABO-RUpAr2/view?usp=sharing) | Verified in the two-app/port-8080 state |
| Validate all endpoints and real PostgreSQL/Redis operations | Healthy run recorded in troubleshooting Entry 8 | `45bab6b` | [01:43-04:15](https://drive.google.com/file/d/1ZL6gZt2dGmtx_k22hOOTwhABO-RUpAr2/view?usp=sharing) | Passed; real record and counter operations shown |
| Prove every configured backend responds | `validate.py` configured-service discovery and `/instance` loop | `45bab6b` | [03:45-04:15](https://drive.google.com/file/d/1ZL6gZt2dGmtx_k22hOOTwhABO-RUpAr2/view?usp=sharing) | Both initial backends observed |
| Verify prohibited host ports and network isolation | `validate.py` Docker port/network inspection | `45bab6b` | [06:52-08:05](https://drive.google.com/file/d/1ZL6gZt2dGmtx_k22hOOTwhABO-RUpAr2/view?usp=sharing) | Required pre-video topology passed |
| Measure availability while one backend is stopped | [`failure_test.sh`](../failure_test.sh) and troubleshooting Entry 9 | `c6aa413` | [04:15-05:32](https://drive.google.com/file/d/1ZL6gZt2dGmtx_k22hOOTwhABO-RUpAr2/view?usp=sharing) | 20 successes, zero failures, and `app-02` observed |
| Restore the stopped backend and prove reintegration | `failure_test.sh` bounded recovery loop and troubleshooting Entry 9 | `c6aa413` | [04:15-05:32](https://drive.google.com/file/d/1ZL6gZt2dGmtx_k22hOOTwhABO-RUpAr2/view?usp=sharing) | Recovered `app-01` served public traffic |
| Create a real PostgreSQL logical backup | [`backup.sh`](../backup.sh) and troubleshooting Entry 10 | `d4992e7` | Not shown | Passed before video; non-empty ignored SQL dump created |
| Restore the PostgreSQL backup and prove recovery | [`restore.sh`](../restore.sh) and troubleshooting Entry 10 | `d4992e7` | Not shown | Passed before video; snapshot state restored |
| Run CI through full-stack validation | [`.github/workflows/ci.yml`](../.github/workflows/ci.yml), troubleshooting Entries 11-12, and [final successful run](https://github.com/Mohamed-atef345/devops-internship-assessment/actions/runs/34779348679) | `e751d08`; final `6dcc0f9` | Not shown | Final three-app/port-8090 pipeline passed |
| Scan the built application image for HIGH/CRITICAL vulnerabilities | Trivy step, security Finding 10, and [final successful run](https://github.com/Mohamed-atef345/devops-internship-assessment/actions/runs/34779348679) | `e751d08`; fix `527f486` | Not shown | Blocking Trivy scan passed in the final pipeline |
| Document final request flow, networks, storage, health relationships, and remaining single points of failure | [`architecture.png`](../architecture.png) and [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) | `bddd495` | Not shown | Final three-app/port-8090 target documented |
| Analyze and correlate all three historical logs | [`scripts/analyze_logs.py`](../scripts/analyze_logs.py), [`log_analysis.md`](../log_analysis.md), and troubleshooting Entry 14 | `6327405` | [08:00-09:00](https://drive.google.com/file/d/1ZL6gZt2dGmtx_k22hOOTwhABO-RUpAr2/view?usp=sharing) | Correlated finding and deduplication method demonstrated |

## Supplemental screenshot evidence

| Requirement | File/output | Commit | Video timestamp | Status |
|---|---|---|---|---|
| Preserve the one-time challenge receipt | [`challenge-receipt.png`](evidence/challenge-receipt.png) and receipt ID above | `6dcc0f9` | [09:14](https://drive.google.com/file/d/1ZL6gZt2dGmtx_k22hOOTwhABO-RUpAr2/view?usp=sharing) | Challenge status `applied`; screenshot is supplemental evidence |
| Prove final three-app/port-8090 build and validation | [`app03-build-completion.png`](evidence/app03-build-completion.png) and [`final-three-app-validation.png`](evidence/final-three-app-validation.png) | live change `de9444d`; NGINX/evidence fix `6dcc0f9` | Not shown before recording ended | Corrected build completed; all checks passed and all three backends were observed; supplemental only |
| Show `app-03` in the NGINX pool | [`nginx-app03-upstream.png`](evidence/nginx-app03-upstream.png) | `6dcc0f9` | Not shown before recording ended | Final configuration screenshot; supplemental only |

The final live-change commit `de9444d` failed CI at full-stack validation because `app-03` was
not yet in the NGINX pool. Commit `6dcc0f9` added the missing upstream; its complete CI run,
including validation and Trivy, passed. The post-recording screenshots are supplemental and do
not replace actions missing from the continuous video.
