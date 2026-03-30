from pathlib import Path

from nanobot.instances import (
    build_docker_instance_command,
    build_instance_command,
    build_onboard_command,
    get_instances_dir,
    list_instances,
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


def test_list_instances_reads_name_from_config(tmp_path: Path) -> None:
    root = tmp_path / "chris"
    root.mkdir(parents=True)
    (root / "config.json").write_text(
        '{"agents": {"defaults": {"name": "Chris"}}}',
        encoding="utf-8",
    )

    instances = list_instances(tmp_path)

    assert len(instances) == 1
    assert instances[0].slug == "chris"
    assert instances[0].name == "Chris"
    assert instances[0].config_path == root / "config.json"


def test_list_instances_falls_back_to_slug_without_config(tmp_path: Path) -> None:
    root = tmp_path / "demo"
    root.mkdir(parents=True)

    instances = list_instances(tmp_path)

    assert len(instances) == 1
    assert instances[0].slug == "demo"
    assert instances[0].name == "demo"


def test_build_docker_instance_command_supports_extra_mounts_and_hosts(tmp_path: Path) -> None:
    instance = resolve_instance_paths("Nano Chris", base_dir=tmp_path)

    command = build_docker_instance_command(
        instance,
        image="nanochris:local",
        nanobot_args=["gateway"],
        detached=True,
        remove=False,
        volume_mounts=["/tmp/whisper:/root/.cache/whisper"],
        extra_hosts=["host.docker.internal:host-gateway"],
        environment={
            "NANOBOT_TOOLS__WEB__SEARCH__PROVIDER": "searxng",
            "NANOBOT_TOOLS__WEB__SEARCH__BASE_URL": "http://nanochris-searxng:8080",
        },
        network="nanochris-net",
    )

    assert command == [
        "docker",
        "run",
        "-d",
        "--name",
        "nanochris-nano-chris",
        "--network",
        "nanochris-net",
        "-v",
        f"{instance.root.expanduser().resolve(strict=False)}:/root/.nanobot",
        "-v",
        "/tmp/whisper:/root/.cache/whisper",
        "--add-host",
        "host.docker.internal:host-gateway",
        "-e",
        "NANOBOT_TOOLS__WEB__SEARCH__PROVIDER=searxng",
        "-e",
        "NANOBOT_TOOLS__WEB__SEARCH__BASE_URL=http://nanochris-searxng:8080",
        "nanochris:local",
        "gateway",
    ]
