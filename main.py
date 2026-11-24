"""Mini NPU Simulator - MAC 연산으로 Cross / X 패턴을 판별한다."""

import json
import os
import time

EPSILON = 1e-9          # 동점 판단 허용오차
REPEAT = 10             # 성능 측정 반복 횟수
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.json")

# 라벨 정규화 표: 여러 표기 -> 표준 라벨(Cross / X)
LABEL_MAP = {
    "+": "Cross", "cross": "Cross",
    "x": "X",
}


def normalize_label(raw):
    """'+', 'cross', 'x' 등 다양한 표기를 표준 라벨로 바꾼다. 모르면 None."""
    if not isinstance(raw, str):
        return None
    return LABEL_MAP.get(raw.strip().lower())


# ---------------------------------------------------------------
# 데이터 구조: n×n 2차원 리스트
# ---------------------------------------------------------------
def make_matrix(n, value=0.0):
    return [[value for _ in range(n)] for _ in range(n)]


def set_value(matrix, row, col, value):
    matrix[row][col] = value


def get_value(matrix, row, col):
    return matrix[row][col]


def is_square(matrix, n):
    """matrix가 n×n 숫자 배열인지 검사한다."""
    if not isinstance(matrix, list) or len(matrix) != n:
        return False
    for row in matrix:
        if not isinstance(row, list) or len(row) != n:
            return False
        for v in row:
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                return False
    return True


# ---------------------------------------------------------------
# MAC 연산 (반복문으로 직접 구현)
# ---------------------------------------------------------------
def mac(pattern, filt):
    """같은 위치끼리 곱한 뒤 모두 더한 점수를 반환한다."""
    n = len(pattern)
    total = 0.0
    for i in range(n):
        for j in range(n):
            total += pattern[i][j] * filt[i][j]
    return total


def decide(score_a, score_b, label_a, label_b):
    """epsilon 기반 비교. 차이가 1e-9 미만이면 동점(None)."""
    if abs(score_a - score_b) < EPSILON:
        return None
    return label_a if score_a > score_b else label_b


def measure_ms(pattern, filt, repeat=REPEAT):
    """MAC 연산만 repeat번 반복해 평균 시간(ms)을 구한다. I/O 제외."""
    start = time.perf_counter()
    for _ in range(repeat):
        mac(pattern, filt)
    end = time.perf_counter()
    return (end - start) * 1000 / repeat


# ---------------------------------------------------------------
# 패턴 생성기 (성능 측정용)
# ---------------------------------------------------------------
def make_cross(n):
    m = make_matrix(n)
    mid = n // 2
    for k in range(n):
        set_value(m, mid, k, 1.0)
        set_value(m, k, mid, 1.0)
    return m


def make_x(n):
    m = make_matrix(n)
    for k in range(n):
        set_value(m, k, k, 1.0)
        set_value(m, k, n - 1 - k, 1.0)
    return m


# ---------------------------------------------------------------
# 출력 도우미
# ---------------------------------------------------------------
def section(title):
    print()
    print("#" + "-" * 40)
    print("# " + title)
    print("#" + "-" * 40)


def print_perf_table(sizes):
    print(f"{'크기':<10}{'평균 시간(ms)':>16}{'연산 횟수(N²)':>16}")
    print("-" * 44)
    for n in sizes:
        ms = measure_ms(make_cross(n), make_x(n))
        print(f"{f'{n}x{n}':<10}{ms:>16.4f}{n * n:>16}")


# ---------------------------------------------------------------
# 모드 1: 사용자 입력 (3×3)
# ---------------------------------------------------------------
def read_matrix(title, n=3):
    """n줄을 입력받는다. 형식이 틀리면 안내 후 처음부터 다시 받는다."""
    while True:
        print(f"{title} ({n}줄 입력, 공백 구분)")
        lines = [input().split() for _ in range(n)]   # n줄을 모두 받은 뒤 검사
        rows = []
        ok = True
        for parts in lines:
            if len(parts) != n:
                ok = False
                break
            try:
                rows.append([float(p) for p in parts])
            except ValueError:
                ok = False
                break
        if ok:
            return rows
        print(f"입력 형식 오류: 각 줄에 {n}개의 숫자를 공백으로 구분해 입력하세요. 다시 입력합니다.\n")


def mode_user():
    section("[1] 필터 입력")
    filter_a = read_matrix("필터 A")
    print()
    filter_b = read_matrix("필터 B")
    print("\n필터 A, B 저장 완료")

    section("[2] 패턴 입력")
    pattern = read_matrix("패턴")

    section("[3] MAC 결과")
    score_a = mac(pattern, filter_a)
    score_b = mac(pattern, filter_b)
    ms = (measure_ms(pattern, filter_a) + measure_ms(pattern, filter_b)) / 2
    result = decide(score_a, score_b, "A", "B")
    print(f"A 점수: {score_a}")
    print(f"B 점수: {score_b}")
    print(f"연산 시간(평균/{REPEAT}회): {ms:.4f} ms")
    if result is None:
        print(f"판정: 판정 불가 (|A-B| < {EPSILON})")
    else:
        print(f"판정: {result}")

    section(f"[4] 성능 분석 (평균/{REPEAT}회)")
    print_perf_table([3])


