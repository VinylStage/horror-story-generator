"""
Tests for prompt_builder module.

Phase B+: System and user prompt construction tests.
"""

import pytest


class TestBuildSystemPrompt:
    """Tests for build_system_prompt function."""

    def test_returns_string(self):
        """Should return a string."""
        from src.story.prompt_builder import build_system_prompt

        result = build_system_prompt()

        assert isinstance(result, str)

    def test_default_prompt_without_template(self):
        """Should return default psychological horror prompt."""
        from src.story.prompt_builder import build_system_prompt

        result = build_system_prompt()

        assert "psychological horror" in result.lower()
        assert "first-person" in result.lower() or "1인칭" in result.lower()
        assert "Korean" in result

    def test_includes_core_guidelines(self):
        """Should include core horror guidelines."""
        from src.story.prompt_builder import build_system_prompt

        result = build_system_prompt()

        # Check for key elements
        assert "everyday" in result.lower() or "ordinary" in result.lower()
        assert "ending" in result.lower()
        assert "horror" in result.lower()

    def test_includes_skeleton_when_provided(self):
        """Should include skeleton when provided."""
        from src.story.prompt_builder import build_system_prompt

        skeleton = {
            "template_name": "test_template",
            "canonical_core": {
                "setting": "apartment",
                "primary_fear": "isolation",
                "antagonist": "neighbor",
                "mechanism": "gradual revelation",
                "twist": "loop"
            },
            "story_skeleton": {
                "act_1": "Protagonist moves into new apartment",
                "act_2": "Strange noises escalate",
                "act_3": "Discovery and loop"
            }
        }

        result = build_system_prompt(skeleton=skeleton)

        assert "test_template" in result
        assert "apartment" in result
        assert "isolation" in result
        assert "Act 1" in result or "act_1" in result.lower()

    def test_includes_research_context_when_provided(self):
        """Should include research context when provided."""
        from src.story.prompt_builder import build_system_prompt

        research_context = {
            "key_concepts": ["liminality", "threshold spaces"],
            "horror_applications": ["eerie transitions", "between states"],
            "source_cards": ["RC-001", "RC-002"]
        }

        result = build_system_prompt(research_context=research_context)

        assert "Research Context" in result
        assert "liminality" in result
        assert "threshold spaces" in result
        assert "eerie transitions" in result
        assert "RC-001" in result

    def test_includes_seed_context_when_provided(self):
        """Should include seed context when provided."""
        from src.story.prompt_builder import build_system_prompt

        seed_context = {
            "seed_id": "SS-2026-01-11-001",
            "key_themes": ["isolation", "paranoia"],
            "atmosphere_tags": ["oppressive", "uncanny"],
            "suggested_hooks": ["A researcher discovers something wrong"],
            "cultural_elements": ["corporate surveillance"]
        }

        result = build_system_prompt(seed_context=seed_context)

        assert "Story Seed" in result
        assert "isolation" in result
        assert "paranoia" in result
        assert "oppressive" in result
        assert "researcher discovers" in result
        assert "corporate surveillance" in result
        assert "SS-2026-01-11-001" in result

    def test_includes_both_research_and_seed(self):
        """Should include both research and seed contexts."""
        from src.story.prompt_builder import build_system_prompt

        research_context = {
            "key_concepts": ["concept1"],
            "horror_applications": ["app1"]
        }

        seed_context = {
            "seed_id": "SS-001",
            "key_themes": ["theme1"],
            "atmosphere_tags": ["atm1"]
        }

        result = build_system_prompt(
            research_context=research_context,
            seed_context=seed_context
        )

        assert "Research Context" in result
        assert "Story Seed" in result
        assert "concept1" in result
        assert "theme1" in result

    def test_legacy_template_format(self):
        """Should support legacy template format."""
        from src.story.prompt_builder import build_system_prompt

        template = {
            "story_config": {
                "genre": "horror",
                "atmosphere": "dark",
                "length": "short"
            },
            "story_elements": {
                "setting": {"location": "abandoned hospital"}
            },
            "writing_style": {
                "narrative_perspective": "1st person",
                "tense": "past",
                "tone": ["ominous", "dread"]
            }
        }

        result = build_system_prompt(template=template)

        assert "horror" in result.lower()
        assert "dark" in result.lower()
        assert "1st person" in result or "1인칭" in result


