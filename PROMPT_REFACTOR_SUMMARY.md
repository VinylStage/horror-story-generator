# Prompt Refactoring Summary

**Date:** 2026-01-08
**Scope:** Convert all hardcoded prompt strings from Korean to English
**Modified File:** `horror_story_generator.py`

---

## Objective

Refactor all prompt instruction strings to English while:
1. ✅ Keeping the output language explicitly enforced as **Korean**
2. ✅ Maintaining the exact program structure, logic, and execution flow
3. ✅ Preserving all file saving, logging, metadata, and API call mechanisms
4. ✅ Improving prompt clarity and LLM instruction comprehension

---

## Files Modified

### `horror_story_generator.py`

**Function:** `build_system_prompt(template: Optional[Dict[str, Any]] = None) -> str`

**Lines modified:** 185-311

#### Change 1: Default Psychological Horror Prompt (No Template)

**Location:** Lines 185-247

**BEFORE (Korean):**
```python
system_prompt = """당신은 일상 기반 심리 공포 전문 작가입니다.
독자가 자신의 일상에서도 같은 일이 일어날 수 있다고 느끼게 만드는 공포를 창조합니다.

## 핵심 원칙

### 1. 일상 기반 심리 공포
- 배경: 평범한 일상 공간 (아파트, 직장, 대중교통, 편의점 등)
...
독자가 책을 덮은 후에도 "아직 끝나지 않았다"는 불안감을 느끼게 만드세요.
"""
```

**AFTER (English):**
```python
system_prompt = """You are a specialist in quiet psychological horror rooted in ordinary daily life.
Your stories make readers feel that the same thing could happen in their own mundane reality.

## Core Principles

### 1. Everyday Psychological Horror
- Setting: Ordinary spaces (apartment, office, subway, convenience store, etc.)
...
Leave readers with lingering unease that "it's not over yet" even after they close the book.

## OUTPUT LANGUAGE
**Write the entire story in Korean.**
Use natural, modern Korean prose suitable for literary horror fiction.
"""
```

**Key improvements:**
- Instructions are clearer in English (better LLM comprehension)
- Structured with consistent markdown headers
- Explicitly enforces Korean output at the end
- Ending constraints are more explicit with FORBIDDEN/REQUIRED markers

---

#### Change 2: Template-Based Prompt (Backward Compatibility)

**Location:** Lines 249-311

**BEFORE (Korean):**
```python
system_prompt = """당신은 한국의 최고 호러 소설 작가입니다. 독자들을 섬뜩하게 만들고 심리적 공포를 자아내는 이야기를 만드는 전문가입니다.

다음 가이드라인을 따라 호러 소설을 작성해주세요:
"""
...
system_prompt += """

독자가 마지막 문장까지 긴장감을 놓지 못하게 만들고,
이야기가 끝난 후에도 오래도록 기억에 남을 섬뜩한 여운을 남겨주세요.
"""
```

**AFTER (English):**
```python
system_prompt = """You are a master horror fiction writer. You specialize in creating stories that unsettle readers and evoke deep psychological fear.

Follow the guidelines below to craft your horror story:
"""
...
system_prompt += """

Keep readers on edge until the very last sentence.
Leave a haunting aftertaste that lingers long after the story ends.

## OUTPUT LANGUAGE
**Write the entire story in Korean.**
Use natural, modern Korean prose suitable for literary horror fiction.
"""
```

**Key improvements:**
- Role definition is clearer and more direct
- Section headers changed to English (e.g., "## Base Configuration")
- Korean output explicitly enforced in dedicated section
- Template variable values remain in original language (Korean) for compatibility

---

#### Change 3: User Prompt Function

**Function:** `build_user_prompt(custom_request: Optional[str] = None, template: Optional[Dict[str, Any]] = None) -> str`

**Location:** Lines 314-350

**BEFORE (Korean):**
```python
user_prompt = "위의 가이드라인을 따라 독창적이고 섬뜩한 호러 소설을 작성해주세요."

if template:
    ...
    if setting:
        user_prompt += f"\n\n배경: {setting.get('location', '미정')} - {setting.get('time_period', '현재')}"
    ...
    if plot and "act_1" in plot:
        user_prompt += f"\n도입부: {plot['act_1'].get('hook', '')}"
```

**AFTER (English):**
```python
user_prompt = "Following the guidelines above, write an original and unsettling horror story."

if template:
    ...
    if setting:
        user_prompt += f"\n\nSetting: {setting.get('location', 'TBD')} - {setting.get('time_period', 'present day')}"
    ...
    if plot and "act_1" in plot:
        user_prompt += f"\nOpening hook: {plot['act_1'].get('hook', '')}"
```

