"""LLM Tool-use 도구 정의 + 실행기.

발표자료 슬라이드 9 ③ 외부 LLM API + Tool-use 의 4종 도구:
- DB 조회
- 1D 시뮬
- 최적화 호출
- 3D 렌더 (시현용은 제외, 시각화는 프런트가 담당)

여기서는 실용적으로 4개:
  search_documents — RAG (사내 자료)
  query_components — 모델·컴포넌트 DB
  run_simulation — 1D 시뮬레이터 호출
  suggest_optimization — 최적화 도구
"""
from typing import Any
import time
import math
from mock_db import MODELS, find_model, find_components_for, find_recent_test, search_docs


# ============================================================
# Tool schemas (Anthropic Tool-use format)
# ============================================================
TOOL_DEFINITIONS = [
    {
        "name": "search_documents",
        "description": (
            "사내 설계 가이드·시험 규격·트러블슈팅 문서를 검색합니다. "
            "질문이 모호하거나 일반적인 원리·기준을 알고 싶을 때 사용. "
            "예: 'SMER 저하 원인', 'IEC 61121 효율 기준'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "검색어 (한국어 가능, 키워드 또는 짧은 자연어)"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "query_components",
        "description": (
            "특정 모델의 컴포넌트 사양을 조회합니다 (압축기·HX·팬·EEV). "
            "모델 식별 후 부품 스펙이나 시험 결과가 필요할 때 사용."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "model_id": {
                    "type": "string",
                    "description": "모델 식별자 (예: HPWD-24-EU, HPWD-27-KR, HPWD-29-UN)"
                },
                "include_recent_test": {
                    "type": "boolean",
                    "description": "최근 시험 보고서도 함께 반환할지 (기본 false)",
                    "default": False
                }
            },
            "required": ["model_id"]
        }
    },
    {
        "name": "run_simulation",
        "description": (
            "1D 시뮬레이터로 모델 성능을 예측합니다. "
            "특정 컴포넌트를 변경했을 때 SMER·건조시간이 어떻게 변할지 예측 시 사용. "
            "현재 값 그대로 시뮬하려면 modifications를 비워서 호출."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "model_id": {
                    "type": "string",
                    "description": "모델 식별자"
                },
                "modifications": {
                    "type": "object",
                    "description": (
                        "변경할 파라미터. 키는 'condenser_ua_increase_pct' (응축기 UA 증가 %), "
                        "'compressor_rpm' (목표 RPM), 'fan_cfm_increase_pct' 중 하나 이상. "
                        "비어있으면 기본값 시뮬."
                    ),
                    "additionalProperties": True
                }
            },
            "required": ["model_id"]
        }
    },
    {
        "name": "suggest_optimization",
        "description": (
            "최적화 도구. 현재 모델 상태와 목표 SMER을 받아 가장 효과적인 설계 변경안을 제안. "
            "이미 진단이 끝나서 구체적 처방이 필요할 때 사용."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "model_id": {
                    "type": "string",
                    "description": "모델 식별자"
                },
                "target_smer": {
                    "type": "number",
                    "description": "목표 SMER (kg/kWh)"
                }
            },
            "required": ["model_id", "target_smer"]
        }
    }
]


# ============================================================
# Tool executors
# ============================================================
def execute_search_documents(query: str) -> dict:
    """RAG 검색 실행. 실제로는 임베딩+벡터 DB."""
    time.sleep(0.4)  # 시현 시 검색 느낌
    docs = search_docs(query, top_k=3)
    return {
        "query": query,
        "result_count": len(docs),
        "documents": [
            {
                "doc_id": d["doc_id"],
                "title": d["title"],
                "category": d["category"],
                "snippet": d["content"][:200] + ("..." if len(d["content"]) > 200 else "")
            }
            for d in docs
        ]
    }


def execute_query_components(model_id: str, include_recent_test: bool = False) -> dict:
    """모델 + 컴포넌트 DB 조회."""
    time.sleep(0.3)
    model = MODELS.get(model_id.upper())
    if not model:
        return {"error": f"모델 '{model_id}' 미존재. 가용 모델 — {list(MODELS.keys())}"}

    components = find_components_for(model["model_id"])
    result = {
        "model_id": model["model_id"],
        "model_name": model["model_name"],
        "category": model["category"],
        "department": model["department"],
        "spec": model["spec"],
        "components": components,
    }

    if include_recent_test:
        test = find_recent_test(model["model_id"])
        if test:
            result["recent_test"] = test

    return result