class TestFormatResearchContext:
    """Tests for _format_research_context function."""

    def test_returns_empty_for_none(self):
        """Should return empty string for None."""
        from src.story.prompt_builder import _format_research_context

        result = _format_research_context(None)

        assert result == ""

    def test_returns_empty_for_empty_dict(self):
        """Should return empty string for empty dict."""
        from src.story.prompt_builder import _format_research_context

        result = _format_research_context({})

        assert result == ""

    def test_formats_key_concepts(self):
        """Should format key concepts."""
        from src.story.prompt_builder import _format_research_context

        context = {
            "key_concepts": ["liminal spaces", "threshold psychology"]
        }

        result = _format_research_context(context)

        assert "concepts" in result.lower()
        assert "liminal spaces" in result
        assert "threshold psychology" in result

    def test_formats_horror_applications(self):
        """Should format horror applications."""
        from src.story.prompt_builder import _format_research_context

        context = {
            "horror_applications": ["use as transition terror", "exploit uncertainty"]
        }

        result = _format_research_context(context)

        assert "application" in result.lower() or "idea" in result.lower()
        assert "transition terror" in result

    def test_formats_source_cards(self):
        """Should format source card references."""
        from src.story.prompt_builder import _format_research_context

        context = {
            "source_cards": ["RC-001", "RC-002", "RC-003"]
        }

        result = _format_research_context(context)

        assert "RC-001" in result
        assert "RC-002" in result


class TestFormatSeedContext:
    """Tests for _format_seed_context function."""

    def test_returns_empty_for_none(self):
        """Should return empty string for None."""
        from src.story.prompt_builder import _format_seed_context

        result = _format_seed_context(None)

        assert result == ""

    def test_returns_empty_for_empty_dict(self):
        """Should return empty string for empty dict."""
        from src.story.prompt_builder import _format_seed_context

        result = _format_seed_context({})

        assert result == ""

    def test_formats_key_themes(self):
        """Should format key themes."""
        from src.story.prompt_builder import _format_seed_context

        context = {
            "key_themes": ["isolation", "paranoia", "surveillance"]
        }

        result = _format_seed_context(context)

        assert "themes" in result.lower()
        assert "isolation" in result
        assert "paranoia" in result

    def test_formats_atmosphere_tags(self):
        """Should format atmosphere tags."""
        from src.story.prompt_builder import _format_seed_context

        context = {
            "atmosphere_tags": ["oppressive", "uncanny", "liminal"]
        }

        result = _format_seed_context(context)

        assert "Atmosphere" in result
        assert "oppressive" in result

    def test_formats_suggested_hooks(self):
        """Should format suggested hooks."""
        from src.story.prompt_builder import _format_seed_context

        context = {
            "suggested_hooks": [
                "A researcher notices a pattern",
                "The elevator stops between floors"
            ]
        }

        result = _format_seed_context(context)

        assert "hook" in result.lower()
        assert "researcher notices" in result

    def test_formats_cultural_elements(self):
        """Should format cultural elements."""
        from src.story.prompt_builder import _format_seed_context

        context = {
            "cultural_elements": [
                "late-night convenience stores",
                "corporate overtime culture"
            ]
        }

        result = _format_seed_context(context)

        assert "Cultural" in result
        assert "convenience stores" in result

    def test_formats_seed_id(self):
        """Should format seed ID reference."""
        from src.story.prompt_builder import _format_seed_context

        context = {
            "seed_id": "SS-2026-01-11-001",
            "key_themes": ["test"]
        }

        result = _format_seed_context(context)

        assert "SS-2026-01-11-001" in result

    def test_includes_inspiration_note(self):
        """Should include note about being inspiration."""
        from src.story.prompt_builder import _format_seed_context

        context = {"key_themes": ["test"]}

        result = _format_seed_context(context)

        assert "inspire" in result.lower() or "seeds" in result.lower()


class TestBuildUserPrompt:
    """Tests for build_user_prompt function."""

    def test_returns_string(self):
        """Should return a string."""
        from src.story.prompt_builder import build_user_prompt

        result = build_user_prompt()

        assert isinstance(result, str)

    def test_uses_custom_request_when_provided(self):
        """Should use custom request when provided."""
        from src.story.prompt_builder import build_user_prompt

        custom = "Write a story about a haunted subway station"

        result = build_user_prompt(custom_request=custom)

        assert result == custom

    def test_returns_default_without_custom(self):
        """Should return default prompt without custom request."""
        from src.story.prompt_builder import build_user_prompt

        result = build_user_prompt()

        assert "horror" in result.lower()
        assert "story" in result.lower()

    def test_includes_template_context(self):
        """Should include template context when available."""
        from src.story.prompt_builder import build_user_prompt

        template = {
            "story_elements": {
                "setting": {
                    "location": "abandoned hospital",
                    "time_period": "1990s"
                },
                "plot_structure": {
                    "act_1": {
                        "hook": "A night shift nurse hears footsteps"
                    }
                }
            }
        }

        result = build_user_prompt(template=template)

        assert "hospital" in result or "Setting" in result


