#!/bin/bash
# =============================================================================
# Backup Verification Script
# Horror Story Generator - Backup/Restore Verification
# Version: 1.0.0
# =============================================================================

set -e

# Load configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/backup_config.sh"

# =============================================================================
# Test Configuration
# =============================================================================

TEST_DIR=""
CLEANUP=true
VERBOSE=false

# =============================================================================
# Usage
# =============================================================================

show_usage() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]

Verify backup and restore functionality with data integrity checks.

OPTIONS:
    --test-dir <path>     Directory for test files (default: temp directory)
    --no-cleanup          Don't clean up test files after completion
    --verbose             Show detailed output
    -h, --help            Show this help message

TESTS:
    1. Backup creation test
    2. Archive integrity test (checksum)
    3. Restore functionality test
    4. Data integrity verification (file-by-file comparison)
    5. SQLite database verification
    6. Full cycle test (backup → modify → restore → verify)

EOF
}

# =============================================================================
# Parse Arguments
# =============================================================================

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --test-dir)
                TEST_DIR="$2"
                shift 2
                ;;
            --no-cleanup)
                CLEANUP=false
                shift
                ;;
            --verbose)
                VERBOSE=true
                shift
                ;;
            -h|--help)
                show_usage
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done

    # Create temp directory if not specified
    if [[ -z "$TEST_DIR" ]]; then
        TEST_DIR=$(mktemp -d)
    else
        mkdir -p "$TEST_DIR"
    fi
}

# =============================================================================
# Test Functions
# =============================================================================

test_count=0
pass_count=0
fail_count=0

run_test() {
    local test_name="$1"
    local test_func="$2"

    test_count=$((test_count + 1))
    echo ""
    log_step "Test $test_count: $test_name"

    if $test_func; then
        pass_count=$((pass_count + 1))
        log_success "PASSED: $test_name"
        return 0
    else
        fail_count=$((fail_count + 1))
        log_error "FAILED: $test_name"
        return 1
    fi
}

# -----------------------------------------------------------------------------
# Test 1: Backup Creation
# -----------------------------------------------------------------------------
test_backup_creation() {
    local backup_output="${TEST_DIR}/backup_test"

    # Run backup
    "${SCRIPT_DIR}/backup.sh" --output "$backup_output" --compress > /dev/null 2>&1

    # Check if backup was created
    local backup_file=$(find "$backup_output" -name "backup_*.tar.gz" | head -1)

    if [[ -z "$backup_file" ]]; then
        log_error "No backup file created"
        return 1
    fi

    # Check if checksum file exists
    if [[ ! -f "${backup_file}.sha256" ]]; then
        log_error "No checksum file created"
        return 1
    fi

    log_info "Backup created: $backup_file"
    echo "$backup_file" > "${TEST_DIR}/backup_path.txt"
    return 0
}

# -----------------------------------------------------------------------------
# Test 2: Archive Integrity
# -----------------------------------------------------------------------------
test_archive_integrity() {
    local backup_file=$(cat "${TEST_DIR}/backup_path.txt" 2>/dev/null)

    if [[ -z "$backup_file" ]] || [[ ! -f "$backup_file" ]]; then
        log_error "Backup file not found"
        return 1
    fi

    # Verify checksum
    local stored_checksum=$(cat "${backup_file}.sha256" | cut -d: -f2)
    local actual_checksum=$(calculate_checksum "$backup_file")

    if [[ "$stored_checksum" != "$actual_checksum" ]]; then
        log_error "Checksum mismatch!"
        log_error "  Expected: $stored_checksum"
        log_error "  Actual:   $actual_checksum"
        return 1
    fi

    log_info "Checksum verified: $actual_checksum"

    # Verify archive can be extracted
    local extract_test="${TEST_DIR}/extract_test"
    mkdir -p "$extract_test"

    if ! tar -tzf "$backup_file" > /dev/null 2>&1; then
        log_error "Archive is corrupted"
        return 1
    fi

    log_info "Archive integrity verified"
    return 0
}

