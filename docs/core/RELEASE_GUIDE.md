# develop → main 릴리즈 PR 가이드

## 0. main → develop 동기화 (선택사항)

### 필요한가?

| 상황 | 필요 여부 | 이유 |
|------|----------|------|
| CI 워크플로우 변경 | ❌ **불필요** | GitHub Actions는 **base branch (main)** 기준으로 실행됨 |
| 코드/로직 변경 | ⚠️ **권장** | 향후 머지 충돌 방지 |
| 장기간 미동기화 | ✅ **필요** | 브랜치 divergence 최소화 |

### 동기화 방법

```bash
# 방법 1: develop에서 main 머지 (이력 보존)
git checkout develop
git pull origin develop
git merge origin/main -m "chore: sync main to develop"
git push origin develop

# 방법 2: rebase (깔끔한 이력, 주의 필요)
git checkout develop
git pull origin develop
git rebase origin/main
git push origin develop --force-with-lease
```

---

## 1. 사전 확인

```bash
# develop 브랜치 최신화
git checkout develop && git pull origin develop

# main과의 차이 확인
git log main..develop --oneline

# 충돌 가능성 확인
git diff main...develop --stat
```

---

## 2. PR 생성

```bash
gh pr create --base main --head develop \
  --title "chore(release): sync develop to main" \
  --body "$(cat <<'EOF'
## Release Sync

develop 브랜치의 변경사항을 main으로 동기화합니다.

### 포함된 주요 변경사항
- (여기에 주요 변경사항 나열)

### Checklist
- [ ] 모든 CI 테스트 통과
- [ ] develop에서 충분한 검증 완료
EOF
)"
```

---

## 3. PR 검증 동작

| 검증 | 동작 |
|------|------|
| Issue Link 검증 | ✅ **건너뜀** (develop → main 예외 처리됨) |
| PR Title 검증 | 통과 필요 (`chore:`, `feat:` 등) |
| CI 테스트 | 통과 필요 |

---

## 4. 머지 후 Release Please 동작

```
develop → main 머지
       ↓
Release Please 실행
       ↓
feat:/fix: 커밋 있으면 → Release PR 자동 생성
       ↓
Release PR 머지 → 버전 태그 + GitHub Release 생성
```

---

## 5. 버전 범프 규칙

| 커밋 타입 | 버전 변화 | 예시 |
|----------|----------|------|
| `feat:` | MINOR (1.4.3 → 1.5.0) | 새 기능 추가 |
| `fix:` | PATCH (1.4.3 → 1.4.4) | 버그 수정 |
| `BREAKING CHANGE` | MAJOR (1.4.3 → 2.0.0) | 호환성 깨짐 |
| `ci:`, `docs:`, `chore:` | 변동 없음 | hidden: true |

---

## 6. 릴리즈 후 main → develop 동기화

릴리즈 완료 후 버전 파일들이 main에서 업데이트되므로 동기화 권장:

```bash
git checkout develop
git pull origin develop
git merge origin/main -m "chore: sync release v1.x.x to develop"
git push origin develop
```

---

## 요약 플로우

```
[develop 작업 완료]
       ↓
[develop → main PR 생성] ← Issue 링크 불필요
       ↓
[PR 머지]
       ↓
[Release Please → Release PR 생성]
       ↓
[Release PR 머지 → 버전 태그 생성]
       ↓
[main → develop 동기화] ← 권장
```
