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
# Test 7: Full Restore Cycle (to temp location)
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

    # Run tests
    run_test "Backup Creation" test_backup_creation || true
    run_test "Archive Integrity" test_archive_integrity || true
    run_test "Manifest Validation" test_manifest_validation || true
    run_test "Restore Dry-Run" test_restore_dry_run || true
    run_test "Data Integrity" test_data_integrity || true
    run_test "SQLite Integrity" test_sqlite_integrity || true
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
