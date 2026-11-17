import subprocess
from pathlib import Path

from scripts.audit_secrets import run_audit


def test_audit_secrets_placeholder_ignored(tmp_path: Path, capsys) -> None:
    example_file = tmp_path / ".env.example"
    example_file.write_text("MY_SECRET=placeholder_value_123\n", encoding="utf-8")

    env_file = tmp_path / ".env"
    env_file.write_text("MY_SECRET=placeholder_value_123\n", encoding="utf-8")

    exit_code = run_audit(env_path=env_file, example_path=example_file, repo_path=tmp_path)
    captured = capsys.readouterr().out

    assert exit_code == 0
    assert "placeholder (diabaikan)" in captured
    assert "Total temuan kebocoran rahasia nyata  : 0" in captured
    # Nilai rahasia tidak pernah dicetak
    assert "placeholder_value_123" not in captured


def test_audit_secrets_clean_real_secret(tmp_path: Path, capsys) -> None:
    example_file = tmp_path / ".env.example"
    example_file.write_text("MY_SECRET=placeholder_value_123\n", encoding="utf-8")

    env_file = tmp_path / ".env"
    secret_val = "super_unique_secret_not_leaked_987654"
    env_file.write_text(f"MY_SECRET={secret_val}\n", encoding="utf-8")

    # Inisialisasi repo git kosong di tmp_path
    subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=str(tmp_path), check=True)
    subprocess.run(
        ["git", "config", "user.email", "tester@example.com"], cwd=str(tmp_path), check=True
    )
    clean_file = tmp_path / "README.md"
    clean_file.write_text("Clean project\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=str(tmp_path), check=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=str(tmp_path), check=True)

    exit_code = run_audit(env_path=env_file, example_path=example_file, repo_path=tmp_path)
    captured = capsys.readouterr().out

    assert exit_code == 0
    assert "Status: BERSIH" in captured
    assert "Total temuan kebocoran rahasia nyata  : 0" in captured
    # Nilai rahasia sungguhan TIDAK PERNAH dicetak
    assert secret_val not in captured


def test_audit_secrets_detects_leak_and_returns_1(tmp_path: Path, capsys) -> None:
    example_file = tmp_path / ".env.example"
    example_file.write_text("MY_SECRET=placeholder_value_123\n", encoding="utf-8")

    leaked_val = "leaked_super_secret_value_abcdef"
    env_file = tmp_path / ".env"
    env_file.write_text(f"MY_SECRET={leaked_val}\n", encoding="utf-8")

    # Inisialisasi repo git dan buat kebocoran di file kode
    subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=str(tmp_path), check=True)
    subprocess.run(
        ["git", "config", "user.email", "tester@example.com"], cwd=str(tmp_path), check=True
    )
    leaked_code_file = tmp_path / "bad_code.py"
    leaked_code_file.write_text(f'token = "{leaked_val}"\n', encoding="utf-8")
    subprocess.run(["git", "add", "bad_code.py"], cwd=str(tmp_path), check=True)
    subprocess.run(["git", "commit", "-m", "leaked commit"], cwd=str(tmp_path), check=True)

    exit_code = run_audit(env_path=env_file, example_path=example_file, repo_path=tmp_path)
    captured = capsys.readouterr().out

    assert exit_code == 1
    assert "Status: BAHAYA" in captured
    # Nilai rahasia sungguhan TIDAK PERNAH dicetak
    assert leaked_val not in captured
