# Backup & Restore Guide

**Version:** 1.0.0
**Status:** Active

---

## Overview

Horror Story Generator 데이터의 통합 백업/복구 시스템입니다.
Bash 스크립트로 구현되어 Python 의존성 없이 독립적으로 실행됩니다.

---

## Quick Start

### 전체 백업

```bash
# 기본 백업 (압축 없음)
./scripts/backup.sh

# 압축 백업 (권장)
./scripts/backup.sh --compress
```

### 복구

```bash
# 전체 복구
./scripts/restore.sh backups/backup_20260118_120000.tar.gz

# 미리보기 (dry-run)
./scripts/restore.sh backups/backup_20260118_120000.tar.gz --dry-run
```

---

## Scripts

### 파일 구조

```
scripts/
├── backup_config.sh   # 공통 설정 및 유틸리티 함수
├── backup.sh          # 백업 실행 스크립트
├── restore.sh         # 복구 실행 스크립트
└── verify_backup.sh   # 백업/복구 검증 스크립트
```

---

## backup.sh

### 사용법

```bash
./scripts/backup.sh [OPTIONS]
```

### 옵션

| 옵션 | 설명 |
|------|------|
| `--all` | 전체 백업 (기본값) |
| `--story-registry` | Story Registry DB만 백업 |
| `--research` | Research 데이터만 백업 (DB + FAISS + cards) |
| `--stories` | 생성된 스토리만 백업 |
| `--story-vectors` | Story 벡터 인덱스만 백업 |
| `--seeds` | Seed 데이터만 백업 |
| `--output <path>` | 출력 디렉토리 지정 (기본: ./backups) |
| `--compress` | tar.gz 압축 생성 |
| `--dry-run` | 실제 백업 없이 미리보기 |
| `--verbose` | 상세 출력 |

### 예시

```bash
# 전체 백업 (압축)
./scripts/backup.sh --compress

# Story Registry만 백업
./scripts/backup.sh --story-registry

# Research와 Stories만 백업
./scripts/backup.sh --research --stories --compress

# 다른 경로에 백업
./scripts/backup.sh --output /mnt/backup --compress

# 미리보기
./scripts/backup.sh --dry-run
```

### 출력 예시

```
========================================
Horror Story Generator Backup
========================================
[INFO] Project root: /path/to/project
[INFO] Output directory: ./backups
[INFO] Components: story-registry research stories
[INFO] Compress: true

[STEP] Backing up: story-registry (52K)
[SUCCESS] Backed up: story-registry
[STEP] Backing up: research (564K)
[SUCCESS] Backed up: research
[STEP] Backing up: stories (52K)
[SUCCESS] Backed up: stories

[STEP] Creating manifest...
[SUCCESS] Manifest created

[STEP] Creating compressed archive...
[SUCCESS] Archive created: backups/backup_20260118_120000.tar.gz
[INFO] Checksum: sha256:abc123...

========================================
Backup Complete
========================================

[INFO] Summary:
  ✓ story-registry (52K)
  ✓ research (564K)
  ✓ stories (52K)
```

---

## restore.sh

### 사용법

```bash
./scripts/restore.sh <backup_file> [OPTIONS]
```

### 옵션

| 옵션 | 설명 |
|------|------|
| `--dry-run` | 실제 복구 없이 미리보기 |
| `--force` | 확인 없이 덮어쓰기 |
| `--component <name>` | 특정 컴포넌트만 복구 |
| `--verbose` | 상세 출력 |

### 예시

```bash
# 전체 복구
./scripts/restore.sh backups/backup_20260118_120000.tar.gz

# 미리보기
./scripts/restore.sh backups/backup_20260118_120000.tar.gz --dry-run

# 확인 없이 강제 복구
./scripts/restore.sh backups/backup_20260118_120000.tar.gz --force

# Story Registry만 복구
./scripts/restore.sh backups/backup_20260118_120000.tar.gz --component story-registry
```

### 복구 프로세스

1. 백업 아카이브 압축 해제 (tar.gz인 경우)
2. manifest.json 읽기 및 정보 표시
3. 기존 데이터 충돌 확인
4. 사용자 확인 (--force가 아닌 경우)
5. 기존 데이터를 `.pre_restore.{timestamp}` 형식으로 백업
6. 백업에서 데이터 복원
7. 결과 요약 표시

