import json
import re
from pathlib import Path

import pdfplumber

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR     = PROJECT_ROOT / "data"
ASSETS_DIR   = PROJECT_ROOT / "assets"
PDF_PATH     = DATA_DIR / "2025학년도 신입생 학부별 졸업요건.pdf"
OUTPUT_PATH  = ASSETS_DIR / "CourseMapping.json"


def is_course_code(word):
    match = re.search(r"[A-Z]{3,4}\d{4}", str(word))
    return match.group(0) if match else None


def clean_text(text):
    if text is None:
        return ""
    return re.sub(r"\s+", "", str(text))


def parse_course_mapping(pdf_path=PDF_PATH, output_path=OUTPUT_PATH):
    course_dict = {}

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            if not tables:
                continue

            for table in tables:
                code_col_idx, name_col_idx = -1, -1
                for row in table:
                    clean_row = [clean_text(cell) for cell in row]
                    for i, cell_text in enumerate(clean_row):
                        if "학정" in cell_text and "번호" in cell_text:
                            code_col_idx = i
                        if "과목" in cell_text or "교과목" in cell_text:
                            name_col_idx = i
                    if code_col_idx != -1 and name_col_idx != -1:
                        break

                if code_col_idx != -1 and name_col_idx != -1:
                    for row in table:
                        code_val = row[code_col_idx]
                        name_val = row[name_col_idx]

                        code = is_course_code(code_val)
                        if code and name_val:
                            new_name = name_val.replace("\n", "").replace(" ", "").strip()

                            if code in course_dict:
                                if re.search(r"[가-힣]", course_dict[code]):
                                    continue
                                if re.search(r"[가-힣]", new_name):
                                    course_dict[code] = new_name
                            else:
                                course_dict[code] = new_name

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(course_dict, f, ensure_ascii=False, indent=4)

    return course_dict


if __name__ == "__main__":
    result = parse_course_mapping()
    print(f"\nParsed {len(result)} courses.")
    print(f"Saved to: {OUTPUT_PATH}")