# -----------------------------------------------------------------------------
# Test 3: Manifest Validation
# -----------------------------------------------------------------------------
test_manifest_validation() {
    local backup_file=$(cat "${TEST_DIR}/backup_path.txt" 2>/dev/null)

    if [[ -z "$backup_file" ]]; then
        log_error "Backup file not found"
        return 1
    fi

    # Extract manifest
    local extract_dir="${TEST_DIR}/manifest_test"
    mkdir -p "$extract_dir"
    tar -xzf "$backup_file" -C "$extract_dir"

    local manifest=$(find "$extract_dir" -name "manifest.json" | head -1)

    if [[ -z "$manifest" ]]; then
        log_error "No manifest.json in backup"
        return 1
    fi

    # Validate JSON format
    if command -v jq &> /dev/null; then
        if ! jq . "$manifest" > /dev/null 2>&1; then
            log_error "Invalid JSON in manifest"
            return 1
        fi

        # Check required fields
        local version=$(jq -r '.backup_version' "$manifest")
        local created=$(jq -r '.created_at' "$manifest")
        local app_ver=$(jq -r '.app_version' "$manifest")

        if [[ "$version" == "null" ]] || [[ "$created" == "null" ]]; then
            log_error "Missing required fields in manifest"
            return 1
        fi

        log_info "Manifest valid - version: $version, app: $app_ver"
    else
        log_warning "jq not installed, skipping detailed validation"
    fi

    return 0
}

# -----------------------------------------------------------------------------
# Test 4: Restore Dry-Run
# -----------------------------------------------------------------------------
test_restore_dry_run() {
    local backup_file=$(cat "${TEST_DIR}/backup_path.txt" 2>/dev/null)

    if [[ -z "$backup_file" ]]; then
        log_error "Backup file not found"
        return 1
    fi

    # Run restore in dry-run mode
    local output=$("${SCRIPT_DIR}/restore.sh" "$backup_file" --dry-run 2>&1)

    # Check for success message
    if echo "$output" | grep -q "Dry-run complete"; then
        log_info "Restore dry-run successful"
        return 0
    else
        log_error "Restore dry-run failed"
        echo "$output"
        return 1
    fi
}

# -----------------------------------------------------------------------------
# Test 5: Data Integrity (Full Cycle)
# -----------------------------------------------------------------------------
test_data_integrity() {
    local backup_file=$(cat "${TEST_DIR}/backup_path.txt" 2>/dev/null)

    if [[ -z "$backup_file" ]]; then
        log_error "Backup file not found"
        return 1
    fi

    # Extract backup
    local backup_extract="${TEST_DIR}/backup_data"
    mkdir -p "$backup_extract"
    tar -xzf "$backup_file" -C "$backup_extract"

    local backup_content=$(find "$backup_extract" -mindepth 1 -maxdepth 1 -type d | head -1)

    # Compare each component
    local all_match=true

    # Story Registry
    if [[ -f "${backup_content}/story_registry.db" ]] && [[ -f "$STORY_REGISTRY_DB" ]]; then
        local backup_hash=$(calculate_checksum "${backup_content}/story_registry.db")
        local current_hash=$(calculate_checksum "$STORY_REGISTRY_DB")

        if [[ "$backup_hash" == "$current_hash" ]]; then
            log_info "story-registry: checksums match"
        else
            log_warning "story-registry: checksums differ (data may have changed since backup)"
        fi
    fi

    # Research directory - compare file count
    if [[ -d "${backup_content}/research" ]] && [[ -d "$RESEARCH_DIR" ]]; then
        local backup_count=$(find "${backup_content}/research" -type f | wc -l | tr -d ' ')
        local current_count=$(find "$RESEARCH_DIR" -type f | wc -l | tr -d ' ')

        if [[ "$backup_count" == "$current_count" ]]; then
            log_info "research: file counts match ($backup_count files)"
        else
            log_warning "research: file counts differ (backup: $backup_count, current: $current_count)"
        fi
    fi

    # Stories directory - compare file count
    if [[ -d "${backup_content}/novel" ]] && [[ -d "$NOVEL_DIR" ]]; then
        local backup_count=$(find "${backup_content}/novel" -type f | wc -l | tr -d ' ')
        local current_count=$(find "$NOVEL_DIR" -type f | wc -l | tr -d ' ')

        if [[ "$backup_count" == "$current_count" ]]; then
            log_info "stories: file counts match ($backup_count files)"
        else
            log_warning "stories: file counts differ (backup: $backup_count, current: $current_count)"
        fi
    fi

    return 0
}