### 출력 예시

```
========================================
Horror Story Generator Restore
========================================
[INFO] Backup file: backups/backup_20260118_120000.tar.gz

[STEP] Extracting backup archive...
[INFO] Backup Version: 1.0.0
[INFO] Created At: 2026-01-18T12:00:00Z
[INFO] App Version: 1.4.3

[INFO] Components in backup:
  - story-registry: 1 files, 53248 bytes
  - research: 97 files, 577536 bytes
  - stories: 6 files, 53248 bytes

[INFO] Components to restore: story-registry research stories

[INFO] Checking for existing data...
  ⚠ story-registry exists (52K) - will be overwritten
  ⚠ research exists (564K) - will be overwritten

Existing data will be overwritten. Continue? [y/N] y

[STEP] Restoring: story-registry (52K)
[INFO] Current data backed up to: data/story_registry.db.pre_restore.20260118_130000
[SUCCESS] Restored: story-registry

========================================
Restore Complete
========================================
```

---

## verify_backup.sh

백업/복구 기능의 무결성을 검증하는 스크립트입니다.

### 사용법

```bash
./scripts/verify_backup.sh [OPTIONS]
```

### 옵션

| 옵션 | 설명 |
|------|------|
| `--test-dir <path>` | 테스트 파일 디렉토리 (기본: 임시 디렉토리) |
| `--no-cleanup` | 테스트 후 파일 유지 |
| `--verbose` | 상세 출력 |

### 수행 테스트

| # | 테스트 | 설명 |
|---|--------|------|
| 1 | Backup Creation | 백업 파일 생성 확인 |
| 2 | Archive Integrity | SHA256 체크섬 검증 |
| 3 | Manifest Validation | manifest.json 형식 검증 |
| 4 | Restore Dry-Run | 복구 미리보기 테스트 |
| 5 | Data Integrity | 파일 수/체크섬 비교 |
| 6 | SQLite Integrity | DB PRAGMA integrity_check |
| 7 | Schema Validation | DB 테이블/컬럼 스키마 검증 |
| 8 | Research Card JSON | 연구 카드 JSON 구조 검증 |
| 9 | Story Metadata JSON | 스토리 메타데이터 JSON 검증 |
| 10 | Story File Pairs | .md와 _metadata.json 쌍 검증 |
| 11 | FAISS Consistency | FAISS 인덱스/메타데이터 일관성 |
| 12 | Cross-References | 스토리↔연구 카드 참조 검증 |
| 13 | Full Restore Cycle | 전체 복구 사이클 테스트 |

### 출력 예시

```
========================================
Backup/Restore Verification
========================================
[INFO] Test directory: /tmp/xxx
[INFO] Cleanup after tests: true

[STEP] Test 1: Backup Creation
[INFO] Backup created: /tmp/xxx/backup_test/backup_xxx.tar.gz
[SUCCESS] PASSED: Backup Creation

[STEP] Test 2: Archive Integrity
[INFO] Checksum verified: abc123...
[SUCCESS] PASSED: Archive Integrity

...

[STEP] Test 7: Schema Validation
[INFO] story_registry: 'stories' table exists
[INFO] story_registry: 'meta' table exists
[INFO] story_registry: schema version = 1.1.0
[SUCCESS] PASSED: Schema Validation

[STEP] Test 11: FAISS Consistency
[INFO] FAISS dimension: 768
[INFO] FAISS mappings consistent: 28 entries
[SUCCESS] PASSED: FAISS Consistency

...

========================================
Test Results
========================================

[INFO] Total: 13 tests
[SUCCESS] Passed: 13
```

---

## 백업 대상

| 컴포넌트 | 경로 | 설명 |
|----------|------|------|
| `story-registry` | `data/story_registry.db` | 스토리 메타데이터 DB |
| `research` | `data/research/` | Research DB, FAISS 인덱스, 카드 파일 |
| `stories` | `data/novel/` | 생성된 스토리 (.md, .json) |
| `story-vectors` | `data/story_vectors/` | 스토리 벡터 인덱스 |
| `seeds` | `data/seeds/` | 시드 데이터 |

