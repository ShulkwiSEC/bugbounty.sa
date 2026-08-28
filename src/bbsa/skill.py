"""Auto-install the bbsa skill into installed coding agents.

The skill (``SKILL.md``) is bundled inside the wheel next to this module and
gets copied, idempotently, into each detected agent's skill directory on the
first run of ``bbsa`` or ``bbsa-mcp``. Changed skill content replaces older
installed copies on the next run. No user interaction.

Agent skill roots (skill dir is ``<root>/bbsa/SKILL.md``):

- Claude Code: ``~/.claude/skills``
- Codex:       ``~/.codex/skills``
- opencode:    ``~/.config/opencode/skills`` (skipped when Claude Code is
  detected because opencode auto-loads ``~/.claude/skills``)

An agent counts as "available" when its config home directory exists.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

__all__ = ["install_skill", "ensure_skill_installed"]

SKILL_NAME = "bbsa"

_AGENTS: tuple[tuple[str, str], ...] = (
    ("Claude Code", "~/.claude/skills"),
    ("Codex", "~/.codex/skills"),
    ("opencode", "~/.config/opencode/skills"),
)


def _skill_source() -> Path:
    return Path(__file__).with_name("SKILL.md")


def _available_targets() -> list[tuple[str, Path]]:
    # ponytail: opencode is skipped whenever ~/.claude exists because opencode
    # auto-loads ~/.claude/skills; a user who disabled that scan
    # (OPENCODE_DISABLE_CLAUDE_CODE_SKILLS=1) gets nothing — README covers manual install.
    home = Path.home()
    claude_root = home / ".claude" / "skills"
    targets: list[tuple[str, Path]] = []
    for name, root in _AGENTS:
        root_path = Path(root).expanduser()
        if name == "opencode":
            if claude_root.parent.exists():
                continue
            if not (home / ".config" / "opencode").exists():
                continue
        else:
            if not root_path.parent.exists():
                continue
        targets.append((name, root_path))
    return targets


def install_skill() -> list[tuple[str, Path]]:
    """Install/refresh the skill into every available agent.

    Returns the agents whose skill file was newly written or updated.
    """
    src = _skill_source()
    if not src.exists():
        return []
    data = src.read_bytes()
    installed: list[tuple[str, Path]] = []
    for name, root in _available_targets():
        dest = root / SKILL_NAME / "SKILL.md"
        if dest.exists() and dest.read_bytes() == data:
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        installed.append((name, dest))
    return installed


def ensure_skill_installed() -> None:
    """Entry-point hook: install silently, never raise, never touch stdout."""
    # ponytail: swallow-all by design — a skill-install failure must never
    # break bbsa; add --debug surfacing if install errors ever matter.
    try:
        installed = install_skill()
        if installed:
            sys.stderr.write(
                "bbsa: installed agent skill into "
                + ", ".join(name for name, _ in installed)
                + "\n"
            )
    except Exception:
        pass


def _self_check() -> None:
    home = Path(os.environ["HOME"])
    (home / ".claude").mkdir(parents=True)
    (home / ".codex").mkdir(parents=True)
    (home / ".config" / "opencode").mkdir(parents=True)

    installed = [name for name, _ in install_skill()]
    assert set(installed) == {"Claude Code", "Codex"}, installed
    assert (home / ".claude" / "skills" / "bbsa" / "SKILL.md").exists()
    assert (home / ".codex" / "skills" / "bbsa" / "SKILL.md").exists()
    assert not (home / ".config" / "opencode" / "skills").exists(), (
        "opencode target must be skipped when Claude Code is present"
    )

    assert install_skill() == [], "second run must be a no-op"

    dest = home / ".claude" / "skills" / "bbsa" / "SKILL.md"
    dest.write_bytes(b"tampered")
    updated = [name for name, _ in install_skill()]
    assert updated == ["Claude Code"], "tampered skill must be refreshed"
    assert dest.read_bytes() == _skill_source().read_bytes()

    codex_only = Path(os.environ["HOME"]) / "codex-only-home"
    codex_only.mkdir()
    (codex_only / ".codex").mkdir()
    old_home = os.environ["HOME"]
    os.environ["HOME"] = str(codex_only)
    try:
        targets = [name for name, _ in install_skill()]
        assert targets == ["Codex"], targets
        assert (codex_only / ".codex" / "skills" / "bbsa" / "SKILL.md").exists()
    finally:
        os.environ["HOME"] = old_home
    print("skill self-check ok")


if __name__ == "__main__":
    _self_check()