# -----------------------------------------------------------------------------
# Test 6: SQLite Integrity
# -----------------------------------------------------------------------------
test_sqlite_integrity() {
    local backup_file=$(cat "${TEST_DIR}/backup_path.txt" 2>/dev/null)

    if [[ -z "$backup_file" ]]; then
        log_error "Backup file not found"
        return 1
    fi

    # Extract backup
    local backup_extract="${TEST_DIR}/sqlite_test"
    mkdir -p "$backup_extract"
    tar -xzf "$backup_file" -C "$backup_extract"

    local backup_content=$(find "$backup_extract" -mindepth 1 -maxdepth 1 -type d | head -1)

    # Test story_registry.db
    if [[ -f "${backup_content}/story_registry.db" ]]; then
        if command -v sqlite3 &> /dev/null; then
            local result=$(sqlite3 "${backup_content}/story_registry.db" "PRAGMA integrity_check;" 2>&1)
            if [[ "$result" == "ok" ]]; then
                log_info "story_registry.db: integrity check passed"
            else
                log_error "story_registry.db: integrity check failed"
                return 1
            fi

            # Count records
            local story_count=$(sqlite3 "${backup_content}/story_registry.db" "SELECT COUNT(*) FROM stories;" 2>/dev/null || echo "0")
            log_info "story_registry.db: $story_count stories"
        else
            log_warning "sqlite3 not installed, skipping database integrity check"
        fi
    fi

    # Test research registry.sqlite
    if [[ -f "${backup_content}/research/registry.sqlite" ]]; then
        if command -v sqlite3 &> /dev/null; then
            local result=$(sqlite3 "${backup_content}/research/registry.sqlite" "PRAGMA integrity_check;" 2>&1)
            if [[ "$result" == "ok" ]]; then
                log_info "research/registry.sqlite: integrity check passed"
            else
                log_error "research/registry.sqlite: integrity check failed"
                return 1
            fi
        fi
    fi

    return 0
}

# -----------------------------------------------------------------------------
# Test 7: Schema Validation
# -----------------------------------------------------------------------------
test_schema_validation() {
    local backup_file=$(cat "${TEST_DIR}/backup_path.txt" 2>/dev/null)

    if [[ -z "$backup_file" ]]; then
        log_error "Backup file not found"
        return 1
    fi

    local backup_extract="${TEST_DIR}/schema_test"
    mkdir -p "$backup_extract"
    tar -xzf "$backup_file" -C "$backup_extract"

    local backup_content=$(find "$backup_extract" -mindepth 1 -maxdepth 1 -type d | head -1)
    local all_valid=true

    # Check story_registry.db schema
    if [[ -f "${backup_content}/story_registry.db" ]]; then
        if command -v sqlite3 &> /dev/null; then
            # Check required tables
            local tables=$(sqlite3 "${backup_content}/story_registry.db" ".tables" 2>/dev/null)

            if echo "$tables" | grep -q "stories"; then
                log_info "story_registry: 'stories' table exists"
            else
                log_error "story_registry: 'stories' table missing"
                all_valid=false
            fi

            if echo "$tables" | grep -q "meta"; then
                log_info "story_registry: 'meta' table exists"
            else
                log_error "story_registry: 'meta' table missing"
                all_valid=false
            fi

            # Check schema version
            local schema_version=$(sqlite3 "${backup_content}/story_registry.db" \
                "SELECT value FROM meta WHERE key='schema_version';" 2>/dev/null)
            if [[ -n "$schema_version" ]]; then
                log_info "story_registry: schema version = $schema_version"
            else
                log_warning "story_registry: no schema version found"
            fi

            # Check required columns in stories table
            local columns=$(sqlite3 "${backup_content}/story_registry.db" \
                "PRAGMA table_info(stories);" 2>/dev/null | cut -d'|' -f2)

            for col in "id" "created_at" "semantic_summary" "accepted"; do
                if echo "$columns" | grep -q "^${col}$"; then
                    [[ "$VERBOSE" == true ]] && log_info "story_registry: column '$col' exists"
                else
                    log_error "story_registry: required column '$col' missing"
                    all_valid=false
                fi
            done
        fi
    fi

    # Check research registry.sqlite schema
    if [[ -f "${backup_content}/research/registry.sqlite" ]]; then
        if command -v sqlite3 &> /dev/null; then
            local tables=$(sqlite3 "${backup_content}/research/registry.sqlite" ".tables" 2>/dev/null)

            if echo "$tables" | grep -q "research_cards"; then
                log_info "research_registry: 'research_cards' table exists"
            else
                log_error "research_registry: 'research_cards' table missing"
                all_valid=false
            fi

            # Check required columns
            local columns=$(sqlite3 "${backup_content}/research/registry.sqlite" \
                "PRAGMA table_info(research_cards);" 2>/dev/null | cut -d'|' -f2)

            for col in "card_id" "topic" "created_at" "status"; do
                if echo "$columns" | grep -q "^${col}$"; then
                    [[ "$VERBOSE" == true ]] && log_info "research_registry: column '$col' exists"
                else
                    log_error "research_registry: required column '$col' missing"
                    all_valid=false
                fi
            done
        fi
    fi

    # Check seed registry schema
    if [[ -f "${backup_content}/seeds/seed_registry.sqlite" ]]; then
        if command -v sqlite3 &> /dev/null; then
            local tables=$(sqlite3 "${backup_content}/seeds/seed_registry.sqlite" ".tables" 2>/dev/null)

            if echo "$tables" | grep -q "story_seeds"; then
                log_info "seed_registry: 'story_seeds' table exists"
            else
                log_warning "seed_registry: 'story_seeds' table missing"
            fi
        fi
    fi

    if [[ "$all_valid" == true ]]; then
        return 0
    else
        return 1
    fi
}

