from pathlib import Path

from nanobot.instances import (
    build_instance_command,
    build_onboard_command,
    get_instances_dir,
    resolve_instance_paths,
)


def test_get_instances_dir_prefers_explicit_base_dir(tmp_path: Path) -> None:
    assert get_instances_dir(tmp_path) == tmp_path


def test_resolve_instance_paths_uses_slugged_name(tmp_path: Path) -> None:
    instance = resolve_instance_paths("Nano Chris", base_dir=tmp_path)

    assert instance.name == "Nano Chris"
    assert instance.slug == "nano-chris"
    assert instance.root == tmp_path / "nano-chris"
    assert instance.config_path == tmp_path / "nano-chris" / "config.json"
    assert instance.workspace_path == tmp_path / "nano-chris" / "workspace"


def test_resolve_instance_paths_defaults_blank_name(tmp_path: Path) -> None:
    instance = resolve_instance_paths("   ", base_dir=tmp_path)

    assert instance.name == "default"
    assert instance.slug == "default"


def test_build_onboard_command_targets_named_instance(tmp_path: Path) -> None:
    instance = resolve_instance_paths("Nano Chris", base_dir=tmp_path)

    assert build_onboard_command(instance, python_executable="python3") == [
        "python3",
        "-m",
        "nanobot",
        "onboard",
        "--config",
        str(instance.config_path),
        "--workspace",
        str(instance.workspace_path),
        "--name",
        "Nano Chris",
        "--wizard",
    ]


def test_build_instance_command_appends_instance_paths(tmp_path: Path) -> None:
    instance = resolve_instance_paths("Nano Chris", base_dir=tmp_path)

    assert build_instance_command(
        instance,
        python_executable="python3",
        command=["agent", "-m", "hello"],
    ) == [
        "python3",
        "-m",
        "nanobot",
        "agent",
        "-m",
        "hello",
        "--config",
        str(instance.config_path),
        "--workspace",
        str(instance.workspace_path),
    ]


def test_build_instance_command_does_not_duplicate_flags(tmp_path: Path) -> None:
    instance = resolve_instance_paths("Nano Chris", base_dir=tmp_path)

    assert build_instance_command(
        instance,
        python_executable="python3",
        command=[
            "gateway",
            "--config",
            "/tmp/custom-config.json",
            "--workspace",
            "/tmp/custom-workspace",
        ],
    ) == [
        "python3",
        "-m",
        "nanobot",
        "gateway",
        "--config",
        "/tmp/custom-config.json",
        "--workspace",
        "/tmp/custom-workspace",
    ]