def execute_run_simulation(model_id: str, modifications: dict | None = None) -> dict:
    """1D 시뮬레이터. 실제 HPWD-Sim 흉내."""
    time.sleep(0.6)  # 시뮬 시간 흉내
    model = MODELS.get(model_id.upper())
    if not model:
        return {"error": f"모델 '{model_id}' 미존재"}

    components = find_components_for(model["model_id"])
    hx = next((c for c in components if c["type"] == "응축기/증발기"), None)
    cmp_comp = next((c for c in components if c["type"] == "압축기"), None)
    fan = next((c for c in components if c["type"] == "팬"), None)

    base_ua = hx["ua_w_per_k"] if hx else 120
    base_capacity = cmp_comp["capacity_cc"] if cmp_comp else 8
    base_cfm = fan["max_cfm"] if fan else 280
    target_smer = model["spec"]["smer_target"]

    # 실제 시뮬 파라미터 적용
    mods = modifications or {}
    ua_pct = float(mods.get("condenser_ua_increase_pct", 0))
    cfm_pct = float(mods.get("fan_cfm_increase_pct", 0))
    rpm = mods.get("compressor_rpm")

    effective_ua = base_ua * (1 + ua_pct / 100)
    effective_cfm = base_cfm * (1 + cfm_pct / 100)

    # 단순화된 SMER 모델 — UA가 핵심 변수
    # 기준: UA 124에서 SMER 0.45, UA 141에서 SMER 0.60
    smer_baseline = 0.45 + (effective_ua - 124) * 0.0088
    smer_baseline += cfm_pct * 0.0008  # 팬 영향 작음
    smer_baseline = round(max(0.30, min(0.75, smer_baseline)), 3)

    # 건조시간 = 함수율 변화량 / SMER (간이)
    drying_time = round(165 * 0.55 / smer_baseline) if smer_baseline > 0 else 999

    # 소음
    noise_baseline = 64.0 + cfm_pct * 0.05 + (ua_pct * 0.03 if ua_pct > 0 else 0)
    noise_baseline = round(noise_baseline, 1)

    return {
        "model_id": model["model_id"],
        "applied_modifications": mods,
        "results": {
            "smer_kg_per_kwh": smer_baseline,
            "smer_target": target_smer,
            "smer_pass": smer_baseline >= target_smer,
            "drying_time_min": drying_time,
            "noise_db": noise_baseline,
            "effective_condenser_ua_w_per_k": round(effective_ua, 1),
            "effective_fan_cfm": round(effective_cfm, 1),
        },
        "note": "1D HPWD-Sim 간이 시뮬 결과. 실제는 ductsim+compressor-sim+HX-Sim 통합 호출."
    }


def execute_suggest_optimization(model_id: str, target_smer: float) -> dict:
    """최적화 — 가장 비용 효과적인 변경안 제안."""
    time.sleep(0.5)
    model = MODELS.get(model_id.upper())
    if not model:
        return {"error": f"모델 '{model_id}' 미존재"}

    components = find_components_for(model["model_id"])
    hx = next((c for c in components if c["type"] == "응축기/증발기"), None)
    base_ua = hx["ua_w_per_k"] if hx else 120

    # 현재 SMER 추정 (mock simulation)
    current_smer = 0.45 + (base_ua - 124) * 0.0088
    current_smer = round(max(0.30, min(0.75, current_smer)), 3)

    if current_smer >= target_smer:
        return {
            "model_id": model["model_id"],
            "current_smer": current_smer,
            "target_smer": target_smer,
            "recommendation": "최적화 불필요 — 이미 목표 달성",
            "candidates": []
        }

    smer_gap = target_smer - current_smer
    # SMER 증가 = UA 증가 ~0.0088 per W/K → 필요 UA 증가량
    needed_ua_increase = smer_gap / 0.0088
    needed_pct = round(needed_ua_increase / base_ua * 100, 1)

    candidates = [
        {
            "rank": 1,
            "change": f"응축기 UA {needed_pct}% 증가 (= {round(base_ua + needed_ua_increase, 1)} W/K)",
            "predicted_smer": round(current_smer + needed_ua_increase * 0.0088, 3),
            "estimated_cost_increase_pct": round(needed_pct * 0.4, 1),
            "rationale": "UA 증가는 효율 향상에 가장 직접적. 핀 밀도 강화 또는 면적 확대."
        },
        {
            "rank": 2,
            "change": "팬 풍량 10% 증가 (대안)",
            "predicted_smer": round(current_smer + 0.008, 3),
            "estimated_cost_increase_pct": 1.5,
            "rationale": "효과는 작지만 비용도 작음. UA 변경과 병행 가능."
        },
        {
            "rank": 3,
            "change": "냉매 충전량 +5% (점검)",
            "predicted_smer": round(current_smer + 0.015, 3),
            "estimated_cost_increase_pct": 0,
            "rationale": "충전량이 적정 미달이면 추가. 현장에서 확인 필요."
        }
    ]

    return {
        "model_id": model["model_id"],
        "current_smer": current_smer,
        "target_smer": target_smer,
        "smer_gap": round(smer_gap, 3),
        "candidates": candidates,
        "primary_recommendation": candidates[0],
    }


# ============================================================
# Dispatcher
# ============================================================
TOOL_FUNCTIONS = {
    "search_documents": execute_search_documents,
    "query_components": execute_query_components,
    "run_simulation": execute_run_simulation,
    "suggest_optimization": execute_suggest_optimization,
}


def execute_tool(name: str, arguments: dict) -> Any:
    """도구 이름으로 실행. 인자는 dict."""
    if name not in TOOL_FUNCTIONS:
        return {"error": f"Unknown tool: {name}"}
    try:
        return TOOL_FUNCTIONS[name](**arguments)
    except TypeError as e:
        return {"error": f"Invalid arguments for {name}: {e}"}
    except Exception as e:
        return {"error": f"Tool execution failed: {type(e).__name__}: {e}"}