class TestPromptBuilderIntegration:
    """Integration tests for prompt builder."""

    def test_full_prompt_construction(self):
        """Should construct full prompt with all contexts."""
        from src.story.prompt_builder import build_system_prompt, build_user_prompt

        skeleton = {
            "template_name": "urban_horror",
            "canonical_core": {
                "setting": "subway",
                "primary_fear": "claustrophobia"
            },
            "story_skeleton": {
                "act_1": "Late night commute",
                "act_2": "Train stops in tunnel",
                "act_3": "Something boards"
            }
        }

        research_context = {
            "key_concepts": ["transit liminal spaces"],
            "horror_applications": ["trapped underground"]
        }

        seed_context = {
            "seed_id": "SS-001",
            "key_themes": ["entrapment", "isolation"],
            "atmosphere_tags": ["claustrophobic", "oppressive"]
        }

        system_prompt = build_system_prompt(
            skeleton=skeleton,
            research_context=research_context,
            seed_context=seed_context
        )

        user_prompt = build_user_prompt(
            custom_request="Write a horror story set in the Seoul subway at 2 AM"
        )

        # Verify system prompt has all sections
        assert "psychological horror" in system_prompt.lower()
        assert "urban_horror" in system_prompt
        assert "Research Context" in system_prompt
        assert "Story Seed" in system_prompt

        # Verify user prompt
        assert "Seoul subway" in user_prompt

    def test_empty_contexts_do_not_break(self):
        """Should handle empty contexts gracefully."""
        from src.story.prompt_builder import build_system_prompt

        # All empty/None contexts
        result = build_system_prompt(
            template=None,
            skeleton=None,
            research_context=None,
            seed_context=None
        )

        assert isinstance(result, str)
        assert len(result) > 0


class TestTargetLength:
    """Tests for target_length parameter (Issue #73)."""

    def test_default_length_when_not_provided(self):
        """Should use default length instruction when target_length is None."""
        from src.story.prompt_builder import build_system_prompt

        result = build_system_prompt(target_length=None)

        assert "3,000–4,000 characters" in result

    def test_custom_length_injection(self):
        """Should inject custom target length into prompt."""
        from src.story.prompt_builder import build_system_prompt

        result = build_system_prompt(target_length=2000)

        assert "2,000 characters" in result
        assert "±10%" in result
        # Should NOT contain default length
        assert "3,000–4,000" not in result

    def test_custom_length_with_large_value(self):
        """Should format large target length with thousands separator."""
        from src.story.prompt_builder import build_system_prompt

        result = build_system_prompt(target_length=4500)

        assert "4,500 characters" in result

    def test_custom_length_does_not_mention_counts_in_output(self):
        """Should include instruction to not mention character counts."""
        from src.story.prompt_builder import build_system_prompt

        result = build_system_prompt(target_length=1500)

        assert "Do not mention character counts" in result

    def test_custom_length_with_skeleton(self):
        """Should work with skeleton template."""
        from src.story.prompt_builder import build_system_prompt

        skeleton = {
            "template_name": "test_template",
            "canonical_core": {"setting": "apartment"},
            "story_skeleton": {"act_1": "Test"}
        }

        result = build_system_prompt(skeleton=skeleton, target_length=3000)

        assert "test_template" in result
        assert "3,000 characters" in result

    def test_custom_length_with_research_context(self):
        """Should work with research context."""
        from src.story.prompt_builder import build_system_prompt

        research_context = {
            "key_concepts": ["test concept"],
            "horror_applications": ["test app"]
        }

        result = build_system_prompt(research_context=research_context, target_length=2500)

        assert "Research Context" in result
        assert "2,500 characters" in result

    def test_legacy_template_with_custom_length(self):
        """Should override template word_count when target_length provided."""
        from src.story.prompt_builder import build_system_prompt

        template = {
            "story_config": {"genre": "horror"},
            "additional_requirements": {"word_count": 5000}
        }

        result = build_system_prompt(template=template, target_length=2000)

        # Should use target_length, not template's word_count
        assert "2,000 characters" in result
        assert "±10%" in result

    def test_legacy_template_without_custom_length(self):
        """Should use template word_count when target_length not provided."""
        from src.story.prompt_builder import build_system_prompt

        template = {
            "story_config": {"genre": "horror"},
            "additional_requirements": {"word_count": 4000}
        }

        result = build_system_prompt(template=template, target_length=None)

        # Should use template's word_count
        assert "4000 characters" in result or "4,000 characters" in result