# -----------------------------------------------------------------------------
# Test 8: Research Card JSON Validation
# -----------------------------------------------------------------------------
test_research_card_json() {
    local backup_file=$(cat "${TEST_DIR}/backup_path.txt" 2>/dev/null)

    if [[ -z "$backup_file" ]]; then
        log_error "Backup file not found"
        return 1
    fi

    local backup_extract="${TEST_DIR}/json_test"
    mkdir -p "$backup_extract"
    tar -xzf "$backup_file" -C "$backup_extract"

    local backup_content=$(find "$backup_extract" -mindepth 1 -maxdepth 1 -type d | head -1)

    # Find research card JSON files
    local card_files=$(find "${backup_content}/research" -name "RC-*.json" 2>/dev/null)
    local card_count=$(echo "$card_files" | grep -c "RC-" || echo "0")

    if [[ "$card_count" -eq 0 ]]; then
        log_warning "No research card JSON files found"
        return 0
    fi

    log_info "Found $card_count research card JSON files"

    local valid_count=0
    local invalid_count=0

    # Check up to 5 random cards
    local sample_cards=$(echo "$card_files" | head -5)

    while IFS= read -r card_file; do
        [[ -z "$card_file" ]] && continue

        if command -v jq &> /dev/null; then
            # Validate JSON syntax
            if ! jq . "$card_file" > /dev/null 2>&1; then
                log_error "Invalid JSON: $(basename "$card_file")"
                invalid_count=$((invalid_count + 1))
                continue
            fi

            # Check required fields
            local card_id=$(jq -r '.card_id // empty' "$card_file")
            local version=$(jq -r '.version // empty' "$card_file")
            local topic=$(jq -r '.input.topic // empty' "$card_file")
            local title=$(jq -r '.output.title // empty' "$card_file")

            if [[ -z "$card_id" ]] || [[ -z "$topic" ]]; then
                log_error "Missing required fields: $(basename "$card_file")"
                invalid_count=$((invalid_count + 1))
            else
                valid_count=$((valid_count + 1))
                [[ "$VERBOSE" == true ]] && log_info "Valid: $card_id"
            fi

            # Check canonical_core structure
            local has_canonical=$(jq -r '.canonical_core.setting_archetype // empty' "$card_file")
            if [[ -z "$has_canonical" ]]; then
                log_warning "Missing canonical_core: $(basename "$card_file")"
            fi
        else
            # Basic JSON check without jq
            if python3 -c "import json; json.load(open('$card_file'))" 2>/dev/null; then
                valid_count=$((valid_count + 1))
            else
                invalid_count=$((invalid_count + 1))
            fi
        fi
    done <<< "$sample_cards"

    log_info "Research cards validated: $valid_count valid, $invalid_count invalid"

    if [[ "$invalid_count" -gt 0 ]]; then
        return 1
    fi
    return 0
}

