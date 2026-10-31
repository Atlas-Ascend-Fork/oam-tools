#!/bin/bash
# ----------------------------------------------------------------------------
# Copyright (c) 2025 Huawei Technologies Co., Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ----------------------------------------------------------------------------

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

CANN_VERSION="${CANN_VERSION:-}"
CHIP_TYPE="910b"
CANN_BASE_URL="https://ascend.devcloud.huaweicloud.com/artifactory/cann-run/software"
OAM_TOOLS_RAW_BASE_URL="${OAM_TOOLS_RAW_BASE_URL:-https://raw.gitcode.com/cann/oam-tools/raw/master}"
# Whitelist of official download hosts; executable .run packages must come from these (security).
ALLOWED_DOWNLOAD_HOSTS="ascend.devcloud.huaweicloud.com raw.gitcode.com"
if [ -z "${INSTALL_PATH:-}" ]; then
    if [ "$(id -u)" -eq 0 ]; then
        INSTALL_PATH="/usr/local/Ascend"
    else
        INSTALL_PATH="${HOME}/Ascend"
    fi
fi
SKIP_OPS="false"

log_info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

check_command() { command -v "$1" &>/dev/null; }

get_url_host() {
    local host="$1"
    host="${host#*://}"
    host="${host%%[/?#]*}"
    host="${host##*@}"
    host="${host%%:*}"
    printf '%s' "$host"
}

# validate_download_url <url> <label> [strict|advisory]
# strict (default): the URL must be https:// and its host must be in
#   ALLOWED_DOWNLOAD_HOSTS; used for everything that gets executed.
# advisory: https:// is still mandatory, but a non-whitelisted host (only
#   possible via user-supplied OAM_TOOLS_RAW_BASE_URL) only triggers a warning.
validate_download_url() {
    local url="$1"
    local label="$2"
    local mode="${3:-strict}"
    local host allowed

    case "$url" in
        https://*) ;;
        *)
            log_error "${label}: non-HTTPS download URL is not allowed: ${url}"
            return 1
            ;;
    esac

    host=$(get_url_host "$url")
    for allowed in $ALLOWED_DOWNLOAD_HOSTS; do
        if [ "$host" = "$allowed" ]; then
            return 0
        fi
    done

    if [ "$mode" = "advisory" ]; then
        log_warn "${label}: '${host}' is not an official source (allowed: ${ALLOWED_DOWNLOAD_HOSTS})"
        log_warn "Make sure you trust this source before using the fetched content"
        return 0
    fi

    log_error "${label}: download host '${host}' is not in the allowed source whitelist: ${ALLOWED_DOWNLOAD_HOSTS}"
    return 1
}

# verify_run_package <pkg_path> <pkg_url> <label>
# Downloads the official sha256 checksum published next to the package and
# verifies the package digest over HTTPS. A package that cannot be verified
# is never executed.
verify_run_package() {
    local pkg_path="$1"
    local pkg_url="$2"
    local label="$3"
    local checksum_file="${pkg_path}.sha256"
    local expected actual

    check_command sha256sum || {
        log_error "sha256sum is required to verify ${label}"
        return 1
    }

    log_info "Verifying ${label} (sha256)..."
    curl -fsSL --connect-timeout 15 --retry 2 "${pkg_url}.sha256" -o "$checksum_file" || {
        rm -f "$checksum_file"
        log_error "Failed to fetch official checksum: ${pkg_url}.sha256"
        log_error "Refusing to execute unverified package: ${pkg_path}"
        return 1
    }

    expected=$(tr -d '[:space:]' < "$checksum_file" | tr '[:upper:]' '[:lower:]')
    if ! printf '%s' "$expected" | grep -qE '^[0-9a-f]{64}$'; then
        rm -f "$checksum_file"
        log_error "Invalid sha256 checksum format for ${label}: ${pkg_url}.sha256"
        return 1
    fi

    actual=$(sha256sum "$pkg_path" | awk '{print $1}')
    if [ "$actual" != "$expected" ]; then
        rm -f "$checksum_file" "$pkg_path"
        log_error "sha256 mismatch for ${label}: expected ${expected}, got ${actual}"
        log_error "Package is corrupted or tampered with; it has been removed: ${pkg_path}"
        return 1
    fi

    rm -f "$checksum_file"
    log_info "${label} integrity verified"
    return 0
}

is_root_user() { [ "$(id -u)" -eq 0 ]; }

