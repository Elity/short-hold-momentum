"""Exercise the container entrypoint against an existing persistent volume."""
import os
from pathlib import Path
import subprocess


def test_v03_seed_adds_assets_without_overwriting_persistent_state(tmp_path):
    seed = tmp_path / "seed"
    repository = tmp_path / "repository"
    for root in (seed, repository):
        for directory in ("config", "data", "docs", "experiments", "paper", "reports"):
            (root / directory).mkdir(parents=True)

    def write(root, name, content):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    preserved = {
        "config/params.frozen.yaml": b"owner V04 parameters\n",
        "config/v03/winner.json": b'{"strategy_id":"C3","owner_frozen":true}\n',
        "paper/accounts/2026-09-05.json": b'{"cash":100000,"positions":{}}\n',
        "paper/v03/C3/days/2026-09-18.json": b"owner v0.3 account and fills\n",
        "reports/paper-2026-09.md": b"existing V04 report\n",
        "reports/v03/selection.json": b"existing v0.3 selection\n",
        "experiments/v03/log.jsonl": b"existing research audit\n",
        "config/v04/winner.json": b"existing frozen S500 winner\n",
        "data/reference/sp500/current.json": b"current NAS member snapshot\n",
        "data/reference/sp500/checks.json": b"current NAS source checks\n",
        "paper/v04/S500-C3/days/2026-09-18.json": b"S500 account and fills\n",
    }
    for name, content in preserved.items():
        write(repository, name, content)
        write(seed, name, b"image copy must not replace this file\n")
    additions = {
        "config/sp500.yaml": b"enabled: true\n",
        "config/v03/candidates.yaml": b"new fixed candidate definitions\n",
        "experiments/prereg/v03/C3.md": b"new preregistration\n",
        "experiments/v03/protocol.json": b"new research protocol\n",
        "reports/v03/research.md": b"new consolidated research report\n",
        "docs/spec-v0.3.md": b"approved v0.3 specification\n",
        "docs/decisions/ADR-011-v03-trend-exit-research.md": b"approved research decision\n",
        "config/v04/candidates.yaml": b"S500 fixed candidates\n",
        "experiments/prereg/v04/S500-C3.md": b"S500 preregistration\n",
        "experiments/v04/protocol.json": b"S500 research protocol\n",
        "reports/v04/research.md": b"S500 consolidated research report\n",
        "docs/spec-v0.4.md": b"approved S500 specification\n",
        "docs/decisions/ADR-012-sp500-universe.md": b"approved S500 scope\n",
        "data/reference/sp500/snapshots/new-snapshot.json": b"new immutable source snapshot\n",
    }
    for name, content in additions.items():
        write(seed, name, content)
    write(seed, "paper/v03/C3/days/2026-09-21.json", b"never inject an image account into a live volume\n")
    write(seed, "paper/v04/S500-C3/days/2026-09-21.json", b"never inject an S500 account\n")
    entrypoint = Path(__file__).resolve().parents[1] / "docker/entrypoint.sh"
    environment = {"PATH": os.environ["PATH"], "SHM_SEED_ROOT": str(seed), "SHM_REPO_ROOT": str(repository)}
    command = ["/bin/sh", str(entrypoint), "/bin/sh", "-c",
               "test -f docs/spec-v0.3.md && test -f reports/v03/research.md && pwd"]
    for _ in range(2):
        completed = subprocess.run(command, env=environment, check=True, text=True, capture_output=True)
        assert Path(completed.stdout.strip()).resolve() == repository.resolve()
        for name, content in {**preserved, **additions}.items():
            assert (repository / name).read_bytes() == content
        assert not (repository / "paper/v03/C3/days/2026-09-21.json").exists()
        assert not (repository / "paper/v04/S500-C3/days/2026-09-21.json").exists()

    # A locally reviewed v0.3 spec also survives a later image update.
    write(repository, "docs/spec-v0.3.md", b"owner reviewed specification\n")
    subprocess.run(command, env=environment, check=True, capture_output=True)
    assert (repository / "docs/spec-v0.3.md").read_bytes() == b"owner reviewed specification\n"