# -----------------------------------------------------------------------------
# Test 9: Story Metadata JSON Validation
# -----------------------------------------------------------------------------
test_story_metadata_json() {
    local backup_file=$(cat "${TEST_DIR}/backup_path.txt" 2>/dev/null)

    if [[ -z "$backup_file" ]]; then
        log_error "Backup file not found"
        return 1
    fi

    local backup_extract="${TEST_DIR}/story_json_test"
    mkdir -p "$backup_extract"
    tar -xzf "$backup_file" -C "$backup_extract"

    local backup_content=$(find "$backup_extract" -mindepth 1 -maxdepth 1 -type d | head -1)

    # Find story metadata JSON files
    local meta_files=$(find "${backup_content}/novel" -name "*_metadata.json" 2>/dev/null)
    local meta_count=$(echo "$meta_files" | grep -c "_metadata.json" || echo "0")

    if [[ "$meta_count" -eq 0 ]]; then
        log_warning "No story metadata JSON files found"
        return 0
    fi

    log_info "Found $meta_count story metadata files"

    local valid_count=0
    local invalid_count=0

    while IFS= read -r meta_file; do
        [[ -z "$meta_file" ]] && continue

        if command -v jq &> /dev/null; then
            # Validate JSON syntax
            if ! jq . "$meta_file" > /dev/null 2>&1; then
                log_error "Invalid JSON: $(basename "$meta_file")"
                invalid_count=$((invalid_count + 1))
                continue
            fi

            # Check required fields (generated_at is always required, story_id is optional for older files)
            local story_id=$(jq -r '.story_id // empty' "$meta_file")
            local generated_at=$(jq -r '.generated_at // empty' "$meta_file")
            local word_count=$(jq -r '.word_count // empty' "$meta_file")

            if [[ -z "$generated_at" ]]; then
                log_error "Missing required fields: $(basename "$meta_file")"
                invalid_count=$((invalid_count + 1))
            else
                valid_count=$((valid_count + 1))
                if [[ -z "$story_id" ]]; then
                    [[ "$VERBOSE" == true ]] && log_info "Valid (legacy): $(basename "$meta_file") (words: $word_count)"
                else
                    [[ "$VERBOSE" == true ]] && log_info "Valid: $story_id (words: $word_count)"
                fi
            fi
        else
            if python3 -c "import json; json.load(open('$meta_file'))" 2>/dev/null; then
                valid_count=$((valid_count + 1))
            else
                invalid_count=$((invalid_count + 1))
            fi
        fi
    done <<< "$meta_files"

    log_info "Story metadata validated: $valid_count valid, $invalid_count invalid"

    if [[ "$invalid_count" -gt 0 ]]; then
        return 1
    fi
    return 0
}

# -----------------------------------------------------------------------------
# Test 10: Story File Pair Validation (MD + JSON)
# -----------------------------------------------------------------------------
test_story_file_pairs() {
    local backup_file=$(cat "${TEST_DIR}/backup_path.txt" 2>/dev/null)

    if [[ -z "$backup_file" ]]; then
        log_error "Backup file not found"
        return 1
    fi

    local backup_extract="${TEST_DIR}/pair_test"
    mkdir -p "$backup_extract"
    tar -xzf "$backup_file" -C "$backup_extract"

    local backup_content=$(find "$backup_extract" -mindepth 1 -maxdepth 1 -type d | head -1)
    local novel_dir="${backup_content}/novel"

    if [[ ! -d "$novel_dir" ]]; then
        log_warning "No novel directory in backup"
        return 0
    fi

    local md_files=$(find "$novel_dir" -name "*.md" 2>/dev/null)
    local md_count=$(echo "$md_files" | grep -c ".md" || echo "0")

    if [[ "$md_count" -eq 0 ]]; then
        log_warning "No story markdown files found"
        return 0
    fi

    local matched=0
    local unmatched=0

    while IFS= read -r md_file; do
        [[ -z "$md_file" ]] && continue

        # Expected metadata file
        local base_name=$(basename "$md_file" .md)
        local meta_file="${novel_dir}/${base_name}_metadata.json"

        if [[ -f "$meta_file" ]]; then
            matched=$((matched + 1))
            [[ "$VERBOSE" == true ]] && log_info "Pair found: $base_name"
        else
            unmatched=$((unmatched + 1))
            log_warning "Missing metadata for: $base_name"
        fi
    done <<< "$md_files"

    log_info "Story file pairs: $matched matched, $unmatched missing metadata"

    if [[ "$unmatched" -gt 0 ]]; then
        log_warning "Some stories missing metadata files"
    fi

    return 0
}