get_missing_required_system_deps() {
    local missing_deps=""

    check_command curl || missing_deps="${missing_deps} curl"
    check_command wget || missing_deps="${missing_deps} wget"
    check_command git || missing_deps="${missing_deps} git"
    check_command cmake || missing_deps="${missing_deps} cmake"
    check_command make || missing_deps="${missing_deps} make"
    check_command g++ || missing_deps="${missing_deps} g++"

    printf '%s' "${missing_deps# }"
}

get_cann_version_from_cmake() {
    local version_file="$1"
    local version=""
    local version_content=""

    if [ -f "$version_file" ]; then
        version_content=$(cat "$version_file")
    else
        if ! check_command curl; then
            log_error "version.cmake not found and curl is unavailable: $version_file" >&2
            return 1
        fi
        log_warn "version.cmake not found locally, fetching from ${OAM_TOOLS_RAW_BASE_URL}/version.cmake" >&2
        validate_download_url "${OAM_TOOLS_RAW_BASE_URL}/version.cmake" "version.cmake download" advisory 1>&2 || return 1
        version_content=$(curl -fsSL "${OAM_TOOLS_RAW_BASE_URL}/version.cmake") || {
            log_error "Failed to fetch version.cmake" >&2
            return 1
        }
    fi

    version=$(printf '%s\n' "$version_content" | sed -nE 's/^[[:space:]]*set_cann_package[[:space:]]*\([^)]*VERSION[[:space:]]+"([^"]+)".*/\1/p' | head -n 1)
    if [ -z "$version" ]; then
        log_error "Failed to parse CANN version from version.cmake" >&2
        return 1
    fi

    echo "$version"
}

get_ops_package_chip_type() {
    case "$1" in
        910_93|910c|910C|910_c|910_C|A3|a3)
            echo "A3"
            ;;
        910B|910b)
            echo "910b"
            ;;
        950)
            echo "950"
            ;;
        *)
            echo "$1"
            ;;
    esac
}

get_arch() {
    local arch=$(uname -m)
    case $arch in
        x86_64) echo "x86_64" ;;
        aarch64) echo "aarch64" ;;
        *) log_error "Unsupported architecture: $arch"; return 1 ;;
    esac
}