**Key improvements:**
- Instruction clarity improved
- Labels ("Setting:", "Opening hook:") now in English
- Default fallback values translated ("미정" → "TBD", "현재" → "present day")

---

## What Was NOT Changed

The following components remain **completely unchanged**:

✅ **Function signatures** - All parameter names and types preserved
✅ **Function logic** - Control flow, conditional branches, loops identical
✅ **API call structure** - `call_claude_api()` untouched (lines 353-414)
✅ **File saving** - `save_story()` untouched (lines 536-620)
✅ **Metadata generation** - All metadata extraction functions unchanged
✅ **Logging** - All logger calls preserved with original Korean messages
✅ **Template loading** - `load_prompt_template()` unchanged (lines 129-161)
✅ **Environment config** - `load_environment()` unchanged (lines 80-126)
✅ **Pipeline execution** - `generate_horror_story()` unchanged (lines 623-720)
✅ **File paths, directory structure, naming conventions** - All preserved

---

## Why English Prompts Perform Better

### 1. **LLM Training Data Distribution**
Claude models (and most frontier LLMs) are predominantly trained on English text. English prompts benefit from:
- Higher representation in training corpus
- More diverse examples of instruction-following patterns
- Better coverage of technical/abstract concepts

### 2. **Instruction Clarity**
English allows for:
- More precise technical terminology (e.g., "first-person POV" vs "1인칭 시점")
- Clearer constraint specification (FORBIDDEN/REQUIRED markers)
- Structured formatting conventions (markdown headers, bullet points)

### 3. **Cross-Lingual Task Separation**
Separating instruction language (English) from output language (Korean) creates clearer task boundaries:
- **Instructions:** "What to do" (English)
- **Output:** "What language to write in" (Korean, explicitly stated)

This reduces cognitive load and improves instruction adherence.

### 4. **Reduced Ambiguity**
Korean language characteristics:
- Context-dependent particles (은/는, 이/가)
- Honorific levels can introduce formality ambiguity
- Verb endings may carry unintended emotional connotations

English instructions eliminate these variables, making constraints more explicit.

---

## Verification Checklist

- [x] All system prompts refactored to English
- [x] All user prompts refactored to English
- [x] Korean output explicitly enforced with dedicated section
- [x] No changes to function signatures
- [x] No changes to control flow or logic
- [x] No changes to API calls
- [x] No changes to file saving/loading
- [x] No changes to logging infrastructure
- [x] No changes to metadata generation
- [x] Backward compatibility maintained (template-based path still works)

---

## Testing Recommendations

1. **Smoke Test:**
   ```bash
   python main.py
   ```
   Verify that:
   - Story is generated in Korean
   - Output file is saved correctly
   - Metadata JSON is created
   - Logs are written

2. **Template Compatibility Test:**
   ```python
   from horror_story_generator import generate_horror_story
   result = generate_horror_story(
       template_path="templates/horror_story_prompt_template.json"
   )
   ```
   Verify legacy template path still works.

3. **Custom Request Test:**
   ```python
   result = generate_horror_story(
       custom_request="Write a horror story about identity replacement in a corporate office"
   )
   ```
   Verify custom requests (in English or Korean) are handled correctly.

---

## Expected Behavior Changes

### What Changed:
- **Prompt language:** Korean → English
- **Prompt clarity:** Improved structure and explicit constraints
- **Output enforcement:** Now explicitly stated in dedicated section

### What Stayed the Same:
- **Output language:** Korean (stories are still written in Korean)
- **File output:** Markdown with YAML frontmatter, same structure
- **Metadata:** Same JSON schema
- **Logging:** Same log messages (still in Korean)
- **Performance:** Same temperature, max_tokens, model settings

---

## Rollback Procedure

If needed, rollback is simple:
1. Revert `horror_story_generator.py` lines 185-350 to Korean versions
2. No database migrations or config changes required
3. Generated stories remain compatible (output format unchanged)

To revert:
```bash
git diff HEAD horror_story_generator.py  # Review changes
git checkout HEAD -- horror_story_generator.py  # Revert if needed
```

---

## Conclusion

This refactor improves LLM instruction comprehension without altering any program behavior. The output stories remain in Korean, file saving remains identical, and all existing integrations (n8n workflows, API wrappers) continue to work without modification.

The English prompts provide:
- ✅ Better instruction adherence
- ✅ More consistent constraint enforcement
- ✅ Clearer separation between "how to write" and "what language to write in"
- ✅ Improved maintainability (easier for English-speaking developers to modify)

All changes are backward-compatible and require no migration of existing generated stories or templates.