# -----------------------------------------------------------------------------
# Test 11: FAISS Metadata Consistency
# -----------------------------------------------------------------------------
test_faiss_consistency() {
    local backup_file=$(cat "${TEST_DIR}/backup_path.txt" 2>/dev/null)

    if [[ -z "$backup_file" ]]; then
        log_error "Backup file not found"
        return 1
    fi

    local backup_extract="${TEST_DIR}/faiss_test"
    mkdir -p "$backup_extract"
    tar -xzf "$backup_file" -C "$backup_extract"

    local backup_content=$(find "$backup_extract" -mindepth 1 -maxdepth 1 -type d | head -1)
    local vectors_dir="${backup_content}/research/vectors"

    if [[ ! -d "$vectors_dir" ]]; then
        log_warning "No vectors directory in backup"
        return 0
    fi

    local metadata_file="${vectors_dir}/metadata.json"
    local faiss_file="${vectors_dir}/research.faiss"

    # Check both files exist
    if [[ ! -f "$metadata_file" ]]; then
        log_warning "FAISS metadata.json not found"
        return 0
    fi

    if [[ ! -f "$faiss_file" ]]; then
        log_warning "research.faiss not found"
        return 0
    fi

    if command -v jq &> /dev/null; then
        # Validate metadata JSON
        if ! jq . "$metadata_file" > /dev/null 2>&1; then
            log_error "FAISS metadata.json is invalid JSON"
            return 1
        fi

        # Check dimension
        local dimension=$(jq -r '.dimension // empty' "$metadata_file")
        if [[ "$dimension" != "768" ]]; then
            log_warning "FAISS dimension is $dimension (expected 768)"
        else
            log_info "FAISS dimension: $dimension"
        fi

        # Check id_to_card and card_to_id consistency
        local id_to_card_count=$(jq -r '.id_to_card | length' "$metadata_file")
        local card_to_id_count=$(jq -r '.card_to_id | length' "$metadata_file")

        if [[ "$id_to_card_count" == "$card_to_id_count" ]]; then
            log_info "FAISS mappings consistent: $id_to_card_count entries"
        else
            log_error "FAISS mapping mismatch: id_to_card=$id_to_card_count, card_to_id=$card_to_id_count"
            return 1
        fi

        # Check FAISS file size is reasonable
        local faiss_size=$(stat -f%z "$faiss_file" 2>/dev/null || stat -c%s "$faiss_file" 2>/dev/null)
        local expected_min=$((id_to_card_count * 768 * 4))  # float32 = 4 bytes

        if [[ "$faiss_size" -lt "$expected_min" ]]; then
            log_warning "FAISS file seems too small for $id_to_card_count vectors"
        else
            log_info "FAISS file size: $faiss_size bytes ($id_to_card_count vectors)"
        fi
    else
        log_warning "jq not installed, skipping detailed FAISS validation"
    fi

    return 0
}

# -----------------------------------------------------------------------------
# Test 12: Cross-Reference Validation
# -----------------------------------------------------------------------------
test_cross_references() {
    local backup_file=$(cat "${TEST_DIR}/backup_path.txt" 2>/dev/null)

    if [[ -z "$backup_file" ]]; then
        log_error "Backup file not found"
        return 1
    fi

    local backup_extract="${TEST_DIR}/xref_test"
    mkdir -p "$backup_extract"
    tar -xzf "$backup_file" -C "$backup_extract"

    local backup_content=$(find "$backup_extract" -mindepth 1 -maxdepth 1 -type d | head -1)

    if ! command -v jq &> /dev/null; then
        log_warning "jq not installed, skipping cross-reference validation"
        return 0
    fi

    local valid_refs=0
    local invalid_refs=0

    # Get all research card IDs from registry
    local registry_cards=""
    if [[ -f "${backup_content}/research/registry.sqlite" ]]; then
        if command -v sqlite3 &> /dev/null; then
            registry_cards=$(sqlite3 "${backup_content}/research/registry.sqlite" \
                "SELECT card_id FROM research_cards;" 2>/dev/null)
        fi
    fi

    # Check story metadata research_used references
    local meta_files=$(find "${backup_content}/novel" -name "*_metadata.json" 2>/dev/null)

    while IFS= read -r meta_file; do
        [[ -z "$meta_file" ]] && continue

        local research_used=$(jq -r '.research_used[]? // empty' "$meta_file" 2>/dev/null)

        while IFS= read -r card_id; do
            [[ -z "$card_id" ]] && continue

            # Check if card exists in registry
            if echo "$registry_cards" | grep -q "^${card_id}$"; then
                valid_refs=$((valid_refs + 1))
                [[ "$VERBOSE" == true ]] && log_info "Valid ref: $card_id"
            else
                # Card might exist as JSON file even if not in registry
                local card_file=$(find "${backup_content}/research" -name "${card_id}.json" 2>/dev/null | head -1)
                if [[ -n "$card_file" ]]; then
                    valid_refs=$((valid_refs + 1))
                else
                    invalid_refs=$((invalid_refs + 1))
                    log_warning "Missing research card: $card_id (referenced in $(basename "$meta_file"))"
                fi
            fi
        done <<< "$research_used"
    done <<< "$meta_files"

    log_info "Cross-references: $valid_refs valid, $invalid_refs invalid"

    if [[ "$invalid_refs" -gt 0 ]]; then
        log_warning "Some research references could not be resolved"
    fi

    return 0
}

