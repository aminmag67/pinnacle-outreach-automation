#!/usr/bin/env python3
import subprocess
import sys

COMMANDS = [
    ("Inspect CRM", ["python", "inspect_crm.py"]),
    ("Due follow-ups", ["python", "crm_due_followups.py"]),
    ("Review queue", ["python", "crm_review_queue.py"]),
    ("Preproduction check", ["python", "crm_preproduction_check.py"]),
]


def run_command(title, command):
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)

    result = subprocess.run(command, text=True)

    if result.returncode != 0:
        print()
        print(f"WARNING: {title} exited with code {result.returncode}")

    return result.returncode


def main():
    print("Pinnacle CRM Daily Check")
    print("=" * 80)

    exit_codes = []

    for title, command in COMMANDS:
        exit_codes.append(run_command(title, command))

    print()
    print("=" * 80)
    print("Next steps")
    print("=" * 80)
    print("1. Review any due follow-ups.")
    print("2. Review any leads in the review queue.")
    print("3. Run python export_crm.py after making CRM changes.")
    print("4. Back up pinnacle_crm.db and crm_exports to Google Drive.")
    print("5. Do not run real draft mode unless intentionally approved.")

    if any(code != 0 for code in exit_codes):
        print()
        print("Daily check completed with warnings.")
        return 1

    print()
    print("Daily check completed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
