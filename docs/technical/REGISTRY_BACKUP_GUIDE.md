# 스토리 레지스트리 백업 가이드

**버전:** 1.1.0
**상태:** 운영 승인됨

---

## 개요

스토리 레지스트리 백업 메커니즘은 스키마 마이그레이션 전 데이터 손실을 방지합니다.

---

## 1. 백업 대상

| 항목 | 설명 |
|------|------|
| 파일 | `data/story_registry.db` (SQLite) |
| 테이블 | `stories`, `story_similarity_edges`, `meta` |
| 데이터 | 생성된 스토리 메타데이터, 중복 검사 이력 |

---

## 2. 백업 발생 시점

백업은 **스키마 마이그레이션이 필요할 때만** 자동으로 생성됩니다.

**조건:**
```
현재 스키마 버전 ≠ 코드의 SCHEMA_VERSION
```

**예시:**
- DB 버전: 1.0.0
- 코드 버전: 1.1.0
- → 백업 생성 후 마이그레이션 진행

**백업이 생성되지 않는 경우:**
- 신규 설치 (DB 파일 없음)
- 버전이 이미 일치함

---

## 3. 백업 파일 명명 규칙

```
{원본파일명}.backup.{이전버전}.{타임스탬프}.db
```

**예시:**
```
story_registry.backup.1.0.0.20260112_130012.db
```

| 구성요소 | 설명 |
|----------|------|
| `story_registry` | 원본 파일명 |
| `backup` | 백업 식별자 |
| `1.0.0` | 마이그레이션 이전 버전 |
| `20260112_130012` | 생성 시간 (YYYYMMDD_HHMMSS) |
| `.db` | SQLite 확장자 |

---

## 4. 백업 저장 위치

백업 파일은 **원본 DB와 동일한 디렉토리**에 저장됩니다.

```
data/
├── story_registry.db                          # 현재 DB
├── story_registry.backup.1.0.0.20260112_130012.db  # 백업
└── ...
```

---

## 5. 백업에서 복원하기

### 5.1 복원 전 확인

```bash
# 현재 DB 상태 확인
sqlite3 data/story_registry.db "SELECT value FROM meta WHERE key='schema_version';"

# 백업 파일 목록 확인
ls -la data/*.backup.*.db
```

### 5.2 복원 절차

```bash
# 1. 애플리케이션 중지
pkill -f "python main.py"

# 2. 현재 DB 백업 (선택사항)
cp data/story_registry.db data/story_registry.db.current

# 3. 백업에서 복원
cp data/story_registry.backup.1.0.0.20260112_130012.db data/story_registry.db

# 4. 복원 확인
sqlite3 data/story_registry.db "SELECT value FROM meta WHERE key='schema_version';"
# 출력: 1.0.0

# 5. 애플리케이션 재시작 (마이그레이션 자동 실행)
python main.py --max-stories 1
```

### 5.3 복원 후 확인

```bash
# 스키마 버전 확인
sqlite3 data/story_registry.db "SELECT value FROM meta WHERE key='schema_version';"

# 스토리 개수 확인
sqlite3 data/story_registry.db "SELECT COUNT(*) FROM stories;"

# 최근 스토리 확인
sqlite3 data/story_registry.db "SELECT id, title, created_at FROM stories ORDER BY created_at DESC LIMIT 5;"
```

---

## 6. 실패 시나리오

### 6.1 백업 실패

| 원인 | 동작 | 로그 |
|------|------|------|
| 디스크 공간 부족 | 경고 로그 후 마이그레이션 계속 | `[RegistryBackup] Backup failed: ...` |
| 권한 오류 | 경고 로그 후 마이그레이션 계속 | `[RegistryBackup] Backup failed: ...` |
| 파일 잠금 | 경고 로그 후 마이그레이션 계속 | `[RegistryBackup] Backup failed: ...` |

**안전 보장:**
- 백업 실패는 **마이그레이션을 차단하지 않음**
- 마이그레이션 자체는 `ALTER TABLE ADD COLUMN`만 사용 (비파괴적)
- 기존 데이터는 마이그레이션 중 수정되지 않음

### 6.2 마이그레이션 실패

| 원인 | 동작 |
|------|------|
| 컬럼 이미 존재 | 무시하고 계속 (idempotent) |
| 테이블 손상 | 예외 발생, 애플리케이션 중단 |

---

## 7. 운영 권장사항

### 수동 백업이 필요한 경우

| 시점 | 이유 |
|------|------|
| 대규모 배치 실행 전 | 롤백 가능성 확보 |
| 버전 업그레이드 전 | 예방적 백업 |
| 정기 백업 (주간) | 장기 보존 |

**수동 백업 명령:**
```bash
cp data/story_registry.db data/story_registry.manual.$(date +%Y%m%d_%H%M%S).db
```

### 백업을 건드리지 말아야 할 경우

| 상황 | 이유 |
|------|------|
| 마이그레이션 진행 중 | 데이터 불일치 위험 |
| 애플리케이션 실행 중 백업 삭제 | 복구 불가 |
| 백업 파일 직접 수정 | 무결성 훼손 |

### 백업 보존 정책 (권장)

```bash
# 30일 이상 된 백업 삭제 (선택사항)
find data/ -name "*.backup.*.db" -mtime +30 -delete
```

---

## 8. 로그 확인

**정상 백업:**
```
[RegistryBackup] Backup created at data/story_registry.backup.1.0.0.20260112_130012.db
[Phase2C][CONTROL] 스키마 마이그레이션 완료: 1.0.0 -> 1.1.0
```

**백업 실패 (비차단):**
```
[RegistryBackup] Backup failed: [Errno 28] No space left on device
[Phase2C][CONTROL] 스키마 마이그레이션 완료: 1.0.0 -> 1.1.0
```

**마이그레이션 불필요:**
```
[Phase2C][CONTROL] 스키마 버전 확인: v1.1.0
```

---

## 코드 참조

| 파일 | 함수 | 설명 |
|------|------|------|
| `src/registry/story_registry.py:96-122` | `_backup_before_migration()` | 백업 생성 |
| `src/registry/story_registry.py:157-159` | `_init_db()` | 백업 호출 |

---

**Note:** 이 가이드는 v1.1.0 기준으로 작성되었습니다.
