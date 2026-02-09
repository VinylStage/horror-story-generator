# Documentation Link Check Guide

**Last Updated:** 2026-02-09

---

## 로컬 링크 검증 방법

### 깨진 내부 링크 찾기

```bash
# Active 문서에서 깨진 .md 링크 찾기
cd docs/
for f in core/*.md technical/*.md task-scheduler/*.md data-model/*.md audit/*.md legal/*.md DOCUMENT_MAP.md; do
  [ -f "$f" ] || continue
  dir=$(dirname "$f")
  grep -oP '\]\(([^)#]+?\.md)' "$f" | sed 's/\](//' | while read -r link; do
    target="$dir/$link"
    [ -e "$target" ] || echo "BROKEN: $f → $link"
  done
done
```

### "job" 잔존 참조 확인 (archive 제외)

```bash
grep -ri "job" docs/core/ docs/technical/*.md docs/task-scheduler/ \
  README.md CONTRIBUTING.md | grep -v archive | grep -v "Legacy.*\/jobs"
```

### 삭제된 파일 참조 확인

```bash
# 아카이빙된 파일로의 참조 확인
grep -rn "REGISTRY_BACKUP_GUIDE\|AS_IS_TO_BE\|TRIGGER_API\|docs/verification/" \
  docs/core/ docs/technical/*.md docs/task-scheduler/ README.md
```

---

## 자동 검증 도구 (향후)

- [markdown-link-check](https://github.com/tcort/markdown-link-check) npm 패키지 권장
- CI 통합 가능: `find docs/ -name '*.md' -exec markdown-link-check {} \;`

---

## 마지막 검증일

| 일시 | 결과 | 이슈 |
|------|------|------|
| 2026-02-09 | PASS (0 broken) | #146 |
