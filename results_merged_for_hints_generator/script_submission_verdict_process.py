import glob
import json
import os
import re
from typing import Any, Dict, Optional, Tuple

from bs4 import BeautifulSoup


def read_html(file_path: str) -> BeautifulSoup:
	with open(file_path, "r", encoding="utf-8") as f:
		return BeautifulSoup(f.read(), "html.parser")


def extract_submission_id_from_filename(file_path: str) -> Optional[str]:
	base = os.path.basename(file_path)
	match = re.match(r"submission_(\d+)\.html$", base)
	return match.group(1) if match else None


def extract_problem_id(submission_soup: BeautifulSoup) -> Optional[str]:
	# Prefer exact Codeforces pattern in links: /problemset/problem/<contest>/<index>
	for a in submission_soup.find_all("a", href=True):
		href = a.get("href", "")
		match = re.search(r"/problemset/problem/(\d+)/([A-Za-z0-9]+)", href)
		if match:
			contest_id, index = match.groups()
			return f"{contest_id}{index}"

	# Fallback: use anchor text if it looks like 1619E, 1497C1 etc.
	for a in submission_soup.find_all("a"):
		text = a.get_text(strip=True)
		if re.match(r"^\d+[A-Za-z][A-Za-z0-9]*$", text):
			return text

	return None


def extract_code(submission_soup: BeautifulSoup) -> Optional[str]:
	code_block = submission_soup.find("pre", id="program-source-text")
	if not code_block:
		return None

	# Keep line breaks where possible.
	code_text = code_block.get_text("\n", strip=True)
	return code_text if code_text else None


def extract_verdict_and_test(verdict_file_path: str) -> Tuple[str, Optional[Dict[str, Any]]]:
	if not os.path.exists(verdict_file_path):
		return "Accepted", None

	soup = read_html(verdict_file_path)

	verdict_span = soup.find("span", class_="verdict")
	verdict_text = verdict_span.get_text(strip=True) if verdict_span else "Unknown"

	def text_or_none(selector: Tuple[str, str]) -> Optional[str]:
		tag, class_name = selector
		node = soup.find(tag, class_=class_name)
		if not node:
			return None
		value = node.get_text("\n", strip=True)
		return value if value else None

	test_obj = {
		"test_number": text_or_none(("span", "test")),
		"time_ms": text_or_none(("span", "timeConsumed")),
		"memory_kb": text_or_none(("span", "memoryConsumed")),
		"input": text_or_none(("pre", "input")),
		"participant_output": text_or_none(("pre", "output")),
		"jury_answer": text_or_none(("pre", "answer")),
		"checker_comment": text_or_none(("pre", "checkerComment")),
		"diagnostics": text_or_none(("pre", "diagnostics")),
	}

	# If file exists but we extracted nothing useful, keep null test.
	if all(value is None for value in test_obj.values()):
		test_obj = None

	return verdict_text, test_obj


def find_submission_and_verdict_dirs(results_dir: str) -> Tuple[Optional[str], Optional[str]]:
	submission_candidates = sorted(glob.glob(os.path.join(results_dir, "submission_pages*")))
	verdict_candidates = sorted(glob.glob(os.path.join(results_dir, "verdict*")))

	submission_dir = submission_candidates[0] if submission_candidates else None
	verdict_dir = verdict_candidates[0] if verdict_candidates else None
	return submission_dir, verdict_dir


def process_all_results(project_root: str) -> Dict[str, Any]:
	output: Dict[str, Any] = {}
	total_files = 0
	duplicates = 0

	results_folders = sorted(
		path
		for path in glob.glob(os.path.join(project_root, "results*"))
		if os.path.isdir(path)
	)

	for results_dir in results_folders:
		submission_dir, verdict_dir = find_submission_and_verdict_dirs(results_dir)
		if not submission_dir:
			continue

		submission_files = sorted(glob.glob(os.path.join(submission_dir, "submission_*.html")))
		for submission_file in submission_files:
			total_files += 1
			submission_id = extract_submission_id_from_filename(submission_file)
			if not submission_id:
				continue

			if submission_id in output:
				duplicates += 1
				continue

			submission_soup = read_html(submission_file)
			problem_id = extract_problem_id(submission_soup)
			code = extract_code(submission_soup)

			verdict_file = (
				os.path.join(verdict_dir, f"submission_{submission_id}.html")
				if verdict_dir
				else ""
			)
			verdict, test_obj = extract_verdict_and_test(verdict_file)

			output[submission_id] = {
				"submission_id": submission_id,
				"problem_id": problem_id,
				"code": code,
				"verdict": verdict,
				"test": test_obj,
			}

	print("=== Submission Verdict Build Completed ===")
	print(f"Results folders scanned: {len(results_folders)}")
	print(f"Submission files scanned: {total_files}")
	print(f"Unique submissions written: {len(output)}")
	print(f"Duplicate submission IDs skipped: {duplicates}")

	return output


def main() -> None:
	script_dir = os.path.dirname(os.path.abspath(__file__))
	project_root = os.path.dirname(script_dir)
	output_file = os.path.join(script_dir, "submission_verdict.json")

	data = process_all_results(project_root)

	with open(output_file, "w", encoding="utf-8") as f:
		json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)

	print(f"Output file: {output_file}")


if __name__ == "__main__":
	main()
