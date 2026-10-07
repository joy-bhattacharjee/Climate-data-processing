from pathlib import Path
import re
import json

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "backend" / "scripts_new"
REPORT_FILE = ROOT / "outputs" / "path_verification_report.json"

# ------------------------------------------------------------
# Patterns that usually indicate old hardcoded path logic
# ------------------------------------------------------------
PATTERNS = {
    "hardcoded_windows_user_path": re.compile(
        r'[rR]?[\'"]([A-Za-z]:\\Users\\[^\'"]+)[\'"]'
    ),
    "hardcoded_windows_absolute_path": re.compile(
        r'[rR]?[\'"]([A-Za-z]:\\[^\'"]+)[\'"]'
    ),
    "os_chdir": re.compile(r'\bos\.chdir\s*\('),
    "input_dir_assignment": re.compile(r'^\s*INPUT_DIR\s*=', re.M),
    "output_dir_assignment": re.compile(r'^\s*OUTPUT_DIR\s*=', re.M),
    "base_dir_assignment": re.compile(r'^\s*BASE_DIR\s*=', re.M),
    "obs_dir_assignment": re.compile(r'^\s*OBS_DIR\s*=', re.M),
    "work_dir_assignment": re.compile(r'^\s*WORK_DIR\s*=', re.M),
    "netcdf_dir_assignment": re.compile(r'^\s*NETCDF_DIR\s*=', re.M),
    "gridded_files_assignment": re.compile(r'^\s*GRIDDED_FILES\s*=', re.M),
    "path_com_assignment": re.compile(r'^\s*path_com\s*=', re.M),
    "temp_zip_dir_assignment": re.compile(r'^\s*TEMP_ZIP_DIR\s*=', re.M),
    "final_output_dir_assignment": re.compile(r'^\s*FINAL_OUTPUT_DIR\s*=', re.M),
    "output_csv_assignment": re.compile(r'^\s*OUTPUT_CSV\s*=', re.M),
    "legacy_folder_name_gridded_data": re.compile(r'gridded_data'),
    "legacy_folder_name_daily_ts": re.compile(r'sievi_daily_time_series'),
    "legacy_folder_name_netcdf": re.compile(r'sievi_cropped_netcdf_ready'),
    "legacy_folder_name_dt": re.compile(r'for_generating_dt_files'),
}

# ------------------------------------------------------------
# Things that indicate the script is already partly portable
# ------------------------------------------------------------
GOOD_SIGNS = {
    "common_paths_import": re.compile(r'_common_paths\s+import'),
    "env_repo_root": re.compile(r'REPO_ROOT'),
    "env_outputs_dir": re.compile(r'OUTPUTS_DIR'),
    "cfg_usage": re.compile(r'\bcfg\s*\('),
    "pathlib_usage": re.compile(r'\bPath\s*\('),
}

def get_line_number(text: str, char_index: int) -> int:
    return text.count("\n", 0, char_index) + 1

def scan_file(file_path: Path):
    text = file_path.read_text(encoding="utf-8", errors="replace")
    issues = []
    good = []

    # Good signs
    for name, pattern in GOOD_SIGNS.items():
        if pattern.search(text):
            good.append(name)

    # Issues
    for name, pattern in PATTERNS.items():
        for match in pattern.finditer(text):
            line_no = get_line_number(text, match.start())
            snippet = text.splitlines()[line_no - 1].strip() if line_no <= len(text.splitlines()) else ""
            issues.append({
                "type": name,
                "line": line_no,
                "match": match.group(0),
                "snippet": snippet[:300]
            })

    # Risk scoring
    score = 0
    for item in issues:
        t = item["type"]
        if t in ["hardcoded_windows_user_path", "hardcoded_windows_absolute_path", "os_chdir"]:
            score += 5
        elif t in [
            "input_dir_assignment", "output_dir_assignment", "base_dir_assignment",
            "obs_dir_assignment", "work_dir_assignment", "netcdf_dir_assignment",
            "gridded_files_assignment", "path_com_assignment",
            "temp_zip_dir_assignment", "final_output_dir_assignment",
            "output_csv_assignment"
        ]:
            score += 2
        else:
            score += 1

    status = "clean"
    if score >= 12:
        status = "high-risk"
    elif score >= 5:
        status = "needs-review"

    return {
        "file": str(file_path.relative_to(ROOT)).replace("\\", "/"),
        "status": status,
        "risk_score": score,
        "good_signs": sorted(good),
        "issues": issues
    }

def summarize(results):
    total = len(results)
    clean = sum(1 for r in results if r["status"] == "clean")
    needs_review = sum(1 for r in results if r["status"] == "needs-review")
    high_risk = sum(1 for r in results if r["status"] == "high-risk")

    hardcoded_total = 0
    chdir_total = 0

    for r in results:
        for issue in r["issues"]:
            if issue["type"] in ["hardcoded_windows_user_path", "hardcoded_windows_absolute_path"]:
                hardcoded_total += 1
            if issue["type"] == "os_chdir":
                chdir_total += 1

    return {
        "total_files_scanned": total,
        "clean_files": clean,
        "needs_review_files": needs_review,
        "high_risk_files": high_risk,
        "hardcoded_path_hits": hardcoded_total,
        "os_chdir_hits": chdir_total,
    }

def print_console_summary(results):
    summary = summarize(results)

    print("=" * 80)
    print("SECOND-PASS PATH VERIFICATION REPORT")
    print("=" * 80)
    print(f"Scripts scanned        : {summary['total_files_scanned']}")
    print(f"Clean                  : {summary['clean_files']}")
    print(f"Needs review           : {summary['needs_review_files']}")
    print(f"High risk              : {summary['high_risk_files']}")
    print(f"Hardcoded path hits    : {summary['hardcoded_path_hits']}")
    print(f"os.chdir hits          : {summary['os_chdir_hits']}")
    print("=" * 80)

    for r in sorted(results, key=lambda x: (-x["risk_score"], x["file"])):
        print(f"\n[{r['status'].upper()}] {r['file']}  (risk={r['risk_score']})")
        if r["good_signs"]:
            print("  good signs:", ", ".join(r["good_signs"]))
        if r["issues"]:
            for issue in r["issues"][:8]:
                print(f"  - line {issue['line']:>4}: {issue['type']}")
                print(f"    {issue['snippet']}")
            if len(r["issues"]) > 8:
                print(f"    ... and {len(r['issues']) - 8} more issue(s)")
        else:
            print("  No suspicious path patterns found.")

def main():
    if not SCRIPTS_DIR.exists():
        raise SystemExit(f"Scripts directory not found: {SCRIPTS_DIR}")

    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)

    results = []
    for file_path in sorted(SCRIPTS_DIR.glob("*.py")):
        if file_path.name.startswith("_"):
            continue
        results.append(scan_file(file_path))

    report = {
        "root": str(ROOT),
        "scripts_dir": str(SCRIPTS_DIR),
        "summary": summarize(results),
        "results": results,
    }

    REPORT_FILE.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print_console_summary(results)
    print("\nJSON report written to:")
    print(REPORT_FILE)

if __name__ == "__main__":
    main()
