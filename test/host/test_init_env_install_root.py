# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Real Linux Bash CLI, path and links; external roots use private fixtures.

Only fixed system/user installation roots are mapped in the temporary script
copy. HOME, the parser, main, detection and environment/link setup are unchanged.
Package installation functions are explicit boundaries: no installer, pip or
system packages run, and the marker setenv file is not a real CANN toolkit.
"""

import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "init_env.sh"
LAYOUTS = ("ascend-toolkit/latest", "cann-9.2.0", "latest", "cann-8.5.0")
# A uid the stub reports instead of the real one. It must not be a value a real
# account holds: 1000 is the most common uid on Linux, so a stub printing 1000
# is indistinguishable from a dead stub on a developer machine.
STUB_UID = "424242"
pytestmark = pytest.mark.skipif(
    sys.platform != "linux" or not shutil.which("bash") or not shutil.which("realpath"),
    reason="Linux Bash and realpath are required for actual symlink semantics",
)


def _suite(root, layout, marker):
    path = root / layout
    (path / "bin").mkdir(parents=True)
    (path / "bin/setenv.bash").write_text(
        f'export OAM_DISCOVERY_MARKER="{marker}"\n', encoding="utf-8"
    )
    for name in ("mmpa", "fmk"):
        directory = path / "x86_64-linux/include" / name
        directory.mkdir(parents=True)
        (directory / "marker.h").write_text(
            "/* private host fixture */\n", encoding="utf-8"
        )
    return path


def _run(
    tmp_path,
    layout="ascend-toolkit/latest",
    spaced=False,
    argument_kind="absolute",
    missing=False,
    help_only=False,
    skip_cann=True,
    system_version=False,
    root_mode="cli",
    system_layout=None,
    empty_path=False,
    without_realpath=False,
    rival_layout=None,
    nonroot_id=False,
    empty_environment=False,
    cann_path=None,
):
    project = tmp_path / "script project"
    caller = tmp_path / "caller directory"
    project.mkdir()
    caller.mkdir()
    root = caller / ("selected root with spaces" if spaced else "selected-root")
    user_root, system_root = (
        tmp_path / "private user root",
        tmp_path / "private system root",
    )
    marker = "selected-root"
    if root_mode == "default":
        root, marker = user_root, "default-user"
    suite = root / layout
    if not missing:
        suite = _suite(root, layout, marker)
    if rival_layout:
        # A second, differently named suite in the same root. It only wins
        # when the versioned entries are no longer searched first.
        _suite(root, rival_layout, f"{marker}-rival")
    if system_layout:
        # A suite under the system root with an arbitrary layout, so the
        # wildcard fallback in detect_cann_path can be reached.
        system_suite = _suite(system_root, system_layout, "default-system")
    elif system_version:
        system_suite = _suite(system_root, "cann-9.2.0", "default-system")
    else:
        system_suite = None

    if argument_kind == "symlink":
        alias = caller / "linked install root"
        alias.symlink_to(root, target_is_directory=True)
        root = alias

    source = SCRIPT.read_text(encoding="utf-8")
    suffix = 'main "$@"'
    assert source.rstrip().endswith(suffix)
    source = source.rstrip()[: -len(suffix)]
    # Fixed external roots are mapped rather than changing HOME or writing
    # /usr/local/Ascend. Quoting preserves each fixed-prefix glob as one word
    # when the temporary workspace prefix itself contains spaces.
    source = source.replace(
        "/usr/local/Ascend/ascend-toolkit/*",
        '"${OAM_TEST_SYSTEM_ROOT}"/ascend-toolkit/*',
    )
    source = source.replace(
        "/usr/local/Ascend/cann-*", '"${OAM_TEST_SYSTEM_ROOT}"/cann-*'
    )
    source = source.replace("/usr/local/Ascend", "${OAM_TEST_SYSTEM_ROOT}")
    source = source.replace("${HOME}/Ascend", "${OAM_TEST_USER_ROOT}")
    source = source.replace("$HOME/Ascend", "${OAM_TEST_USER_ROOT}")
    (project / "init_env_source.sh").write_text(source, encoding="utf-8")
    shutil.copyfile(ROOT / "version.cmake", project / "version.cmake")
    driver = project / "run.sh"
    driver.write_text(
        """#!/usr/bin/env bash