detect_cann_path() {
    local paths=(
        "/usr/local/Ascend/ascend-toolkit/latest"
        "/usr/local/Ascend/latest"
        "/usr/local/Ascend/cann-${CANN_VERSION}"
        "/usr/local/Ascend/cann-${CANN_VERSION}-beta.1"
        "/usr/local/Ascend/cann"
        "$HOME/Ascend/ascend-toolkit/latest"
        "$HOME/Ascend/latest"
        "$HOME/Ascend/cann-${CANN_VERSION}"
        "$HOME/Ascend/cann-${CANN_VERSION}-beta.1"
        "$HOME/Ascend/cann"
    )

    for p in "${paths[@]}"; do
        if [ -d "$p" ] && [ -f "$p/bin/setenv.bash" ]; then
            echo "$p"
            return 0
        fi
    done

    if [ -d "/usr/local/Ascend" ]; then
        for d in /usr/local/Ascend/ascend-toolkit/*; do
            [ -d "$d" ] && [ -f "$d/bin/setenv.bash" ] && echo "$d" && return 0
        done
        for d in /usr/local/Ascend/cann-*; do
            [ -d "$d" ] && [ -f "$d/bin/setenv.bash" ] && echo "$d" && return 0
        done
    fi
    return 1
}

install_cann() {
    log_info "Checking CANN installation..."

    local existing_cann=$(detect_cann_path)
    if [ -n "$existing_cann" ]; then
        log_info "CANN already installed at: $existing_cann"
        return 0
    fi

    log_info "CANN not found, starting installation..."
    log_warn "This will download ~3GB of packages"

    local arch=$(get_arch)
    local previous_dir="$PWD"
    local download_dir
    download_dir=$(mktemp -d "${TMPDIR:-/tmp}/cann_install.XXXXXX") || {
        log_error "Failed to create private CANN download directory"
        return 1
    }
    chmod 700 "$download_dir"
    # shellcheck disable=SC2064  # expand the private path now, before any cd
    trap 'rm -rf -- "$download_dir"' RETURN
    trap 'rm -rf -- "$download_dir"; exit 130' INT TERM HUP QUIT
    cd "$download_dir"

    local ops_package_chip_type=$(get_ops_package_chip_type "$CHIP_TYPE")
    local toolkit_pkg="Ascend-cann-toolkit_${CANN_VERSION}_linux-${arch}.run"
    local ops_pkg="Ascend-cann-${ops_package_chip_type}-ops_${CANN_VERSION}_linux-${arch}.run"
    local toolkit_url="${CANN_BASE_URL}/${CANN_VERSION}/${arch}/${toolkit_pkg}"
    local ops_url="${CANN_BASE_URL}/${CANN_VERSION}/${arch}/${ops_pkg}"

    validate_download_url "$toolkit_url" "CANN toolkit download" || return 1
    if [ ! -f "$toolkit_pkg" ]; then
        log_info "Downloading CANN toolkit (${arch})..."
        log_info "URL: $toolkit_url"
        wget -q --show-progress -O "$toolkit_pkg" "$toolkit_url" || {
            rm -f "$toolkit_pkg"
            log_error "Failed to download toolkit"
            return 1
        }
    fi
    verify_run_package "${download_dir}/${toolkit_pkg}" "$toolkit_url" "CANN toolkit package" || return 1

    if [ "$SKIP_OPS" = "false" ]; then
        validate_download_url "$ops_url" "CANN ops download" || return 1
        if [ ! -f "$ops_pkg" ]; then
            log_info "Downloading CANN ops (${ops_package_chip_type}, ${arch})..."
            log_info "URL: $ops_url"
            wget -q --show-progress -O "$ops_pkg" "$ops_url" || {
                rm -f "$ops_pkg"
                log_error "Failed to download ops"
                return 1
            }
        fi
        verify_run_package "${download_dir}/${ops_pkg}" "$ops_url" "CANN ops package" || return 1
    fi

    log_info "Installing CANN toolkit..."
    chmod +x "$toolkit_pkg"
    ./$toolkit_pkg --full --install-path="$INSTALL_PATH" || {
        log_error "Failed to install toolkit"
        return 1
    }

    if [ "$SKIP_OPS" = "false" ]; then
        log_info "Installing CANN ops..."
        chmod +x "$ops_pkg"
        ./$ops_pkg --install --install-path="$INSTALL_PATH" || {
            log_warn "Ops installation may have issues (this can be normal on non-NPU systems)"
        }
    fi

    log_info "Cleaning up..."
    cd "$previous_dir"
    trap - INT TERM HUP QUIT

    log_info "CANN installation completed"
}

setup_cann_env() {
    log_info "Setting up CANN environment..."

    CANN_PATH=$(detect_cann_path)
    if [ -z "$CANN_PATH" ]; then
        log_error "CANN installation not found after installation!"
        return 1
    fi

    log_info "CANN path: $CANN_PATH"
    export ASCEND_HOME_PATH="$CANN_PATH"

    if [ -f "$CANN_PATH/bin/setenv.bash" ]; then
        source "$CANN_PATH/bin/setenv.bash"
        log_info "Sourced setenv.bash"
    fi

    local pkg_inc="$CANN_PATH/pkg_inc"
    local arch_inc=""

    if [ -d "$CANN_PATH/x86_64-linux/include" ]; then
        arch_inc="$CANN_PATH/x86_64-linux/include"
    elif [ -d "$CANN_PATH/aarch64-linux/include" ]; then
        arch_inc="$CANN_PATH/aarch64-linux/include"
    fi

    if [ -n "$arch_inc" ] && [ -d "$arch_inc" ]; then
        mkdir -p "$pkg_inc"
        for dir in mmpa fmk ts adump; do
            if [ ! -e "$pkg_inc/$dir" ] && [ -d "$arch_inc/$dir" ]; then
                ln -sf "$arch_inc/$dir" "$pkg_inc/$dir" 2>/dev/null && \
                    log_info "Linked $dir"
            fi
        done
    fi
}

install_system_deps() {
    log_info "Checking system dependencies..."

    local missing_cmds
    missing_cmds=$(get_missing_required_system_deps)

    if ! is_root_user; then
        if [ -n "$missing_cmds" ]; then
            log_warn "Skipping system dependency installation (non-root user)"
            log_error "Missing required system commands: ${missing_cmds}"
            log_error "Install them manually or rerun this script as root/sudo"
            return 1
        else
            log_info "Required system dependencies are available"
        fi

        check_command cmake && log_info "cmake: $(cmake --version 2>&1 | head -1)" || log_warn "cmake: not installed"
        check_command g++ && log_info "g++: $(g++ --version 2>&1 | head -1)" || log_warn "g++: not installed"
        check_command ccache && log_info "ccache: available" || log_warn "ccache: not installed"
        return 0
    fi

    if check_command apt-get; then
        apt-get update -qq 2>/dev/null || log_warn "apt-get update failed"
        local pkgs=""
        check_command curl || pkgs="$pkgs curl"
        check_command wget || pkgs="$pkgs wget"
        check_command git || pkgs="$pkgs git"
        check_command cmake || pkgs="$pkgs cmake"
        check_command make || pkgs="$pkgs make"
        check_command g++ || pkgs="$pkgs g++"
        check_command ccache || pkgs="$pkgs ccache"

        if [ -n "$pkgs" ]; then
            log_info "Installing:$pkgs"
            apt-get install -y -qq $pkgs 2>/dev/null || log_warn "Some packages may have failed"
        fi
    elif check_command yum; then
        local pkgs=""
        check_command curl || pkgs="$pkgs curl"
        check_command wget || pkgs="$pkgs wget"
        check_command git || pkgs="$pkgs git"
        check_command cmake || pkgs="$pkgs cmake"
        check_command make || pkgs="$pkgs make"
        check_command g++ || pkgs="$pkgs gcc-c++"

        if [ -n "$pkgs" ]; then
            log_info "Installing:$pkgs"
            yum install -y -q $pkgs 2>/dev/null || log_warn "Some packages may have failed"
        fi
    else
        log_warn "No supported package manager found, skipping system dependency installation"
    fi

    missing_cmds=$(get_missing_required_system_deps)
    if [ -n "$missing_cmds" ]; then
        log_error "Missing required system commands after installation attempt: ${missing_cmds}"
        return 1
    fi

    check_command cmake && log_info "cmake: $(cmake --version 2>&1 | head -1)" || log_warn "cmake: not installed"
    check_command g++ && log_info "g++: $(g++ --version 2>&1 | head -1)" || log_warn "g++: not installed"
    check_command ccache && log_info "ccache: available" || log_warn "ccache: not installed"
}

run_pip_command() {
    local python="$1"
    shift

    local pip_log
    pip_log=$(mktemp "${TMPDIR:-/tmp}/init_env_pip.XXXXXX") || {
        log_error "Failed to create temporary pip log file"
        return 1
    }

    if "$python" -m pip "$@" >"$pip_log" 2>&1; then
        rm -f "$pip_log"
        return 0
    fi

    log_warn "pip command failed: $python -m pip $*"
    local pip_error_tail
    pip_error_tail=$(tail -n 5 "$pip_log" 2>/dev/null || true)
    if [ -n "$pip_error_tail" ]; then
        while IFS= read -r line; do
            log_warn "pip: $line"
        done <<< "$pip_error_tail"
    fi
    rm -f "$pip_log"
    return 1
}

install_python_deps() {
    log_info "Checking Python dependencies..."

    local python="python3"
    check_command python3 || python="python"

    if ! check_command "$python"; then
        log_error "Python is not installed"
        return 1
    fi

    log_info "Python: $($python --version 2>&1)"

    local requirements_file="${1:-requirements.txt}"
    local remote_requirements_url="${OAM_TOOLS_RAW_BASE_URL}/requirements.txt"
    local requirements_content=""

    if [ -f "$requirements_file" ]; then
        log_info "Installing Python dependencies from: $requirements_file"
        run_pip_command "$python" install --upgrade pip -q || log_warn "Failed to upgrade pip, continuing"
        run_pip_command "$python" install -r "$requirements_file" -q || {
            log_error "Failed to install Python dependencies from: $requirements_file"
            return 1
        }
    elif check_command curl; then
        log_warn "requirements.txt not found locally, installing from: $remote_requirements_url"
        validate_download_url "$remote_requirements_url" "requirements.txt download" advisory || return 1
        requirements_content=$(curl -fsSL "$remote_requirements_url") || {
            log_error "Failed to fetch requirements.txt"
            return 1
        }
        if [ -z "$(printf '%s\n' "$requirements_content" | tr -d '[:space:]')" ]; then
            log_error "Fetched requirements.txt is empty, refusing to install"
            return 1
        fi
        if printf '%s\n' "$requirements_content" | grep -qE '^[[:space:]]*-'; then
            log_error "Fetched requirements.txt contains pip option lines (e.g. --index-url), refusing to install"
            return 1
        fi
        local tmp_requirements
        tmp_requirements=$(mktemp "${TMPDIR:-/tmp}/oam_requirements.XXXXXX") || {
            log_error "Failed to create temporary requirements file"
            return 1
        }
        printf '%s\n' "$requirements_content" > "$tmp_requirements" || {
            rm -f "$tmp_requirements"
            log_error "Failed to write temporary requirements file"
            return 1
        }
        run_pip_command "$python" install --upgrade pip -q || log_warn "Failed to upgrade pip, continuing"
        run_pip_command "$python" install -r "$tmp_requirements" -q || {
            rm -f "$tmp_requirements"
            log_error "Failed to install Python dependencies from: $remote_requirements_url"
            return 1
        }
        rm -f "$tmp_requirements"
    else
        log_error "requirements.txt not found and curl is unavailable, cannot install Python dependencies"
        return 1
    fi

    check_command pytest && log_info "pytest: $(pytest --version 2>&1 | head -1)"
    check_command coverage && log_info "coverage: $(coverage --version 2>&1 | head -1)"
}

show_help() {
    local work_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    local version_file="${work_dir}/version.cmake"
    local default_cann_version="${CANN_VERSION:-}"

    if [ -z "$default_cann_version" ] && [ -f "$version_file" ]; then
        default_cann_version=$(get_cann_version_from_cmake "$version_file" 2>/dev/null || true)
    fi
    default_cann_version="${default_cann_version:-auto-detect from version.cmake}"

    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "oam-tools development environment setup script"
    echo ""
    echo "Options:"
    echo "  --cann-version VERSION   CANN version (default: ${default_cann_version})"
    echo "  --chip-type TYPE         Chip type examples: 910b, 910_93/A3, 950 (default: ${CHIP_TYPE})"
    echo "  --install-path PATH      Installation path (default: ${INSTALL_PATH})"
    echo "  --skip-cann              Skip CANN installation"
    echo "  --skip-ops, --toolkit-only  Skip ops package download (compile-only scenario)"
    echo "  --help                   Show this help"
    echo ""
    echo "Examples:"
    echo "  $0                       # Install with defaults"
    echo "  $0 --skip-cann           # Skip CANN, install only deps"
    echo "  $0 --skip-ops            # Install toolkit only, skip ops"
    echo "  $0 --chip-type 910_93    # Use A3 ops package"
    echo ""
}

main() {
    local skip_cann=false
    local work_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    local version_file="${work_dir}/version.cmake"

    while [[ $# -gt 0 ]]; do
        case $1 in
            --cann-version)
                CANN_VERSION="$2"
                shift 2
                ;;
            --chip-type)
                CHIP_TYPE="$2"
                shift 2
                ;;
            --install-path)
                INSTALL_PATH="$2"
                shift 2
                ;;
            --skip-cann)
                skip_cann=true
                shift
                ;;
            --skip-ops|--toolkit-only)
                SKIP_OPS="true"
                shift
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            *)
                log_warn "Unknown option: $1"
                shift
                ;;
        esac
    done

    if [ -z "$CANN_VERSION" ]; then
        if ! CANN_VERSION=$(get_cann_version_from_cmake "$version_file"); then
            log_error "CANN version could not be determined, please specify --cann-version"
            exit 1
        fi
    fi

    if [ -z "$CANN_VERSION" ]; then
        log_error "CANN version could not be determined, please specify --cann-version"
        exit 1
    fi

    echo ""
    echo "=========================================="
    echo "  oam-tools Development Environment Setup"
    echo "=========================================="
    echo ""
    echo "Configuration:"
    echo "  CANN Version:  ${CANN_VERSION}"
    echo "  Chip Type:     ${CHIP_TYPE}"
    echo "  Install Path:  ${INSTALL_PATH}"
    echo "  Skip Ops:      ${SKIP_OPS}"
    echo ""

    cd "$work_dir"
    log_info "Working directory: $work_dir"

    install_system_deps

    if [ "$skip_cann" = true ]; then
        log_info "Skipping CANN installation (--skip-cann)"
    else
        install_cann
    fi

    setup_cann_env
    install_python_deps "${work_dir}/requirements.txt"

    echo ""
    log_info "=========================================="
    log_info "  Development environment ready!"
    log_info "=========================================="
    echo ""
    echo "Next steps:"
    echo "  bash build.sh          # Build project"
    echo "  bash build.sh -u       # Build and run UT"
    echo "  bash build.sh -u --cov # Build with coverage"
    echo ""
}

main "$@"
