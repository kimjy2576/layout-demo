"""Mock DB simulating HPWD internal data.
실제로는 PostgreSQL / TimescaleDB에 있을 데이터.
시현용으로 Python dict로 단순화.
"""

# 모델 카탈로그
MODELS = {
    "HPWD-24-EU": {
        "model_id": "HPWD-24-EU",
        "model_name": "HPWD-24-EU (양산)",
        "category": "프리미엄",
        "launch_date": "2024-01-15",
        "department": "R&D 1팀",
        "components": ["HPWD-24-EU-CMP", "HPWD-24-EU-HX", "HPWD-24-EU-FAN", "HPWD-24-EU-EEV"],
        "spec": {
            "rated_capacity_kg": 10.0,
            "smer_target": 0.55,
            "noise_db_target": 65,
        }
    },
    "HPWD-27-KR": {
        "model_id": "HPWD-27-KR",
        "model_name": "HPWD-27-KR (양산)",
        "category": "프리미엄+",
        "launch_date": "2024-06-01",
        "department": "R&D 1팀",
        "components": ["HPWD-27-KR-CMP", "HPWD-27-KR-HX", "HPWD-27-KR-FAN", "HPWD-27-KR-EEV"],
        "spec": {
            "rated_capacity_kg": 12.0,
            "smer_target": 0.60,
            "noise_db_target": 63,
        }
    },
    "HPWD-29-UN": {
        "model_id": "HPWD-29-UN",
        "model_name": "HPWD-29-UN (개발 중)",
        "category": "보급형",
        "launch_date": "2025-03-10",
        "department": "R&D 2팀",
        "components": ["HPWD-29-UN-CMP", "HPWD-29-UN-HX", "HPWD-29-UN-FAN", "HPWD-29-UN-EEV"],
        "spec": {
            "rated_capacity_kg": 9.0,
            "smer_target": 0.50,
            "noise_db_target": 67,
        }
    },
}

# 컴포넌트 카탈로그
COMPONENTS = {
    "HPWD-24-EU-CMP": {"id": "HPWD-24-EU-CMP", "type": "압축기", "capacity_cc": 8.0, "rpm_range": "1500-3500", "vendor": "벤더A"},
    "HPWD-24-EU-HX": {"id": "HPWD-24-EU-HX", "type": "응축기/증발기", "ua_w_per_k": 124, "fin_density": "high"},
    "HPWD-24-EU-FAN": {"id": "HPWD-24-EU-FAN", "type": "팬", "max_cfm": 280},
    "HPWD-24-EU-EEV": {"id": "HPWD-24-EU-EEV", "type": "EEV", "max_step": 480},

    "HPWD-27-KR-CMP": {"id": "HPWD-27-KR-CMP", "type": "압축기", "capacity_cc": 10.0, "rpm_range": "1500-3800", "vendor": "벤더A"},
    "HPWD-27-KR-HX": {"id": "HPWD-27-KR-HX", "type": "응축기/증발기", "ua_w_per_k": 152, "fin_density": "ultra-high"},
    "HPWD-27-KR-FAN": {"id": "HPWD-27-KR-FAN", "type": "팬", "max_cfm": 320},
    "HPWD-27-KR-EEV": {"id": "HPWD-27-KR-EEV", "type": "EEV", "max_step": 480},

    "HPWD-29-UN-CMP": {"id": "HPWD-29-UN-CMP", "type": "압축기", "capacity_cc": 7.0, "rpm_range": "1500-3000", "vendor": "벤더B"},
    "HPWD-29-UN-HX": {"id": "HPWD-29-UN-HX", "type": "응축기/증발기", "ua_w_per_k": 108, "fin_density": "medium"},
    "HPWD-29-UN-FAN": {"id": "HPWD-29-UN-FAN", "type": "팬", "max_cfm": 240},
    "HPWD-29-UN-EEV": {"id": "HPWD-29-UN-EEV", "type": "EEV", "max_step": 360},
}

# 시험 보고서
TESTS = {
    "T-HPWD24EU-001": {
        "test_id": "T-HPWD24EU-001",
        "model_id": "HPWD-24-EU",
        "test_date": "2024-03-15",
        "result": "PASS",
        "smer_kg_per_kwh": 0.62,
        "drying_time_min": 165,
        "noise_db": 64.2,
        "summary": "정상 — SMER 목표 0.55 초과 달성"
    },
    "T-HPWD24EU-002": {
        "test_id": "T-HPWD24EU-002",
        "model_id": "HPWD-24-EU",
        "test_date": "2024-04-22",
        "result": "FAIL",
        "smer_kg_per_kwh": 0.45,
        "drying_time_min": 220,
        "noise_db": 64.8,
        "summary": "FAIL — SMER 0.45 (목표 0.55 대비 18% 부족) · 건조 시간 33% 초과 · 청구사항: '빨래가 안 말라'"
    },
    "T-HPWD24EU-003": {
        "test_id": "T-HPWD24EU-003",
        "model_id": "HPWD-24-EU",
        "test_date": "2024-05-10",
        "result": "PASS",
        "smer_kg_per_kwh": 0.60,
        "drying_time_min": 170,
        "noise_db": 64.5,
        "summary": "응축기 UA 14% 증가 후 재시험 — PASS"
    },
    "T-HPWD27KR-001": {
        "test_id": "T-HPWD27KR-001",
        "model_id": "HPWD-27-KR",
        "test_date": "2024-08-03",
        "result": "PASS",
        "smer_kg_per_kwh": 0.65,
        "drying_time_min": 152,
        "noise_db": 62.8,
        "summary": "정상 — 모든 목표 달성"
    },
}