source "$(dirname "$0")/init_env_source.sh"
function install_system_deps() { printf '%s\\n' 'BOUNDARY=system-packages'; }
function install_python_deps() { printf '%s\\n' 'BOUNDARY=python-packages'; }
main "$@"
printf 'OBSERVED_PATH=%s\\n' "$ASCEND_HOME_PATH"
printf 'OBSERVED_MARKER=%s\\n' "${OAM_DISCOVERY_MARKER:-not-sourced}"
for name in mmpa fmk; do
    link="$ASCEND_HOME_PATH/pkg_inc/$name"
    printf 'LINK_TARGET_%s=%s\\n' "$name" "$(readlink -- "$link" 2>/dev/null || true)"
    if [ -L "$link" ] && [ -f "$link/marker.h" ]; then
        printf 'LINK_STATE_%s=live\\n' "$name"
    else
        printf 'LINK_STATE_%s=missing-or-dangling\\n' "$name"
    fi
done
""",
        encoding="utf-8",
    )
    env = dict(os.environ)
    env.pop("INSTALL_PATH", None)
    env.pop("OAM_DISCOVERY_MARKER", None)
    if empty_environment:
        # Exported but empty: a different input from an unset variable and from
        # --install-path "", so it needs its own path through main().
        env["INSTALL_PATH"] = ""
    env.update(
        CANN_VERSION="9.2.0",
        OAM_TEST_SYSTEM_ROOT=str(system_root),
        OAM_TEST_USER_ROOT=str(user_root),
    )
    if cann_path is not None:
        env["CANN_PATH"] = cann_path
    arguments = [shutil.which("bash"), str(driver)]
    if help_only:
        arguments.append("--help")
    else:
        if skip_cann:
            arguments.append("--skip-cann")
        if root_mode == "cli":
            value = str(root)
            if argument_kind == "relative":
                value = "./" + root.name
            elif argument_kind == "relative_same_cwd":
                root_in_project = project / root.name
                shutil.move(str(root), root_in_project)
                suite = root_in_project / layout
                caller = project
                value = "./" + root.name
            elif argument_kind == "trailing":
                value += "///"
            if empty_path:
                value = ""
            arguments.extend(("--install-path", value))
        elif root_mode == "environment":
            env["INSTALL_PATH"] = str(root)
    if nonroot_id:
        # Root CI reports `id -u` 0, which makes the script default to the
        # system root and leaves the HOME precedence cases uncovered. A stub
        # uid keeps them running everywhere; only `id` is shadowed.
        stub_bin = tmp_path / "private-id-bin"
        stub_bin.mkdir()
        (stub_bin / "id").write_text(
            "#!/usr/bin/env bash\nprintf '%s\\n'\n" % STUB_UID,
            encoding="utf-8",
        )
        (stub_bin / "id").chmod(0o755)
        env["PATH"] = str(stub_bin) + os.pathsep + env["PATH"]
    if without_realpath:
        private_bin = tmp_path / "private-bin"
        private_bin.mkdir()
        for command in ("dirname", "mkdir", "ln", "readlink"):
            target = shutil.which(command)
            assert target
            (private_bin / command).symlink_to(target)
        if nonroot_id:
            (private_bin / "id").write_text(
                "#!/usr/bin/env bash\nprintf '%s\\n'\n" % STUB_UID,
                encoding="utf-8",
            )
            (private_bin / "id").chmod(0o755)
        else:
            target = shutil.which("id")
            assert target
            (private_bin / "id").symlink_to(target)
        env["PATH"] = str(private_bin)
    result = subprocess.run(
        arguments,
        cwd=caller,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=20,
    )
    output = result.stdout + result.stderr
    observed = dict(
        line.split("=", 1)
        for line in output.splitlines()
        if line.startswith(("OBSERVED_", "LINK_TARGET_", "LINK_STATE_"))
    )
    return result, output, observed, suite, system_suite


def _assert_suite(result, output, observed, suite, marker):
    assert result.returncode == 0, output
    assert observed["OBSERVED_PATH"] == str(suite)
    assert Path(observed["OBSERVED_PATH"]).is_absolute()
    assert observed["OBSERVED_MARKER"] == marker
    assert "BOUNDARY=python-packages" in output
    for name in ("mmpa", "fmk"):
        assert observed[f"LINK_STATE_{name}"] == "live"
        assert observed[f"LINK_TARGET_{name}"] == str(
            suite / "x86_64-linux/include" / name
        )


@pytest.mark.parametrize("layout", LAYOUTS)
@pytest.mark.parametrize("spaced", (False, True))
def test_selected_existing_layouts_and_real_links(tmp_path, layout, spaced):
    result, output, observed, suite, _ = _run(tmp_path, layout=layout, spaced=spaced)
    _assert_suite(result, output, observed, suite, "selected-root")
    assert "Skipping CANN installation (--skip-cann)" in output


def test_missing_installation_remains_failure(tmp_path):
    result, output, observed, _, _ = _run(tmp_path, missing=True)
    assert result.returncode == 1
    assert "Setting up CANN environment..." in output
    assert "BOUNDARY=python-packages" not in output
    assert not observed


def test_missing_explicit_root_falls_back_to_the_system_suite(tmp_path):
    # The explicit root wins when it holds a suite, but a missing one must
    # still let the standard system root be found instead of failing.
    result, output, observed, _, system_suite = _run(
        tmp_path, missing=True, system_version=True
    )
    _assert_suite(result, output, observed, system_suite, "default-system")


@pytest.mark.parametrize("layout", ("cann-9.2.0", "cann-9.2.0-beta.1", "cann"))
def test_explicit_exact_entries_beat_the_system_suite(tmp_path, layout):
    result, output, observed, suite, _ = _run(
        tmp_path, layout=layout, system_version=True
    )
    _assert_suite(result, output, observed, suite, "selected-root")


@pytest.mark.parametrize(
    ("layout", "rival_layout"),
    (
        ("cann-9.2.0", "ascend-toolkit/latest"),
        ("cann-9.2.0-beta.1", "latest"),
        ("cann-9.2.0", "cann-8.5.0"),
    ),
)
def test_explicit_root_prefers_versioned_entries(tmp_path, layout, rival_layout):
    result, output, observed, suite, _ = _run(
        tmp_path, layout=layout, rival_layout=rival_layout
    )
    _assert_suite(result, output, observed, suite, "selected-root")
    assert observed["OBSERVED_MARKER"] != "selected-root-rival"


def test_explicit_wildcard_hit_warns_about_the_version(tmp_path):
    result, output, observed, suite, _ = _run(tmp_path, layout="cann-8.5.0")
    _assert_suite(result, output, observed, suite, "selected-root")
    assert "Detected CANN 8.5.0 while CANN_VERSION is 9.2.0" in output


def test_full_install_flow_warns_about_the_version_exactly_once(tmp_path):
    # install_cann and setup_cann_env both call detect_cann_path, so the
    # default full-install flow used to print this warning twice
    # (fujun19, PR #762 2026-10-21). install_cann now remembers the hit
    # in CANN_PATH; a fresh installation still re-probes.
    result, output, observed, suite, _ = _run(
        tmp_path, layout="cann-8.5.0", skip_cann=False
    )
    _assert_suite(result, output, observed, suite, "selected-root")
    warnings = [line for line in output.splitlines() if "Detected CANN" in line]
    assert len(warnings) == 1


def test_inherited_bogus_cann_path_is_ignored(tmp_path):
    # CANN_PATH is an internal accumulator, not a caller setting (fujun19,
    # PR #899 2026-11-01): an inherited value used to masquerade as the
    # install_cann cache, skip detection entirely and export a nonexistent
    # ASCEND_HOME_PATH with exit code 0.
    bogus = str(tmp_path / "bogus" / "cann-9.2.0")
    result, output, observed, suite, _ = _run(tmp_path, cann_path=bogus)
    _assert_suite(result, output, observed, suite, "selected-root")
    assert bogus not in output


def test_inherited_valid_cann_path_is_ignored(tmp_path):
    # Even a working inherited CANN_PATH pointing at a real suite must not
    # win: detection re-runs and the chosen install root is what gets sourced.
    inherited = _suite(tmp_path / "inherited-root", "cann-9.2.0", "inherited-root")
    result, output, observed, suite, _ = _run(tmp_path, cann_path=str(inherited))
    _assert_suite(result, output, observed, suite, "selected-root")
    assert observed["OBSERVED_MARKER"] != "inherited-root"


@pytest.mark.parametrize("layout", ("ascend-toolkit/8.0.0", "ascend-toolkit/9.1.0"))
def test_toolkit_wildcard_hit_warns_about_the_version(tmp_path, layout):
    # The same wildcard scan reaches ascend-toolkit/<version>, so a differently
    # versioned toolkit under that layout must not be selected silently either.
    result, output, observed, suite, _ = _run(tmp_path, layout=layout)
    _assert_suite(result, output, observed, suite, "selected-root")
    version = layout.split("/")[-1]
    assert f"Detected CANN {version} while CANN_VERSION is 9.2.0" in output


def test_automatic_system_toolkit_wildcard_warns_about_the_version(tmp_path):
    # The default install root reaches ascend-toolkit/<version> through the
    # wildcard loop in detect_cann_path, which runs before scan_install_root.
    # Only warning inside scan_install_root left this path silent.
    result, output, observed, _, system_suite = _run(
        tmp_path,
        layout="unused",
        root_mode="default",
        missing=True,
        system_layout="ascend-toolkit/8.0.0",
        nonroot_id=True,
    )
    _assert_suite(result, output, observed, system_suite, "default-system")
    assert "Detected CANN 8.0.0 while CANN_VERSION is 9.2.0" in output


def test_toolkit_latest_does_not_warn_about_a_version(tmp_path):
    # "latest" sits in the same glob as the versioned toolkit directories but
    # is a layout name, not a version, so it must stay silent.
    result, output, observed, suite, _ = _run(tmp_path, layout="ascend-toolkit/latest")
    _assert_suite(result, output, observed, suite, "selected-root")
    assert "Detected CANN" not in output


def test_empty_environment_variable_warns_and_keeps_the_default_root(tmp_path):
    # An exported but empty INSTALL_PATH is neither an error nor equivalent to
    # an unset variable: the default root is still used, and the substitution
    # is reported instead of happening quietly.
    result, output, observed, suite, _ = _run(
        tmp_path,
        layout="cann-9.2.0",
        root_mode="default",
        nonroot_id=True,
        empty_environment=True,
    )
    _assert_suite(result, output, observed, suite, "default-user")
    assert "INSTALL_PATH is set but empty; it is treated as unset" in output


def test_absent_environment_variable_has_no_empty_warning(tmp_path):
    # Guards the branch above: it must key off "set but empty", not off
    # "the default root was chosen".
    result, output, observed, suite, _ = _run(
        tmp_path,
        layout="cann-9.2.0",
        root_mode="default",
        nonroot_id=True,
    )
    _assert_suite(result, output, observed, suite, "default-user")
    assert "INSTALL_PATH is set but empty" not in output


@pytest.mark.parametrize("spaced", (False, True))
def test_symlink_root_resolves_with_realpath(tmp_path, spaced):
    result, output, observed, suite, _ = _run(
        tmp_path, spaced=spaced, argument_kind="symlink"
    )
    _assert_suite(result, output, observed, suite, "selected-root")
    assert "realpath is unavailable" not in output


def test_help_keeps_custom_path_contract_without_packages(tmp_path):
    result, output, observed, _, _ = _run(tmp_path, help_only=True)
    assert result.returncode == 0
    assert "--install-path PATH" in output
    assert "BOUNDARY=" not in output
    assert not observed


@pytest.mark.parametrize("spaced", (False, True))
def test_relative_root_exports_absolute_path_and_live_links(tmp_path, spaced):
    result, output, observed, suite, _ = _run(
        tmp_path, spaced=spaced, argument_kind="relative_same_cwd"
    )
    _assert_suite(result, output, observed, suite, "selected-root")


def test_relative_root_resolves_before_script_changes_cwd(tmp_path):
    result, output, observed, suite, _ = _run(
        tmp_path, spaced=True, argument_kind="relative"
    )
    _assert_suite(result, output, observed, suite, "selected-root")


@pytest.mark.parametrize("spaced", (False, True))
def test_trailing_slashes_export_normalized_path(tmp_path, spaced):
    result, output, observed, suite, _ = _run(
        tmp_path, spaced=spaced, argument_kind="trailing"
    )
    _assert_suite(result, output, observed, suite, "selected-root")


@pytest.mark.parametrize("layout", ("cann-8.0.0", "ascend-toolkit/8.0.0"))
def test_automatic_root_does_not_hide_standard_requested_version(tmp_path, layout):
    result, output, observed, _, system_suite = _run(
        tmp_path,
        layout=layout,
        root_mode="default",
        system_version=True,
        nonroot_id=True,
    )
    _assert_suite(result, output, observed, system_suite, "default-system")


@pytest.mark.parametrize("root_mode", ("cli", "environment"))
def test_explicit_root_keeps_intentional_precedence(tmp_path, root_mode):
    result, output, observed, suite, _ = _run(
        tmp_path, layout="cann-8.0.0", root_mode=root_mode, system_version=True
    )
    _assert_suite(result, output, observed, suite, "selected-root")


def test_default_user_requested_version_still_works(tmp_path):
    result, output, observed, suite, _ = _run(
        tmp_path, layout="cann-9.2.0", root_mode="default", nonroot_id=True
    )
    _assert_suite(result, output, observed, suite, "default-user")


def test_stub_uid_really_shadows_the_real_one(tmp_path):
    # Guards the guard: without the stub the default-mode cases above would
    # silently select the system root when CI runs as root. Assert the uid
    # itself -- the script's own choice of root depends on more than the uid
    # (the standard-path array prefers $HOME/Ascend), so going through the
    # script could not tell a dead stub from a live one.
    stub_bin = tmp_path / "private-id-bin"
    stub_bin.mkdir()
    (stub_bin / "id").write_text(
        "#!/usr/bin/env bash\nprintf '%s\\n'\n" % STUB_UID, encoding="utf-8"
    )
    (stub_bin / "id").chmod(0o755)
    # A stub that prints the machine's own uid proves nothing: the assertion
    # below would pass with the stub removed entirely.
    assert STUB_UID != str(os.getuid())
    env = dict(os.environ)
    env["PATH"] = str(stub_bin) + os.pathsep + env["PATH"]
    probe = subprocess.run(
        [shutil.which("bash"), "-c", "id -u"],
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=20,
    )
    assert probe.returncode == 0, probe.stdout + probe.stderr
    assert probe.stdout.strip() == STUB_UID


def test_explicit_empty_path_has_clear_error_before_installation(tmp_path):
    # The argument parser rejects an empty value before main() sees it, so the
    # message is the parser's; main()'s empty-path check stays as a backstop
    # for any future caller that bypasses argument parsing.
    result, output, observed, _, _ = _run(tmp_path, empty_path=True)
    assert result.returncode == 1
    assert "[ERROR]" in output
    assert "--install-path requires a non-empty value" in output
    assert "BOUNDARY=" not in output
    assert not observed


@pytest.mark.parametrize("argument_kind", ["absolute", "relative"])
def test_existing_root_remains_usable_without_realpath(tmp_path, argument_kind):
    result, output, observed, suite, _ = _run(
        tmp_path, spaced=True, argument_kind=argument_kind, without_realpath=True
    )
    _assert_suite(result, output, observed, suite, "selected-root")
    # The warning is conditional: it fires only when the fallback had to
    # rewrite the value. An absolute root needs no rewriting, so there is
    # nothing to warn about; a relative one is prefixed with $(pwd -P).
    if argument_kind == "absolute":
        assert "realpath is unavailable" not in output
    else:
        assert "realpath is unavailable" in output
        assert "without expanding symlinks" in output


@pytest.mark.parametrize("spaced", (False, True))
def test_fallback_trailing_slashes_are_normalized(tmp_path, spaced):
    result, output, observed, suite, _ = _run(
        tmp_path, spaced=spaced, argument_kind="trailing", without_realpath=True
    )
    _assert_suite(result, output, observed, suite, "selected-root")
    assert "realpath is unavailable" in output


def test_fallback_symlink_exports_physical_path_and_live_links(tmp_path):
    result, output, observed, suite, _ = _run(
        tmp_path, spaced=True, argument_kind="symlink", without_realpath=True
    )
    _assert_suite(result, output, observed, suite, "selected-root")
    assert "realpath is unavailable" in output


def test_fallback_trailing_slashes_normalized_before_root_exists(tmp_path):
    result, output, observed, _, _ = _run(
        tmp_path, missing=True, argument_kind="trailing", without_realpath=True
    )
    assert result.returncode == 1
    assert "realpath is unavailable" in output
    assert not observed
    banner = [
        line for line in output.splitlines() if line.strip().startswith("Install Path:")
    ]
    assert len(banner) == 1
    assert "///" not in banner[0]
    assert banner[0].rstrip().endswith("selected-root")