---

## 백업 파일 구조

### 디렉토리 백업

```
backup_20260118_120000/
├── manifest.json
├── story_registry.db
├── research/
│   ├── registry.sqlite
│   ├── vectors/
│   │   ├── research.faiss
│   │   └── metadata.json
│   └── 2026/
│       └── *.json
├── novel/
│   ├── horror_story_*.md
│   └── horror_story_*_metadata.json
└── seeds/
    └── seed_registry.sqlite
```

### 압축 백업

```
backup_20260118_120000.tar.gz
backup_20260118_120000.tar.gz.sha256
```

---

## manifest.json

백업 메타데이터를 담은 JSON 파일입니다.

```json
{
  "backup_version": "1.0.0",
  "created_at": "2026-01-18T12:00:00Z",
  "app_version": "1.4.3",
  "components": {
    "story-registry": {
      "files": 1,
      "size_bytes": 53248
    },
    "research": {
      "files": 97,
      "size_bytes": 577536
    },
    "stories": {
      "files": 6,
      "size_bytes": 53248
    }
  },
  "checksum": "sha256:abc123..."
}
```

| 필드 | 설명 |
|------|------|
| `backup_version` | 백업 스크립트 버전 |
| `created_at` | 백업 생성 시간 (UTC) |
| `app_version` | 앱 버전 (pyproject.toml에서) |
| `components` | 컴포넌트별 파일 수와 크기 |
| `checksum` | 무결성 검증용 체크섬 |

---

## 운영 권장사항

### 정기 백업 스케줄

```bash
# crontab 예시: 매일 새벽 3시 압축 백업
0 3 * * * cd /path/to/project && ./scripts/backup.sh --compress
```

### 백업 전 권장사항

| 시점 | 이유 |
|------|------|
| 대규모 배치 실행 전 | 롤백 가능성 확보 |
| 버전 업그레이드 전 | 스키마 변경 대비 |
| 주간 정기 백업 | 장기 보존 |

### 백업 보존 정책

```bash
# 30일 이상 된 백업 삭제
find backups/ -name "backup_*.tar.gz" -mtime +30 -delete
find backups/ -name "backup_*.tar.gz.sha256" -mtime +30 -delete
```

### 복구 후 확인사항

1. 애플리케이션 정상 실행 확인
2. Story Registry 쿼리 테스트
3. Research 카드 조회 확인
4. API 헬스체크 (`GET /health`)

---

## 문제 해결

### 백업 실패

| 증상 | 원인 | 해결 |
|------|------|------|
| "No data found to backup" | 데이터 디렉토리 비어있음 | 데이터 존재 확인 |
| Permission denied | 권한 부족 | `chmod +x scripts/*.sh` |
| Disk space error | 디스크 공간 부족 | 공간 확보 후 재시도 |

### 복구 실패

| 증상 | 원인 | 해결 |
|------|------|------|
| "Backup file not found" | 잘못된 경로 | 파일 경로 확인 |
| "Failed to extract" | 손상된 아카이브 | 체크섬 확인 |
| Component not found | 해당 컴포넌트가 백업에 없음 | manifest.json 확인 |

### 체크섬 검증

```bash
# 백업 체크섬 확인
cat backups/backup_20260118_120000.tar.gz.sha256

# 수동 검증
shasum -a 256 backups/backup_20260118_120000.tar.gz
```

---

## 호환성

| 환경 | 지원 |
|------|------|
| macOS | ✅ |
| Linux | ✅ |
| Windows (WSL) | ✅ |
| Windows (Git Bash) | ⚠️ 일부 제한 |

### 의존성

- bash 4.0+
- tar
- gzip
- jq (선택사항 - manifest 보기 향상)
- sha256sum 또는 shasum

---

## 관련 문서

- [Registry Backup Guide](./REGISTRY_BACKUP_GUIDE.md) - Story Registry 자동 백업
- [Architecture](../core/ARCHITECTURE.md) - 시스템 아키텍처
- [API Reference](../core/API.md) - API 문서