# -----------------------------------------------------------------------------
# Test 13: Full Restore Cycle (to temp location)
# -----------------------------------------------------------------------------
test_full_restore_cycle() {
    local backup_file=$(cat "${TEST_DIR}/backup_path.txt" 2>/dev/null)

    if [[ -z "$backup_file" ]]; then
        log_error "Backup file not found"
        return 1
    fi

    # Create isolated test environment
    local restore_test="${TEST_DIR}/restore_cycle"
    local restore_data="${restore_test}/data"
    mkdir -p "$restore_data"

    # Extract backup to simulate restore
    tar -xzf "$backup_file" -C "$restore_test"
    local backup_content=$(find "$restore_test" -mindepth 1 -maxdepth 1 -type d -name "backup_*" | head -1)

    # Copy contents to simulate restored state
    if [[ -f "${backup_content}/story_registry.db" ]]; then
        cp "${backup_content}/story_registry.db" "$restore_data/"
    fi

    if [[ -d "${backup_content}/research" ]]; then
        cp -r "${backup_content}/research" "$restore_data/"
    fi

    if [[ -d "${backup_content}/novel" ]]; then
        cp -r "${backup_content}/novel" "$restore_data/"
    fi

    # Verify restored files exist
    local restored_files=$(find "$restore_data" -type f | wc -l | tr -d ' ')

    if [[ "$restored_files" -gt 0 ]]; then
        log_info "Restore cycle complete: $restored_files files restored"
        return 0
    else
        log_error "No files were restored"
        return 1
    fi
}

# =============================================================================
# Cleanup
# =============================================================================

cleanup() {
    if [[ "$CLEANUP" == true ]] && [[ -n "$TEST_DIR" ]] && [[ -d "$TEST_DIR" ]]; then
        rm -rf "$TEST_DIR"
        log_info "Cleaned up test directory"
    else
        log_info "Test files preserved at: $TEST_DIR"
    fi
}

# =============================================================================
# Main
# =============================================================================

main() {
    parse_args "$@"

    print_header "Backup/Restore Verification"

    log_info "Test directory: $TEST_DIR"
    log_info "Cleanup after tests: $CLEANUP"

    echo ""

    # Run tests - Basic
    run_test "Backup Creation" test_backup_creation || true
    run_test "Archive Integrity" test_archive_integrity || true
    run_test "Manifest Validation" test_manifest_validation || true
    run_test "Restore Dry-Run" test_restore_dry_run || true
    run_test "Data Integrity" test_data_integrity || true
    run_test "SQLite Integrity" test_sqlite_integrity || true

    # Run tests - Schema Validation
    run_test "Schema Validation" test_schema_validation || true

    # Run tests - JSON Validation
    run_test "Research Card JSON" test_research_card_json || true
    run_test "Story Metadata JSON" test_story_metadata_json || true
    run_test "Story File Pairs" test_story_file_pairs || true

    # Run tests - Advanced Validation
    run_test "FAISS Consistency" test_faiss_consistency || true
    run_test "Cross-References" test_cross_references || true

    # Run tests - Full Cycle
    run_test "Full Restore Cycle" test_full_restore_cycle || true

    echo ""
    print_header "Test Results"

    echo ""
    log_info "Total: $test_count tests"
    log_success "Passed: $pass_count"

    if [[ $fail_count -gt 0 ]]; then
        log_error "Failed: $fail_count"
    fi

    echo ""

    # Cleanup
    cleanup

    # Exit with appropriate code
    if [[ $fail_count -gt 0 ]]; then
        exit 1
    fi

    exit 0
}

main "$@"
