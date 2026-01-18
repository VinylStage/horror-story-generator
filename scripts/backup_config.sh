#!/bin/bash
# =============================================================================
# Backup Configuration
# Horror Story Generator - Unified Backup/Restore System
# Version: 1.0.0
# =============================================================================

# Script directory (resolve symlinks)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# =============================================================================
# Directory Paths
# =============================================================================

DATA_DIR="${PROJECT_ROOT}/data"
BACKUP_DIR="${PROJECT_ROOT}/backups"

# Data components
STORY_REGISTRY_DB="${DATA_DIR}/story_registry.db"
RESEARCH_DIR="${DATA_DIR}/research"
NOVEL_DIR="${DATA_DIR}/novel"
STORY_VECTORS_DIR="${DATA_DIR}/story_vectors"
SEEDS_DIR="${DATA_DIR}/seeds"

# =============================================================================
# Backup Settings
# =============================================================================

BACKUP_VERSION="1.0.0"
DATE_FORMAT="%Y%m%d_%H%M%S"

# =============================================================================
# Colors for output
# =============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# =============================================================================
# Helper Functions
# =============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${CYAN}[STEP]${NC} $1"
}

# Print header
print_header() {
    echo -e "${BOLD}========================================${NC}"
    echo -e "${BOLD}$1${NC}"
    echo -e "${BOLD}========================================${NC}"
}

# Check if directory exists and is not empty
dir_exists_and_not_empty() {
    local dir="$1"
    if [[ -d "$dir" ]] && [[ -n "$(ls -A "$dir" 2>/dev/null)" ]]; then
        return 0
    fi
    return 1
}

# Get file count in directory
get_file_count() {
    local dir="$1"
    if [[ -d "$dir" ]]; then
        find "$dir" -type f 2>/dev/null | wc -l | tr -d ' '
    else
        echo "0"
    fi
}

# Get directory size in bytes
get_dir_size() {
    local dir="$1"
    if [[ -d "$dir" ]]; then
        # macOS doesn't support -b flag, use -k and multiply
        if du -sb "$dir" &>/dev/null; then
            du -sb "$dir" 2>/dev/null | cut -f1
        else
            # macOS: du -sk gives KB, multiply by 1024
            echo $(( $(du -sk "$dir" 2>/dev/null | cut -f1) * 1024 ))
        fi
    elif [[ -f "$dir" ]]; then
        # Try macOS stat first, then Linux
        stat -f%z "$dir" 2>/dev/null || stat -c%s "$dir" 2>/dev/null || echo "0"
    else
        echo "0"
    fi
}

# Get directory size human readable
get_dir_size_human() {
    local dir="$1"
    if [[ -d "$dir" ]]; then
        du -sh "$dir" 2>/dev/null | cut -f1
    elif [[ -f "$dir" ]]; then
        ls -lh "$dir" 2>/dev/null | awk '{print $5}'
    else
        echo "0"
    fi
}

# Calculate SHA256 checksum
calculate_checksum() {
    local file="$1"
    if command -v sha256sum &> /dev/null; then
        sha256sum "$file" | cut -d' ' -f1
    elif command -v shasum &> /dev/null; then
        shasum -a 256 "$file" | cut -d' ' -f1
    else
        echo "checksum_unavailable"
    fi
}

# Get app version from pyproject.toml
get_app_version() {
    if [[ -f "${PROJECT_ROOT}/pyproject.toml" ]]; then
        grep -E '^version\s*=' "${PROJECT_ROOT}/pyproject.toml" | head -1 | sed 's/.*"\([^"]*\)".*/\1/'
    else
        echo "unknown"
    fi
}

# Ensure backup directory exists
ensure_backup_dir() {
    if [[ ! -d "$BACKUP_DIR" ]]; then
        mkdir -p "$BACKUP_DIR"
        log_info "Created backup directory: $BACKUP_DIR"
    fi
}

# =============================================================================
# Component Definitions
# =============================================================================

# Array of all components
ALL_COMPONENTS=("story-registry" "research" "stories" "story-vectors" "seeds")

# Get component path
get_component_path() {
    local component="$1"
    case "$component" in
        "story-registry") echo "$STORY_REGISTRY_DB" ;;
        "research") echo "$RESEARCH_DIR" ;;
        "stories") echo "$NOVEL_DIR" ;;
        "story-vectors") echo "$STORY_VECTORS_DIR" ;;
        "seeds") echo "$SEEDS_DIR" ;;
        *) echo "" ;;
    esac
}

# Check if component exists
component_exists() {
    local component="$1"
    local path=$(get_component_path "$component")

    if [[ -z "$path" ]]; then
        return 1
    fi

    if [[ "$component" == "story-registry" ]]; then
        [[ -f "$path" ]]
    else
        dir_exists_and_not_empty "$path"
    fi
}