# 사내 설계 가이드 (RAG용 문서)
DESIGN_GUIDES = [
    {
        "doc_id": "DG-001",
        "title": "건조기 SMER 저하 원인 5가지",
        "category": "트러블슈팅",
        "content": (
            "건조기 SMER(Specific Moisture Extraction Rate, kg/kWh)이 목표보다 낮을 때 의심 원인:\n"
            "1. 응축기(Condenser) UA 부족 — 가장 흔한 원인. 열교환 면적·핀 밀도 점검\n"
            "2. 압축기 효율 저하 — 운전 시간 누적, 냉매 누설 확인\n"
            "3. 팬 풍량 부족 — 필터 막힘, 모터 노화\n"
            "4. EEV 제어 이상 — 과열도 제어 점검\n"
            "5. 냉매 충전량 부족 — Subcooling/Superheat 측정\n"
            "→ 1번 확인이 80% 케이스 해결"
        )
    },
    {
        "doc_id": "DG-002",
        "title": "응축기 UA 14% 증가 권장 사례",
        "category": "설계변경",
        "content": (
            "HPWD-24-EU 모델 SMER 저하 사례에서, 응축기 UA를 124 → 141 W/K (14% 증가)로 변경 후\n"
            "SMER 0.45 → 0.60 kg/kWh로 회복. 변경 비용 ~5% 증가, 건조 시간 23% 단축.\n"
            "권장 — UA 증가는 응축기 면적 확대 또는 핀 밀도 강화로 구현."
        )
    },
    {
        "doc_id": "DG-003",
        "title": "IEC 61121 §5.2 — 건조기 효율 기준",
        "category": "규격",
        "content": (
            "IEC 61121 §5.2 — 가정용 건조기 SMER 기준:\n"
            "- 표준급 (Class C): SMER ≥ 0.40 kg/kWh\n"
            "- 효율급 (Class A): SMER ≥ 0.50 kg/kWh\n"
            "- 고효율급 (A+): SMER ≥ 0.55 kg/kWh\n"
            "측정 — IEC 61121 부속서 B 표준 부하 (3.5kg, 60% 함수율)"
        )
    },
    {
        "doc_id": "DG-004",
        "title": "응축기·증발기 UA 계산 (ε-NTU)",
        "category": "이론",
        "content": (
            "ε-NTU 방법에서 UA = NTU × C_min\n"
            "건조기 응축기는 일반적으로 Cross-flow Unmixed 구성.\n"
            "효율 ε = 1 - exp(-NTU·(1-Cr)) / (1 - Cr·exp(-NTU·(1-Cr)))\n"
            "UA 증가 시 → 응축 압력 감소 → 압축비 감소 → COP 상승 → SMER 향상"
        )
    },
]


def find_model(query: str) -> dict | None:
    """모델명 또는 부분 일치로 모델 찾기."""
    query_upper = query.upper().strip()
    for model_id, model in MODELS.items():
        if query_upper == model_id or query_upper in model["model_name"].upper():
            return model
    return None


def find_components_for(model_id: str) -> list[dict]:
    """특정 모델의 컴포넌트 리스트."""
    model = MODELS.get(model_id)
    if not model:
        return []
    return [COMPONENTS[c] for c in model["components"] if c in COMPONENTS]


def find_recent_test(model_id: str) -> dict | None:
    """특정 모델의 가장 최근 시험 결과."""
    tests = [t for t in TESTS.values() if t["model_id"] == model_id]
    if not tests:
        return None
    return max(tests, key=lambda t: t["test_date"])


def search_docs(query: str, top_k: int = 3) -> list[dict]:
    """단순 키워드 기반 사내 문서 검색 (실제로는 벡터 DB)."""
    keywords = query.lower().replace(",", " ").split()
    scored = []
    for doc in DESIGN_GUIDES:
        text = (doc["title"] + " " + doc["content"]).lower()
        score = sum(1 for k in keywords if k in text)
        if score > 0:
            scored.append((score, doc))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [d for _, d in scored[:top_k]]
