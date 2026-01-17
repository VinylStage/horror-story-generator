"""
Tests for template_loader module.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.story.template_loader import (
    load_template_skeletons,
    select_random_template,
    compute_template_weights,
    count_cluster_occurrences_in_registry,
    SYSTEMIC_INEVITABILITY_CLUSTER,
    PHASE3B_LOOKBACK_WINDOW,
    PHASE3B_WEIGHT_PENALTIES,
    reset_last_template_id,
    TEMPLATE_SKELETONS_PATH,
)


class TestLoadTemplateSkeletons:
    """Tests for load_template_skeletons function."""

    def test_loads_skeletons(self):
        """Test that template skeletons are loaded."""
        skeletons = load_template_skeletons()
        assert isinstance(skeletons, list)
        assert len(skeletons) > 0

    def test_skeleton_structure(self):
        """Test that skeletons have required fields."""
        skeletons = load_template_skeletons()
        assert len(skeletons) > 0

        skeleton = skeletons[0]
        assert "template_id" in skeleton
        assert "template_name" in skeleton


class TestSelectRandomTemplate:
    """Tests for select_random_template function."""

    def setup_method(self):
        """Reset last template ID before each test."""
        reset_last_template_id()

    def test_returns_template(self):
        """Test that select_random_template returns a template."""
        template = select_random_template()
        assert template is not None
        assert "template_id" in template

    def test_back_to_back_prevention(self):
        """Test that same template is not selected back-to-back."""
        template1 = select_random_template()
        template2 = select_random_template()

        # If there's more than one template, they should be different
        skeletons = load_template_skeletons()
        if len(skeletons) > 1:
            assert template1.get("template_id") != template2.get("template_id")

    def test_exclude_template_ids(self):
        """Test excluding specific template IDs."""
        skeletons = load_template_skeletons()
        if len(skeletons) < 2:
            pytest.skip("Need at least 2 templates for this test")

        first_id = skeletons[0].get("template_id")
        template = select_random_template(exclude_template_ids={first_id})

        # Selected template should not be the excluded one
        assert template.get("template_id") != first_id


class TestComputeTemplateWeights:
    """Tests for compute_template_weights function."""

    def test_no_penalty_below_threshold(self):
        """Test no penalty when cluster count is below threshold."""
        skeletons = [
            {"template_id": "T-001"},
            {"template_id": "T-002"},
        ]

        weights = compute_template_weights(skeletons, cluster_count=0)
        assert weights == [1.0, 1.0]

        weights = compute_template_weights(skeletons, cluster_count=3)
        assert weights == [1.0, 1.0]

    def test_penalty_at_threshold_4(self):
        """Test 50% penalty at cluster count >= 4."""
        skeletons = [
            {"template_id": "T-SYS-001"},  # In cluster
            {"template_id": "T-002"},       # Not in cluster
        ]

        weights = compute_template_weights(skeletons, cluster_count=4)
        assert weights[0] == 0.50  # Cluster template penalized
        assert weights[1] == 1.0   # Non-cluster template unchanged

    def test_penalty_at_threshold_6(self):
        """Test 80% penalty at cluster count >= 6."""
        skeletons = [
            {"template_id": "T-APT-001"},  # In cluster
            {"template_id": "T-002"},       # Not in cluster
        ]

        weights = compute_template_weights(skeletons, cluster_count=6)
        assert weights[0] == 0.20  # 80% penalty = 0.20 multiplier
        assert weights[1] == 1.0

    def test_penalty_at_threshold_8(self):
        """Test 95% penalty at cluster count >= 8."""
        skeletons = [
            {"template_id": "T-INF-001"},  # In cluster
            {"template_id": "T-002"},       # Not in cluster
        ]

        weights = compute_template_weights(skeletons, cluster_count=8)
        assert weights[0] == 0.05  # 95% penalty = 0.05 multiplier
        assert weights[1] == 1.0


class TestClusterConfiguration:
    """Tests for cluster configuration constants."""

    def test_cluster_set_type(self):
        """Test that cluster is a frozenset."""
        assert isinstance(SYSTEMIC_INEVITABILITY_CLUSTER, frozenset)

    def test_cluster_has_members(self):
        """Test that cluster has expected members."""
        assert "T-SYS-001" in SYSTEMIC_INEVITABILITY_CLUSTER
        assert "T-APT-001" in SYSTEMIC_INEVITABILITY_CLUSTER
        assert "T-INF-001" in SYSTEMIC_INEVITABILITY_CLUSTER
        assert "T-ECO-001" in SYSTEMIC_INEVITABILITY_CLUSTER

    def test_lookback_window(self):
        """Test lookback window configuration."""
        assert PHASE3B_LOOKBACK_WINDOW == 10

    def test_weight_penalties(self):
        """Test weight penalties configuration."""
        assert 4 in PHASE3B_WEIGHT_PENALTIES
        assert 6 in PHASE3B_WEIGHT_PENALTIES
        assert 8 in PHASE3B_WEIGHT_PENALTIES

        assert PHASE3B_WEIGHT_PENALTIES[4] == 0.50
        assert PHASE3B_WEIGHT_PENALTIES[6] == 0.20
        assert PHASE3B_WEIGHT_PENALTIES[8] == 0.05


class TestLoadTemplateSkeletonsEdgeCases:
    """Tests for edge cases in load_template_skeletons."""

    def test_file_not_found_returns_empty_list(self):
        """Test that missing file returns empty list."""
        with patch.object(Path, 'exists', return_value=False):
            # Need to patch the specific path object
            with patch('src.story.template_loader.TEMPLATE_SKELETONS_PATH') as mock_path:
                mock_path.exists.return_value = False
                skeletons = load_template_skeletons()
                assert skeletons == []


class TestCountClusterOccurrences:
    """Tests for count_cluster_occurrences_in_registry function."""

    def test_returns_zero_when_registry_is_none(self):
        """Test that None registry returns 0."""
        count = count_cluster_occurrences_in_registry(None)
        assert count == 0

    def test_returns_zero_on_registry_error(self):
        """Test that registry errors return 0."""
        mock_registry = MagicMock()
        mock_registry.load_recent_accepted.side_effect = Exception("DB error")

        count = count_cluster_occurrences_in_registry(mock_registry)
        assert count == 0

    def test_counts_cluster_templates(self):
        """Test counting templates in the cluster."""
        mock_record1 = MagicMock()
        mock_record1.template_id = "T-SYS-001"  # In cluster

        mock_record2 = MagicMock()
        mock_record2.template_id = "T-OTHER-001"  # Not in cluster

        mock_record3 = MagicMock()
        mock_record3.template_id = "T-APT-001"  # In cluster

        mock_registry = MagicMock()
        mock_registry.load_recent_accepted.return_value = [
            mock_record1, mock_record2, mock_record3
        ]

        count = count_cluster_occurrences_in_registry(mock_registry)
        assert count == 2

    def test_respects_lookback_parameter(self):
        """Test that lookback parameter is passed to registry."""
        mock_registry = MagicMock()
        mock_registry.load_recent_accepted.return_value = []

        count_cluster_occurrences_in_registry(mock_registry, lookback=5)
        mock_registry.load_recent_accepted.assert_called_once_with(limit=5)


class TestSelectRandomTemplateEdgeCases:
    """Tests for edge cases in select_random_template."""

    def setup_method(self):
        """Reset state before each test."""
        reset_last_template_id()

    def test_returns_none_when_no_skeletons(self):
        """Test that None is returned when no skeletons available."""
        with patch('src.story.template_loader.load_template_skeletons', return_value=[]):
            template = select_random_template()
            assert template is None

    def test_weighted_selection_with_registry(self):
        """Test weighted selection when registry is provided."""
        mock_record = MagicMock()
        mock_record.template_id = "T-SYS-001"

        mock_registry = MagicMock()
        # Return 4 cluster templates to trigger penalty
        mock_registry.load_recent_accepted.return_value = [mock_record] * 4

        # Call multiple times and verify it still works
        template = select_random_template(registry=mock_registry)
        assert template is not None
        assert "template_id" in template

    def test_no_penalty_when_cluster_count_low(self):
        """Test no penalty applied when cluster count < 4."""
        mock_record = MagicMock()
        mock_record.template_id = "T-SYS-001"

        mock_registry = MagicMock()
        # Return only 2 cluster templates (below threshold)
        mock_registry.load_recent_accepted.return_value = [mock_record] * 2

        template = select_random_template(registry=mock_registry)
        assert template is not None

    def test_weighted_selection_high_penalty(self):
        """Test weighted selection with high cluster count (>= 8)."""
        mock_record = MagicMock()
        mock_record.template_id = "T-SYS-001"

        mock_registry = MagicMock()
        # Return 10 cluster templates to trigger highest penalty
        mock_registry.load_recent_accepted.return_value = [mock_record] * 10

        template = select_random_template(registry=mock_registry)
        assert template is not None


class TestResetLastTemplateId:
    """Tests for reset_last_template_id function."""

    def test_reset_allows_same_template_selection(self):
        """Test that reset allows same template to be selected."""
        # Select a template
        template1 = select_random_template()

        # Reset
        reset_last_template_id()

        # Now the same template could theoretically be selected
        # (though random, at least it's possible)
        template2 = select_random_template()
        assert template2 is not None
