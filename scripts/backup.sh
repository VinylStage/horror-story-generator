#!/bin/bash
# =============================================================================
# Backup Script
# Horror Story Generator - Unified Backup System
# Version: 1.0.0
# =============================================================================

set -e

# Load configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/backup_config.sh"

# =============================================================================
# Default Options
# =============================================================================

BACKUP_ALL=true
BACKUP_COMPONENTS=()
OUTPUT_DIR=""
COMPRESS=false
DRY_RUN=false
VERBOSE=false

# =============================================================================
# Usage
# =============================================================================

show_usage() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]

Backup Horror Story Generator data.

OPTIONS:
    --all                 Backup all components (default)
    --story-registry      Backup story registry database only
    --research            Backup research data only (DB + FAISS + cards)
    --stories             Backup generated stories only
    --story-vectors       Backup story vector index only
    --seeds               Backup seed data only
    --output <path>       Output directory (default: ./backups)
    --compress            Create compressed tar.gz archive
    --dry-run             Show what would be backed up without doing it
    --verbose             Show detailed output
    -h, --help            Show this help message

EXAMPLES:
    $(basename "$0")                      # Full backup to ./backups
    $(basename "$0") --compress           # Full backup with compression
    $(basename "$0") --story-registry     # Backup only story registry
    $(basename "$0") --research --stories # Backup research and stories
    $(basename "$0") --dry-run            # Preview backup

EOF
}

# =============================================================================
# Parse Arguments
# =============================================================================

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --all)
                BACKUP_ALL=true
                shift
                ;;
            --story-registry)
                BACKUP_ALL=false
                BACKUP_COMPONENTS+=("story-registry")
                shift
                ;;
            --research)
                BACKUP_ALL=false
                BACKUP_COMPONENTS+=("research")
                shift
                ;;
            --stories)
                BACKUP_ALL=false
                BACKUP_COMPONENTS+=("stories")
                shift
                ;;
            --story-vectors)
                BACKUP_ALL=false
                BACKUP_COMPONENTS+=("story-vectors")
                shift
                ;;
            --seeds)
                BACKUP_ALL=false
                BACKUP_COMPONENTS+=("seeds")
                shift
                ;;
            --output)
                OUTPUT_DIR="$2"
                shift 2
                ;;
            --compress)
                COMPRESS=true
                shift
                ;;
            --dry-run)
                DRY_RUN=true
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

    # Set default output directory
    if [[ -z "$OUTPUT_DIR" ]]; then
        OUTPUT_DIR="$BACKUP_DIR"
    fi

    # If backing up all, use all components
    if [[ "$BACKUP_ALL" == true ]]; then
        BACKUP_COMPONENTS=("${ALL_COMPONENTS[@]}")
    fi
}

# =============================================================================
# Backup Functions
# =============================================================================

# Create manifest.json
create_manifest() {
    local backup_path="$1"
    local manifest_file="${backup_path}/manifest.json"
    local app_version=$(get_app_version)
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    # Build components JSON
    local components_json="{"
    local first=true

    for component in "${BACKUP_COMPONENTS[@]}"; do
        if component_exists "$component"; then
            local path=$(get_component_path "$component")
            local file_count=$(get_file_count "$path")
            local size_bytes=$(get_dir_size "$path")

            if [[ "$first" == true ]]; then
                first=false
            else
                components_json+=","
            fi

            components_json+="\"${component}\":{\"files\":${file_count},\"size_bytes\":${size_bytes}}"
        fi
    done

    components_json+="}"

    # Write manifest
    cat > "$manifest_file" << EOF
{
  "backup_version": "${BACKUP_VERSION}",
  "created_at": "${timestamp}",
  "app_version": "${app_version}",
  "components": ${components_json},
  "checksum": "pending"
}
EOF

    echo "$manifest_file"
}

# Backup a single component
backup_component() {
    local component="$1"
    local backup_path="$2"
    local source_path=$(get_component_path "$component")

    if [[ -z "$source_path" ]]; then
        log_warning "Unknown component: $component"
        return 1
    fi

    if ! component_exists "$component"; then
        log_warning "Component not found or empty: $component ($source_path)"
        return 0
    fi

    local size=$(get_dir_size_human "$source_path")

    if [[ "$DRY_RUN" == true ]]; then
        log_info "[DRY-RUN] Would backup: $component ($size)"
        return 0
    fi

    log_step "Backing up: $component ($size)"

    if [[ "$component" == "story-registry" ]]; then
        # Single file backup
        cp "$source_path" "${backup_path}/"
    else
        # Directory backup
        cp -r "$source_path" "${backup_path}/"
    fi

    log_success "Backed up: $component"
}

