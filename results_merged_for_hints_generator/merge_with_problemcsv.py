import argparse
import csv
import json
import os
from typing import Any, Dict


def resolve_path(base_dir: str, maybe_relative_path: str) -> str:
	if os.path.isabs(maybe_relative_path):
		return maybe_relative_path
	return os.path.normpath(os.path.join(base_dir, maybe_relative_path))


def normalize_problem_id(value: Any) -> str:
	if value is None:
		return ""
	return str(value).strip()


def ensure_dict(value: Any) -> Dict[str, Any]:
	if isinstance(value, dict):
		return value
	return {}


def merge_statements_from_csv(merged_file: str, csv_file: str) -> None:
	csv.field_size_limit(10**9)

	with open(merged_file, "r", encoding="utf-8") as f:
		merged_data = json.load(f)

	if not isinstance(merged_data, dict):
		raise ValueError("Merged file must contain a JSON object/dict")

	filled_null = 0
	skipped_non_null = 0
	missing_in_merged = 0
	invalid_rows = 0

	with open(csv_file, "r", encoding="utf-8", newline="") as f:
		reader = csv.DictReader(f, delimiter=";")
		expected = {"problem_id", "problem_statement"}
		if not reader.fieldnames or not expected.issubset(set(reader.fieldnames)):
			raise ValueError(
				"CSV must contain columns: problem_id and problem_statement"
			)

		for row in reader:
			problem_id = normalize_problem_id(row.get("problem_id"))
			statement = row.get("problem_statement")

			if not problem_id or statement is None:
				invalid_rows += 1
				continue

			if problem_id not in merged_data:
				missing_in_merged += 1
				continue

			entry = ensure_dict(merged_data.get(problem_id))
			old_statement = entry.get("statement")
			if old_statement is None:
				entry["statement"] = statement
				merged_data[problem_id] = entry
				filled_null += 1
			else:
				skipped_non_null += 1

	with open(merged_file, "w", encoding="utf-8") as f:
		json.dump(merged_data, f, ensure_ascii=False, indent=2, sort_keys=True)

	print("=== problems.csv -> merged completed ===")
	print(f"Filled null statements: {filled_null}")
	print(f"Skipped non-null statements: {skipped_non_null}")
	print(f"Rows missing in merged: {missing_in_merged}")
	print(f"Skipped invalid rows: {invalid_rows}")
	print(f"Total in merged now: {len(merged_data)}")
	print(f"Updated file: {merged_file}")


def main() -> None:
	script_dir = os.path.dirname(os.path.abspath(__file__))
	project_root = os.path.dirname(script_dir)

	parser = argparse.ArgumentParser(
		description="Fill only null statements in code_solution_hints_merged.json using problems.csv"
	)
	parser.add_argument(
		"--merged-file",
		default=os.path.join(script_dir, "code_solution_hints_merged.json"),
		help="Path to merged JSON file",
	)
	parser.add_argument(
		"--csv-file",
		default=os.path.join(project_root, "Hints", "problems.csv"),
		help="Path to problems.csv",
	)
	args = parser.parse_args()

	merged_file = resolve_path(project_root, args.merged_file)
	csv_file = resolve_path(project_root, args.csv_file)

	if not os.path.exists(merged_file):
		raise FileNotFoundError(f"Merged file not found: {merged_file}")
	if not os.path.exists(csv_file):
		raise FileNotFoundError(f"CSV file not found: {csv_file}")

	merge_statements_from_csv(merged_file=merged_file, csv_file=csv_file)


if __name__ == "__main__":
	main()
