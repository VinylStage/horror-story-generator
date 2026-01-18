#!/bin/bash
# =============================================================================
# Restore Script
# Horror Story Generator - Unified Restore System
# Version: 1.0.0
# =============================================================================

set -e

# Load configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/backup_config.sh"

# =============================================================================
# Default Options
# =============================================================================

BACKUP_FILE=""
DRY_RUN=false
FORCE=false
RESTORE_COMPONENT=""
VERBOSE=false

# =============================================================================
# Usage
# =============================================================================

show_usage() {
    cat << EOF
Usage: $(basename "$0") <backup_file> [OPTIONS]

Restore Horror Story Generator data from backup.

ARGUMENTS:
    backup_file           Path to backup file (.tar.gz) or directory

OPTIONS:
    --dry-run             Show what would be restored without doing it
    --force               Overwrite existing data without confirmation
    --component <name>    Restore only specific component
                          (story-registry, research, stories, story-vectors, seeds)
    --verbose             Show detailed output
    -h, --help            Show this help message

EXAMPLES:
    $(basename "$0") backups/backup_20260118_120000.tar.gz
    $(basename "$0") backups/backup_20260118_120000 --dry-run
    $(basename "$0") backup.tar.gz --component story-registry
    $(basename "$0") backup.tar.gz --force

EOF
}

# =============================================================================
# Parse Arguments
# =============================================================================

parse_args() {
    if [[ $# -eq 0 ]]; then
        show_usage
        exit 1
    fi

    # First argument is the backup file
    BACKUP_FILE="$1"
    shift

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --force)
                FORCE=true
                shift
                ;;
            --component)
                RESTORE_COMPONENT="$2"
                shift 2
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

    # Validate backup file
    if [[ ! -e "$BACKUP_FILE" ]]; then
        log_error "Backup file not found: $BACKUP_FILE"
        exit 1
    fi

    # Validate component if specified
    if [[ -n "$RESTORE_COMPONENT" ]]; then
        local valid=false
        for comp in "${ALL_COMPONENTS[@]}"; do
            if [[ "$comp" == "$RESTORE_COMPONENT" ]]; then
                valid=true
                break
            fi
        done
        if [[ "$valid" == false ]]; then
            log_error "Invalid component: $RESTORE_COMPONENT"
            log_info "Valid components: ${ALL_COMPONENTS[*]}"
            exit 1
        fi
    fi
}

# =============================================================================
# Restore Functions
# =============================================================================

# Extract backup if compressed
extract_backup() {
    local backup_file="$1"
    local temp_dir=""

    if [[ -d "$backup_file" ]]; then
        # Already a directory
        echo "$backup_file"
        return
    fi

    if [[ "$backup_file" == *.tar.gz ]] || [[ "$backup_file" == *.tgz ]]; then
        # Log to stderr to not pollute return value
        log_step "Extracting backup archive..." >&2

        temp_dir=$(mktemp -d)
        tar -xzf "$backup_file" -C "$temp_dir"

        # Find the extracted directory
        local extracted_dir=$(find "$temp_dir" -mindepth 1 -maxdepth 1 -type d | head -1)

        if [[ -z "$extracted_dir" ]]; then
            log_error "Failed to extract backup" >&2
            rm -rf "$temp_dir"
            exit 1
        fi

        echo "$extracted_dir"
    else
        log_error "Unsupported backup format: $backup_file" >&2
        exit 1
    fi
}

# Read manifest
read_manifest() {
    local backup_path="$1"
    local manifest_file="${backup_path}/manifest.json"

    if [[ ! -f "$manifest_file" ]]; then
        log_warning "No manifest.json found in backup"
        return 1
    fi

    if command -v jq &> /dev/null; then
        log_info "Backup Version: $(jq -r '.backup_version' "$manifest_file")"
        log_info "Created At: $(jq -r '.created_at' "$manifest_file")"
        log_info "App Version: $(jq -r '.app_version' "$manifest_file")"

        echo ""
        log_info "Components in backup:"
        jq -r '.components | to_entries[] | "  - \(.key): \(.value.files) files, \(.value.size_bytes) bytes"' "$manifest_file"
    else
        log_info "Manifest found (install jq for detailed info)"
        cat "$manifest_file"
    fi

    return 0
}

