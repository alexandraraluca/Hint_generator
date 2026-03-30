import argparse
import json
import os
import re
from typing import Any, Dict


def resolve_path(base_dir: str, maybe_relative_path: str) -> str:
	if os.path.isabs(maybe_relative_path):
		return maybe_relative_path
	return os.path.normpath(os.path.join(base_dir, maybe_relative_path))


def build_link_from_problem_id(problem_id: str) -> str:
	match = re.match(r"^(\d+)([A-Za-z][A-Za-z0-9]*)$", str(problem_id))
	if not match:
		return None
	contest_id, index = match.groups()
	return f"/problemset/problem/{contest_id}/{index}"


def to_tutorial_payload(forum_item: Dict[str, Any]) -> Dict[str, Any]:
	return {
		"code": forum_item.get("code"),
		"solution": forum_item.get("solution"),
		"hints": forum_item.get("hints"),
	}


def merge_missing_from_forum(merged_file: str, forum_file: str) -> None:
	with open(merged_file, "r", encoding="utf-8") as f:
		merged_data = json.load(f)

	with open(forum_file, "r", encoding="utf-8") as f:
		forum_data = json.load(f)

	if not isinstance(merged_data, dict):
		raise ValueError("Merged file must contain a JSON object/dict")
	if not isinstance(forum_data, list):
		raise ValueError("Forum file must contain a JSON array/list")

	added = 0
	skipped_existing = 0
	skipped_invalid = 0

	for item in forum_data:
		if not isinstance(item, dict):
			skipped_invalid += 1
			continue

		problem_id = item.get("problem_id")
		if not problem_id:
			skipped_invalid += 1
			continue

		problem_id = str(problem_id)
		if problem_id in merged_data:
			skipped_existing += 1
			continue

		merged_data[problem_id] = {
			"name": f"{problem_id} - Unknown",
			"link": build_link_from_problem_id(problem_id),
			"statement": None,
			"tutorial": to_tutorial_payload(item),
		}
		added += 1

	with open(merged_file, "w", encoding="utf-8") as f:
		json.dump(merged_data, f, ensure_ascii=False, indent=2, sort_keys=True)

	print("=== Forum -> Merged completed ===")
	print(f"Added missing problems: {added}")
	print(f"Skipped existing problems: {skipped_existing}")
	print(f"Skipped invalid forum entries: {skipped_invalid}")
	print(f"Total in merged now: {len(merged_data)}")
	print(f"Updated file: {merged_file}")


def main() -> None:
	script_dir = os.path.dirname(os.path.abspath(__file__))
	project_root = os.path.dirname(script_dir)

	parser = argparse.ArgumentParser(
		description="Add only missing forum problems into code_solution_hints_merged.json"
	)
	parser.add_argument(
		"--merged-file",
		default=os.path.join(script_dir, "code_solution_hints_merged.json"),
		help="Path to merged JSON file",
	)
	parser.add_argument(
		"--forum-file",
		default=os.path.join(project_root, "Hints", "forum_posts_processed.json"),
		help="Path to forum_posts_processed.json",
	)

	args = parser.parse_args()

	merged_file = resolve_path(project_root, args.merged_file)
	forum_file = resolve_path(project_root, args.forum_file)

	if not os.path.exists(merged_file):
		raise FileNotFoundError(f"Merged file not found: {merged_file}")
	if not os.path.exists(forum_file):
		raise FileNotFoundError(f"Forum file not found: {forum_file}")

	merge_missing_from_forum(merged_file, forum_file)


if __name__ == "__main__":
	main()