# ---------------------------------------------------------------
# 모드 2: data.json 분석
# ---------------------------------------------------------------
def load_filters(raw_filters):
    """{'size_5': {'Cross': [...], 'X': [...]}, ...} 형태로 정규화해 반환."""
    filters = {}
    if not isinstance(raw_filters, dict):
        print("[오류] filters 항목이 없거나 형식이 잘못되었습니다.")
        return filters
    for size_key, pair in raw_filters.items():
        if not isinstance(pair, dict):
            print(f"[오류] {size_key}: 필터 형식이 잘못되었습니다.")
            continue
        normalized = {}
        for label_key, matrix in pair.items():
            label = normalize_label(label_key)
            if label is None:
                print(f"[오류] {size_key}: 알 수 없는 필터 키 '{label_key}'")
                continue
            normalized[label] = matrix
        if "Cross" in normalized and "X" in normalized:
            filters[size_key] = normalized
            print(f"[OK] {size_key:<8} 필터 로드 완료 (Cross, X)")
        else:
            print(f"[오류] {size_key}: Cross/X 필터가 모두 있어야 합니다.")
    return filters


def size_from_key(key):
    """'size_13_2' -> 13. 규칙에 안 맞으면 None."""
    parts = key.split("_")
    if len(parts) != 3 or parts[0] != "size":
        return None
    try:
        return int(parts[1])
    except ValueError:
        return None


def analyze_case(key, case, filters):
    """한 케이스를 분석하고 (통과 여부, 실패 사유)를 반환한다. 예외로 멈추지 않는다."""
    n = size_from_key(key)
    if n is None:
        return False, "키 형식 오류 (size_N_idx 아님)"
    if not isinstance(case, dict):
        return False, "케이스 형식 오류"

    filt = filters.get(f"size_{n}")
    if filt is None:
        return False, f"size_{n} 필터 없음"

    pattern = case.get("input")
    if not is_square(pattern, n):
        return False, f"패턴 크기 불일치 (기대 {n}x{n})"
    if not is_square(filt["Cross"], n) or not is_square(filt["X"], n):
        return False, f"필터 크기 불일치 (기대 {n}x{n})"

    expected = normalize_label(case.get("expected"))
    if expected is None:
        return False, f"알 수 없는 expected 값 '{case.get('expected')}'"

    score_cross = mac(pattern, filt["Cross"])
    score_x = mac(pattern, filt["X"])
    result = decide(score_cross, score_x, "Cross", "X")
    shown = result if result else "UNDECIDED"

    print(f"Cross 점수: {score_cross}")
    print(f"X 점수: {score_x}")
    if result == expected:
        print(f"판정: {shown} | expected: {expected} | PASS")
        return True, ""
    if result is None:
        print(f"판정: {shown} | expected: {expected} | FAIL (동점 규칙)")
        return False, "동점(UNDECIDED) 처리 규칙에 따라 FAIL"
    print(f"판정: {shown} | expected: {expected} | FAIL")
    return False, f"판정 {shown} ≠ expected {expected}"


def mode_json():
    try:
        with open(DATA_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"[오류] data.json을 찾을 수 없습니다: {DATA_FILE}")
        return
    except json.JSONDecodeError as e:
        print(f"[오류] data.json 형식이 잘못되었습니다: {e}")
        return

    section("[1] 필터 로드")
    filters = load_filters(data.get("filters"))

    section("[2] 패턴 분석 (라벨 정규화 적용)")
    patterns = data.get("patterns")
    if not isinstance(patterns, dict):
        print("[오류] patterns 항목이 없거나 형식이 잘못되었습니다.")
        patterns = {}

    passed = 0
    failures = []
    for key, case in patterns.items():
        print(f"--- {key} ---")
        try:
            ok, reason = analyze_case(key, case, filters)
        except Exception as e:   # 예상 못 한 데이터도 케이스 단위 FAIL로 처리
            ok, reason = False, f"처리 중 오류: {e}"
        if ok:
            passed += 1
        else:
            if not reason.startswith("동점") and "≠" not in reason:
                print(f"FAIL: {reason}")
            failures.append((key, reason))

    section(f"[3] 성능 분석 (평균/{REPEAT}회)")
    print_perf_table([3, 5, 13, 25])

    section("[4] 결과 요약")
    total = len(patterns)
    print(f"총 테스트: {total}개")
    print(f"통과: {passed}개")
    print(f"실패: {len(failures)}개")
    if failures:
        print("\n실패 케이스:")
        for key, reason in failures:
            print(f"- {key}: {reason}")
    print('\n(상세 원인 분석 및 복잡도 설명은 README.md의 "결과 리포트" 섹션 참고)')


# ---------------------------------------------------------------
# 시작
# ---------------------------------------------------------------
def main():
    print("=== Mini NPU Simulator ===")
    while True:
        print("\n[모드 선택]")
        print("1. 사용자 입력 (3x3)")
        print("2. data.json 분석")
        choice = input("선택: ").strip()
        if choice == "1":
            mode_user()
            break
        if choice == "2":
            mode_json()
            break
        print("1 또는 2를 입력하세요.")


if __name__ == "__main__":
    main()