# Check what would be overwritten
check_conflicts() {
    local backup_path="$1"
    local components=("$@")
    local has_conflicts=false

    echo ""
    log_info "Checking for existing data..."

    for component in "${components[@]}"; do
        [[ "$component" == "$backup_path" ]] && continue

        if component_exists "$component"; then
            local path=$(get_component_path "$component")
            local size=$(get_dir_size_human "$path")
            echo -e "  ${YELLOW}⚠${NC} $component exists ($size) - will be overwritten"
            has_conflicts=true
        fi
    done

    if [[ "$has_conflicts" == true ]] && [[ "$FORCE" == false ]] && [[ "$DRY_RUN" == false ]]; then
        echo ""
        read -p "Existing data will be overwritten. Continue? [y/N] " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "Restore cancelled"
            exit 0
        fi
    fi
}

# Restore a single component
restore_component() {
    local component="$1"
    local backup_path="$2"
    local target_path=$(get_component_path "$component")

    if [[ -z "$target_path" ]]; then
        log_warning "Unknown component: $component"
        return 1
    fi

    # Check if component exists in backup
    local backup_component_path=""
    case "$component" in
        "story-registry")
            backup_component_path="${backup_path}/story_registry.db"
            ;;
        "research")
            backup_component_path="${backup_path}/research"
            ;;
        "stories")
            backup_component_path="${backup_path}/novel"
            ;;
        "story-vectors")
            backup_component_path="${backup_path}/story_vectors"
            ;;
        "seeds")
            backup_component_path="${backup_path}/seeds"
            ;;
    esac

    if [[ ! -e "$backup_component_path" ]]; then
        log_warning "Component not found in backup: $component"
        return 0
    fi

    local size=$(get_dir_size_human "$backup_component_path")

    if [[ "$DRY_RUN" == true ]]; then
        log_info "[DRY-RUN] Would restore: $component ($size)"
        return 0
    fi

    log_step "Restoring: $component ($size)"

    # Create backup of current data if exists
    if [[ -e "$target_path" ]]; then
        local timestamp=$(date +"$DATE_FORMAT")
        local current_backup="${target_path}.pre_restore.${timestamp}"

        if [[ "$component" == "story-registry" ]]; then
            cp "$target_path" "$current_backup"
        else
            mv "$target_path" "$current_backup"
        fi

        log_info "Current data backed up to: $current_backup"
    fi

    # Restore from backup
    if [[ "$component" == "story-registry" ]]; then
        # Ensure parent directory exists
        mkdir -p "$(dirname "$target_path")"
        cp "$backup_component_path" "$target_path"
    else
        # Ensure parent directory exists
        mkdir -p "$(dirname "$target_path")"
        cp -r "$backup_component_path" "$target_path"
    fi

    log_success "Restored: $component"
}

# =============================================================================
# Main
# =============================================================================

main() {
    parse_args "$@"

    print_header "Horror Story Generator Restore"

    log_info "Backup file: $BACKUP_FILE"

    if [[ "$DRY_RUN" == true ]]; then
        echo ""
        log_warning "DRY-RUN MODE - No files will be modified"
    fi

    echo ""

    # Extract backup if needed
    local backup_path=$(extract_backup "$BACKUP_FILE")
    local temp_extracted=false

    if [[ "$backup_path" != "$BACKUP_FILE" ]]; then
        temp_extracted=true
    fi

    # Read and display manifest
    read_manifest "$backup_path" || true

    echo ""

    # Determine which components to restore
    local components_to_restore=()
    if [[ -n "$RESTORE_COMPONENT" ]]; then
        components_to_restore=("$RESTORE_COMPONENT")
    else
        components_to_restore=("${ALL_COMPONENTS[@]}")
    fi

    log_info "Components to restore: ${components_to_restore[*]}"

    # Check for conflicts
    check_conflicts "$backup_path" "${components_to_restore[@]}"

    echo ""

    # Restore each component
    for component in "${components_to_restore[@]}"; do
        restore_component "$component" "$backup_path"
    done

    # Cleanup temporary directory
    if [[ "$temp_extracted" == true ]] && [[ "$DRY_RUN" == false ]]; then
        rm -rf "$(dirname "$backup_path")"
    fi

    echo ""

    if [[ "$DRY_RUN" == true ]]; then
        log_success "Dry-run complete. No files were modified."
    else
        print_header "Restore Complete"

        echo ""
        log_info "Summary:"
        for component in "${components_to_restore[@]}"; do
            local target_path=$(get_component_path "$component")
            if [[ -e "$target_path" ]]; then
                local size=$(get_dir_size_human "$target_path")
                echo -e "  ${GREEN}✓${NC} $component ($size)"
            else
                echo -e "  ${YELLOW}○${NC} $component (not restored)"
            fi
        done

        echo ""
        log_warning "Please verify your application works correctly after restore."
    fi

    echo ""
}

main "$@"
