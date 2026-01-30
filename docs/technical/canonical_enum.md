# Canonical Enum 정의서 (Horror Template System)

> **Version:** v1.6.0 <!-- x-release-please-version -->

**Enum Version:** 1.0
**Status:** FROZEN (value additions only, semantic changes forbidden)

**Purpose:**

호러 템플릿의 **정체성(identity)**을 기계적으로 정의하여

- 중복 템플릿 생성을 방지하고
    
- 의미 단위의 변주만 허용하며
    
- 장기적으로 확장 가능한 자동 생성 시스템을 구축하기 위함
    

---

## **1. Canonical Key란 무엇인가?**

  

**Canonical Key**는 다음 질문에 답하기 위한 구조다.

  

> “이 이야기는 **본질적으로 어떤 종류의 공포인가?**”

  

- 문체 ❌
    
- 소재의 세부 묘사 ❌
    
- 국가/이름 ❌
    

  

→ **공포가 작동하는 구조**만을 추출한다.

---

## **2. Canonical Key의 전체 구조**

  

Canonical Key는 **5개의 차원(dimension)**으로 구성된다.

```
[공간] + [핵심 공포] + [적대 원형] + [위협 작동 방식] + [결말 구조]
```

JSON 표현:

```
{
  "setting_archetype": "...",
  "primary_fear": "...",
  "antagonist_archetype": "...",
  "threat_mechanism": "...",
  "twist_family": "..."
}
```

---

## **3. Canonical Dimension별 정의**

---

## **3.1 setting_archetype (공간 원형)**

  

> **공포가 발생하는 ‘공간의 본질적 유형’**

|**값**|**설명**|
|---|---|
|apartment|공동 주거 공간. 소음, 감시, 계급 불안|
|hospital|의료 공간. 신체 통제, 생사 결정|
|rural|시골/외딴 지역. 고립, 전통, 숨겨진 역사|
|domestic_space|‘안전해야 할 집’. 가정의 배신|
|digital|온라인/가상 공간. 정체성 붕괴|
|liminal|전이 공간. 목적 없는 공간, 백룸|
|infrastructure|사회 기반시설. 붕괴/고립|
|body|인체 자체가 공간이 됨|
|abstract|명확한 물리 공간 없음|

📌 **규칙**

- 실제 지명 사용 금지
    
- 하나만 선택
    

---

## **3.2 primary_fear (핵심 공포)**

  

> **이야기가 궁극적으로 자극하는 단 하나의 공포**

|**값**|**의미**|
|---|---|
|loss_of_autonomy|내 몸/행동을 통제할 수 없음|
|identity_erasure|내가 ‘나’가 아님|
|social_displacement|사회에서 밀려남|
|contamination|더럽혀짐, 침식|
|isolation|완전한 고립|
|annihilation|존재 자체의 소멸|

📌 **규칙**

- 반드시 **하나만 선택**
    
- 모든 판정의 최우선 기준
    

---

## **3.3 antagonist_archetype (적대 원형)**

  

> **공포를 유발하는 ‘존재 또는 구조’의 유형**

|**값**|**설명**|
|---|---|
|ghost|전통적 초자연 존재|
|system|제도, 조직, 구조|
|technology|기술, AI, 기계|
|body|신체 내부의 위협|
|collective|군중, 공동체|
|unknown|정체 불명|

📌 **주의**

- 반드시 의인화할 필요 없음
    
- “사람”이 아닐 수 있음
    

---

## **3.4 threat_mechanism (위협 작동 방식)**

  

> **공포가 실제로 작동하는 메커니즘**

|**값**|**설명**|
|---|---|
|surveillance|감시, 노출|
|possession|빙의, 장악|
|debt|빚, 의무, 계약|
|infection|감염, 확산|
|impersonation|대체, 위장|
|confinement|물리/심리적 구속|
|erosion|점진적 붕괴|
|exploitation|착취, 수탈|

📌 **포인트**

- 점프스케어 ❌
    
- “무섭게 만드는 방식”이 아님
    
- **“공포가 지속되는 구조”**
    

---

## **3.5 twist_family (결말 구조 계열)**

  

> **이야기의 궁극적 반전/귀결 유형**

|**값**|**설명**|
|---|---|
|revelation|숨겨진 진실 드러남|
|inevitability|탈출 불가|
|inversion|역할/의미 뒤집힘|
|circularity|끝이 시작|
|self_is_monster|내가 가해자|
|ambiguity|해석 불가 결말|

📌 **규칙**

- 반전 유무와 무관
    
- 구조적 귀결 기준
    

---

## **4. Canonical Key 사용 예시**

  

### **예시 1: 한국 아파트 층간소음 호러**

```
{
  "setting_archetype": "apartment",
  "primary_fear": "social_displacement",
  "antagonist_archetype": "system",
  "threat_mechanism": "surveillance",
  "twist_family": "inevitability"
}
```

---

### **예시 2: 딥페이크 정체성 호러**

```
{
  "setting_archetype": "digital",
  "primary_fear": "identity_erasure",
  "antagonist_archetype": "technology",
  "threat_mechanism": "impersonation",
  "twist_family": "self_is_monster"
}
```

---

## **5. Canonical Key 운영 규칙 (중요)**

1. Canonical Key는 **생성 후 불변**
    
2. 동일 Canonical Key → **템플릿 중복**
    
3. 변주 허용은 Canonical이 아닌 **서브 요소**에서만
    
4. Canonical 변경 = **새 템플릿**
    

---

## **6. 관련 파일**

| 파일 | 용도 |
|------|------|
| `/docs/technical/canonical_enum.md` | 사람용 정의서 (본 문서) |
| `/assets/canonical/canonical_enum.md` | 동일 문서 (assets 복사본) |
| `/schema/canonical_key.schema.json` | 기계용 JSON Schema (Draft 2020-12) |
| `/docs/technical/KU_TO_CANONICAL_KEY_RULES.md` | KU → CK 생성 규칙서 |

JSON Schema는 본 문서와 동일한 enum 값을 포함하며, 프로그래밍적 검증에 사용된다.
KU에서 Canonical Key를 생성하는 규칙은 KU_TO_CANONICAL_KEY_RULES.md에 정의되어 있다.
    

---

## **7. 한 줄 요약**

  

> **Canonical Enum은**

> **“이 이야기가 왜 다른 이야기와 다른지”를**

> **기계에게 설명하기 위한 언어다.**

---

다음으로 할 수 있는 것:

  

1️⃣ **이 정의서를 기계용 JSON Schema로 변환**

2️⃣ **Canonical Key 생성 규칙 문서화 (KU → CK)**

3️⃣ **이 정의서를 Claude 프롬프트에 삽입하는 버전 작성**

  

원하는 다음 단계를 말해줘.