from dataclasses import dataclass
import subprocess


@dataclass(frozen=True)
class GitGateResult:
    approved: bool
    committed: bool
    summary: str


class GitGate:
    def __init__(self, repo_path: str = "."):
        self._repo_path = repo_path

    def _run(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            args,
            cwd=self._repo_path,
            check=False,
            text=True,
            capture_output=True,
        )

    def show_diff_summary(self) -> str:
        diff_stat = self._run(["git", "diff", "--stat"])
        summary = diff_stat.stdout.strip()
        print(summary if summary else "No changes detected.")
        return summary

    def commit_if_approved(self, summary: str) -> GitGateResult:
        diff_full = self._run(["git", "diff"])
        if diff_full.stdout.strip():
            print(diff_full.stdout)
        else:
            print("No diff to approve.")

        approved = input("Approve commit? (y/n): ").strip().lower() == "y"
        if not approved:
            return GitGateResult(approved=False, committed=False, summary=summary)

        add_result = self._run(["git", "add", "."])
        if add_result.returncode != 0:
            return GitGateResult(approved=True, committed=False, summary=summary)

        commit_result = self._run(["git", "commit", "-m", summary])
        committed = commit_result.returncode == 0
        return GitGateResult(approved=True, committed=committed, summary=summary)