# Create compressed archive
create_archive() {
    local backup_path="$1"
    local archive_name="$2"

    log_step "Creating compressed archive..."

    local parent_dir=$(dirname "$backup_path")
    local backup_name=$(basename "$backup_path")

    cd "$parent_dir"
    tar -czf "${archive_name}" "$backup_name"
    cd - > /dev/null

    # Calculate checksum
    local checksum=$(calculate_checksum "${parent_dir}/${archive_name}")

    # Update manifest with checksum (in the archive)
    # For now, create a separate checksum file
    echo "sha256:${checksum}" > "${parent_dir}/${archive_name}.sha256"

    # Remove uncompressed backup
    rm -rf "$backup_path"

    log_success "Archive created: ${parent_dir}/${archive_name}"
    log_info "Checksum: sha256:${checksum}"
}

# =============================================================================
# Main
# =============================================================================

main() {
    parse_args "$@"

    print_header "Horror Story Generator Backup"

    # Show configuration
    log_info "Project root: $PROJECT_ROOT"
    log_info "Output directory: $OUTPUT_DIR"
    log_info "Components: ${BACKUP_COMPONENTS[*]}"
    log_info "Compress: $COMPRESS"

    if [[ "$DRY_RUN" == true ]]; then
        echo ""
        log_warning "DRY-RUN MODE - No files will be modified"
        echo ""
    fi

    # Check if any data exists
    local has_data=false
    for component in "${BACKUP_COMPONENTS[@]}"; do
        if component_exists "$component"; then
            has_data=true
            break
        fi
    done

    if [[ "$has_data" == false ]]; then
        log_error "No data found to backup"
        exit 1
    fi

    # Create backup directory
    ensure_backup_dir
    if [[ "$OUTPUT_DIR" != "$BACKUP_DIR" ]]; then
        mkdir -p "$OUTPUT_DIR"
    fi

    # Create timestamped backup folder
    local timestamp=$(date +"$DATE_FORMAT")
    local backup_name="backup_${timestamp}"
    local backup_path="${OUTPUT_DIR}/${backup_name}"

    if [[ "$DRY_RUN" == false ]]; then
        mkdir -p "$backup_path"
        log_info "Backup path: $backup_path"
    fi

    echo ""

    # Backup each component
    for component in "${BACKUP_COMPONENTS[@]}"; do
        backup_component "$component" "$backup_path"
    done

    echo ""

    if [[ "$DRY_RUN" == true ]]; then
        log_success "Dry-run complete. No files were modified."
        exit 0
    fi

    # Create manifest
    log_step "Creating manifest..."
    create_manifest "$backup_path"
    log_success "Manifest created"

    # Compress if requested
    if [[ "$COMPRESS" == true ]]; then
        echo ""
        create_archive "$backup_path" "${backup_name}.tar.gz"
        log_info "Final backup: ${OUTPUT_DIR}/${backup_name}.tar.gz"
    else
        # Calculate checksum for uncompressed backup
        local manifest_file="${backup_path}/manifest.json"
        local checksum=$(calculate_checksum "$manifest_file")

        # Update manifest with checksum
        if command -v jq &> /dev/null; then
            jq --arg cs "sha256:${checksum}" '.checksum = $cs' "$manifest_file" > "${manifest_file}.tmp"
            mv "${manifest_file}.tmp" "$manifest_file"
        fi

        log_info "Final backup: $backup_path"
    fi

    echo ""
    print_header "Backup Complete"

    # Summary
    echo ""
    log_info "Summary:"
    for component in "${BACKUP_COMPONENTS[@]}"; do
        if component_exists "$component"; then
            local path=$(get_component_path "$component")
            local size=$(get_dir_size_human "$path")
            echo -e "  ${GREEN}✓${NC} $component ($size)"
        else
            echo -e "  ${YELLOW}○${NC} $component (skipped - not found)"
        fi
    done

    echo ""
}

main "$@"
