"""Human-reviewed frozen research-question sets for real evaluation.

The built-in questions are proposals, not a gold standard.  A frozen set is
created only from a complete review in which every proposal has an explicit
decision, every quality check is Boolean, and every included question passes
all checks.  Reviewer names and free-form notes are not copied into run
artifacts.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


QUESTION_REVIEW_SCHEMA = "cosmatter.question-set-review/v1"
FROZEN_QUESTION_SET_SCHEMA = "cosmatter.frozen-question-set/v1"
QUESTION_REVIEW_AUDIT_SCHEMA = "cosmatter.question-set-review-audit/v1"
BLANK_REVIEW_STATUS = "blank_human_question_set_review_not_frozen"
REVIEWED_STATUS = "human_reviewed_question_set_for_evaluation"
FROZEN_STATUS = "human_reviewed_frozen_question_set_not_evaluation_result"
_EVIDENCE_LEVELS = {"literature_mentioned", "data_supported", "reproducible", "already_reproduced"}
_CHECKS = {
    "answerable_by_literature",
    "material_explicit",
    "target_property_explicit",
    "scope_bounded",
    "avoids_assumed_answer",
}
_TOP_FIELDS = {"schema_version", "question_set_id", "material_family", "trust_status", "review_instructions", "questions"}
_QUESTION_FIELDS = {
    "question_id", "question", "material", "target_property", "scope",
    "intended_evidence_level", "review_decision", "review_checks", "review_note",
}
_FROZEN_FIELDS = {
    "schema_version", "mission_id", "question_set_id", "material_family", "trust_status",
    "question_count", "question_set_sha256", "source_review_sha256", "questions",
}
_FROZEN_QUESTION_FIELDS = {
    "question_id", "question", "material", "target_property", "scope", "intended_evidence_level",
}
_AUDIT_FIELDS = {
    "schema_version", "mission_id", "question_set_id", "trust_status", "reviewed_question_count",
    "included_question_count", "excluded_question_count", "included_evidence_level_counts",
    "source_review_sha256", "frozen_question_set_sha256", "freeze_gate",
}


class QuestionSetError(ValueError):
    """Raised when a question review cannot safely become a frozen set."""


_BFO_CORE_QUESTIONS: tuple[dict[str, str], ...] = (
    {
        "question_id": "bfo_transition_temperatures",
        "question": "BiFeO3 的结构相变温度、铁电居里温度和反铁磁奈尔温度分别有哪些可定位的数据报告，样品形态和测量定义如何影响可比性？",
        "material": "BiFeO3",
        "target_property": "结构、铁电与磁有序转变温度",
        "scope": "分别比较块体、陶瓷和外延薄膜；保留升降温路径、测量方法、误差和相变定义。",
        "intended_evidence_level": "data_supported",
    },
    {
        "question_id": "bfo_epitaxial_phase_boundary",
        "question": "外延 BiFeO3 薄膜中，应变、厚度与氧化学势如何共同改变已报告的相稳定性边界？",
        "material": "BiFeO3 外延薄膜",
        "target_property": "相稳定性边界与结构相",
        "scope": "比较衬底、应变、厚度、氧分压或化学势及表征条件；区分直接测量与模型推断。",
        "intended_evidence_level": "data_supported",
    },
    {
        "question_id": "bfo_domain_coupling",
        "question": "BiFeO3 薄膜中畴结构与铁电—反铁磁耦合的报告，在什么样品和测量条件下可以相互比较？",
        "material": "BiFeO3 薄膜",
        "target_property": "畴结构、铁电与磁有序耦合",
        "scope": "记录取向、应变、缺陷、厚度、温度、场史和表征方法；不把相关性自动解释为因果。",
        "intended_evidence_level": "data_supported",
    },
    {
        "question_id": "bfo_leakage_protocols",
        "question": "不同制备和电学测量协议对 BiFeO3 薄膜缺陷相关漏电报告造成了哪些可定位、可复核的差异？",
        "material": "BiFeO3 薄膜",
        "target_property": "缺陷相关漏电与电学响应",
        "scope": "比较沉积或退火、氧环境、电极、厚度、温度、偏压和测试协议，并保留未报告条件。",
        "intended_evidence_level": "data_supported",
    },
    {
        "question_id": "bfo_band_gap_methods",
        "question": "BiFeO3 的带隙数值在不同实验测量和第一性原理计算中为何不可直接混用，哪些方法与条件可形成同边界比较？",
        "material": "BiFeO3",
        "target_property": "带隙",
        "scope": "分开光学测量与计算结果，记录样品形态、温度、拟合定义、泛函或修正方法及不确定度。",
        "intended_evidence_level": "data_supported",
    },
    {
        "question_id": "bfo_synthesis_reproducibility",
        "question": "哪些公开的 BiFeO3 单相样品制备路线报告了足以由独立研究者执行并判定成败的工艺参数和物相纯度标准？",
        "material": "BiFeO3",
        "target_property": "单相制备路线的可复现性",
        "scope": "核对前驱体、化学计量、气氛、温度时间史、相纯度判据、失败条件和独立重复边界。",
        "intended_evidence_level": "reproducible",
    },
    {
        "question_id": "bfo_counterevidence_boundary",
        "question": "针对 BiFeO3 相稳定性与功能响应的常见解释，独立文献中有哪些条件明确的反例或不一致结果？",
        "material": "BiFeO3",
        "target_property": "相稳定性与功能响应的反例边界",
        "scope": "只记录已执行检索边界内的反例；不得由未命中推断全局不存在反证。",
        "intended_evidence_level": "literature_mentioned",
    },
    {
        "question_id": "bfo_independent_reproduction",
        "question": "BiFeO3 文献中的哪些限定结果已有材料、条件和判据相匹配的独立复现记录，哪些仍只有单一路线报告？",
        "material": "BiFeO3",
        "target_property": "独立复现状态",
        "scope": "要求不同研究执行记录、相同受限主张、条件对齐、偏差说明和人工核查；综述转述不算独立复现。",
        "intended_evidence_level": "already_reproduced",
    },
)


def bfo_question_set_review_template(question_set_id: str = "bfo-core-v1") -> dict[str, Any]:
    """Return an editable proposal pack with no human decisions pre-filled."""
    if not isinstance(question_set_id, str) or not question_set_id.strip() or len(question_set_id) > 120:
        raise QuestionSetError("question_set_id is invalid")
    return {
        "schema_version": QUESTION_REVIEW_SCHEMA,
        "question_set_id": question_set_id.strip(),
        "material_family": "BiFeO3",
        "trust_status": BLANK_REVIEW_STATUS,
        "review_instructions": {
            "decision": "Set every review_decision to include or exclude after checking the question text and intended evidence level.",
            "checks": "Set all five review_checks to true or false. Included questions require all five checks to be true.",
            "note": "Record a short reason for every decision; do not paste paper text, credentials, URLs, or local paths.",
        },
        "questions": [
            {
                **item,
                "review_decision": "unreviewed",
                "review_checks": {name: None for name in sorted(_CHECKS)},
                "review_note": "",
            }
            for item in _BFO_CORE_QUESTIONS
        ],
    }


def freeze_reviewed_question_set(*, mission_id: str, mission_material: str, review: object) -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate a complete human review and return frozen and aggregate artifacts."""
    questions = _validate_review(review, reviewed=True)
    assert isinstance(review, dict)
    if _identity_text(review["material_family"]) not in _identity_text(mission_material) and _identity_text(mission_material) not in _identity_text(review["material_family"]):
        raise QuestionSetError("question-set material family does not match the mission material")
    included = [item for item in questions if item["review_decision"] == "include"]
    if len(included) < 3:
        raise QuestionSetError("a frozen question set requires at least three included questions")
    frozen_questions = [
        {key: item[key] for key in ("question_id", "question", "material", "target_property", "scope", "intended_evidence_level")}
        for item in included
    ]
    question_hash = _sha256(frozen_questions)
    review_hash = _sha256(review)
    frozen = {
        "schema_version": FROZEN_QUESTION_SET_SCHEMA,
        "mission_id": mission_id,
        "question_set_id": review["question_set_id"],
        "material_family": review["material_family"],
        "trust_status": FROZEN_STATUS,
        "question_count": len(frozen_questions),
        "question_set_sha256": question_hash,
        "source_review_sha256": review_hash,
        "questions": frozen_questions,
    }
    level_counts = {level: 0 for level in sorted(_EVIDENCE_LEVELS)}
    for item in frozen_questions:
        level_counts[item["intended_evidence_level"]] += 1
    audit = {
        "schema_version": QUESTION_REVIEW_AUDIT_SCHEMA,
        "mission_id": mission_id,
        "question_set_id": review["question_set_id"],
        "trust_status": "aggregate_human_question_set_review_audit_not_evaluation_result",
        "reviewed_question_count": len(questions),
        "included_question_count": len(included),
        "excluded_question_count": len(questions) - len(included),
        "included_evidence_level_counts": level_counts,
        "source_review_sha256": review_hash,
        "frozen_question_set_sha256": question_hash,
        "freeze_gate": "ready_for_question_level_evaluation_not_metrics",
    }
    return frozen, audit


def write_question_set_review_template(path: Path, payload: dict[str, Any]) -> Path:
    _validate_review(payload, reviewed=False)
    if path.suffix.lower() != ".json":
        raise QuestionSetError("question-set review template output must be a JSON file")
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_new_json(path, payload)
    return path


def write_frozen_question_set(run_dir: Path, frozen: dict[str, Any], audit: dict[str, Any]) -> tuple[Path, Path]:
    _validate_frozen_pair(frozen, audit)
    run_dir.mkdir(parents=True, exist_ok=True)
    frozen_path = run_dir / "frozen_question_set.json"
    audit_path = run_dir / "question_set_review_audit.json"
    if frozen_path.exists() or audit_path.exists():
        raise QuestionSetError("frozen question-set artifacts already exist and cannot be overwritten")
    _write_new_json(frozen_path, frozen)
    try:
        _write_new_json(audit_path, audit)
    except OSError:
        frozen_path.unlink(missing_ok=True)
        raise
    return frozen_path, audit_path


def load_question_set_readiness_summary(run_dir: Path, *, mission_id: str) -> dict[str, Any] | None:
    """Return a browser-safe aggregate only after validating the frozen pair.

    The question text, reviewer notes, identifiers, and hashes deliberately do
    not cross this projection boundary. A missing pair means not yet frozen;
    a partial or inconsistent pair is an error rather than an empty result.
    """
    pair = _load_frozen_question_set_pair(run_dir, mission_id=mission_id)
    if pair is None:
        return None
    _, audit = pair
    return {
        "reviewed_question_count": audit["reviewed_question_count"],
        "included_question_count": audit["included_question_count"],
        "excluded_question_count": audit["excluded_question_count"],
        "included_evidence_level_counts": dict(audit["included_evidence_level_counts"]),
        "freeze_gate": audit["freeze_gate"],
    }


def load_frozen_question_set_binding(run_dir: Path, *, mission_id: str) -> dict[str, Any] | None:
    """Return the validated identity needed to bind an evaluation run."""
    pair = _load_frozen_question_set_pair(run_dir, mission_id=mission_id)
    if pair is None:
        return None
    frozen, _ = pair
    return {
        "question_set_id": frozen["question_set_id"],
        "frozen_question_count": frozen["question_count"],
        "frozen_question_set_sha256": frozen["question_set_sha256"],
    }


def _load_frozen_question_set_pair(run_dir: Path, *, mission_id: str) -> tuple[dict[str, Any], dict[str, Any]] | None:
    frozen_path = run_dir / "frozen_question_set.json"
    audit_path = run_dir / "question_set_review_audit.json"
    if not frozen_path.exists() and not audit_path.exists():
        return None
    if not frozen_path.exists() or not audit_path.exists():
        raise QuestionSetError("frozen question set and review audit must both exist")
    try:
        frozen = json.loads(frozen_path.read_text(encoding="utf-8"))
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise QuestionSetError("frozen question-set artifacts are unreadable") from exc
    _validate_frozen_pair(frozen, audit)
    if frozen["mission_id"] != mission_id:
        raise QuestionSetError("frozen question set does not belong to this mission")
    return frozen, audit


def _validate_review(payload: object, *, reviewed: bool) -> list[dict[str, Any]]:
    if not isinstance(payload, dict) or set(payload) != _TOP_FIELDS:
        raise QuestionSetError("question-set review has unsupported or missing fields")
    expected_status = REVIEWED_STATUS if reviewed else BLANK_REVIEW_STATUS
    if payload.get("schema_version") != QUESTION_REVIEW_SCHEMA or payload.get("trust_status") != expected_status:
        raise QuestionSetError("question-set review schema or trust status is invalid")
    if not all(isinstance(payload.get(field), str) and payload[field].strip() for field in ("question_set_id", "material_family")):
        raise QuestionSetError("question-set identity is invalid")
    if not isinstance(payload.get("review_instructions"), dict) or set(payload["review_instructions"]) != {"decision", "checks", "note"}:
        raise QuestionSetError("question-set review instructions are invalid")
    raw_questions = payload.get("questions")
    if not isinstance(raw_questions, list) or not 3 <= len(raw_questions) <= 50:
        raise QuestionSetError("question-set review must contain between 3 and 50 questions")
    ids: set[str] = set()
    normalized_questions: set[str] = set()
    result: list[dict[str, Any]] = []
    for item in raw_questions:
        if not isinstance(item, dict) or set(item) != _QUESTION_FIELDS:
            raise QuestionSetError("question-set item fields are invalid")
        for field, limit in (("question_id", 120), ("question", 1000), ("material", 300), ("target_property", 300), ("scope", 1000)):
            value = item.get(field)
            if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
                raise QuestionSetError(f"question-set {field} is invalid")
        question_id = item["question_id"].strip()
        normalized = _identity_text(item["question"])
        if question_id in ids or normalized in normalized_questions:
            raise QuestionSetError("question-set IDs and question texts must be unique")
        if item.get("intended_evidence_level") not in _EVIDENCE_LEVELS:
            raise QuestionSetError("question-set evidence level is invalid")
        checks = item.get("review_checks")
        if not isinstance(checks, dict) or set(checks) != _CHECKS:
            raise QuestionSetError("question-set review checks are invalid")
        decision, note = item.get("review_decision"), item.get("review_note")
        if reviewed:
            if decision not in {"include", "exclude"} or not all(isinstance(value, bool) for value in checks.values()):
                raise QuestionSetError("every question requires a complete human decision and Boolean checks")
            if not isinstance(note, str) or not note.strip() or len(note.strip()) > 500:
                raise QuestionSetError("every reviewed question requires a bounded review note")
            if decision == "include" and not all(checks.values()):
                raise QuestionSetError("included questions must pass every quality check")
        elif decision != "unreviewed" or any(value is not None for value in checks.values()) or note != "":
            raise QuestionSetError("blank question-set templates cannot contain review decisions")
        ids.add(question_id)
        normalized_questions.add(normalized)
        result.append(item)
    return result


def _validate_frozen_pair(frozen: object, audit: object) -> None:
    if not isinstance(frozen, dict) or set(frozen) != _FROZEN_FIELDS or frozen.get("schema_version") != FROZEN_QUESTION_SET_SCHEMA or frozen.get("trust_status") != FROZEN_STATUS:
        raise QuestionSetError("frozen question set is invalid")
    if not isinstance(audit, dict) or set(audit) != _AUDIT_FIELDS or audit.get("schema_version") != QUESTION_REVIEW_AUDIT_SCHEMA or audit.get("trust_status") != "aggregate_human_question_set_review_audit_not_evaluation_result":
        raise QuestionSetError("question-set review audit is invalid")
    if not all(isinstance(frozen.get(field), str) and frozen[field].strip() for field in ("mission_id", "question_set_id", "material_family", "question_set_sha256", "source_review_sha256")):
        raise QuestionSetError("frozen question-set identity is invalid")
    if not _is_sha256(frozen["question_set_sha256"]) or not _is_sha256(frozen["source_review_sha256"]):
        raise QuestionSetError("frozen question-set hashes are invalid")
    if frozen.get("mission_id") != audit.get("mission_id") or frozen.get("question_set_id") != audit.get("question_set_id"):
        raise QuestionSetError("frozen question set and audit identities do not match")
    questions = frozen.get("questions")
    if not isinstance(questions, list) or not 3 <= len(questions) <= 50 or frozen.get("question_count") != len(questions) or frozen.get("question_set_sha256") != _sha256(questions):
        raise QuestionSetError("frozen question-set content hash is invalid")
    if any(not isinstance(item, dict) or set(item) != _FROZEN_QUESTION_FIELDS for item in questions):
        raise QuestionSetError("frozen question-set item fields are invalid")
    if any(
        not all(isinstance(item.get(field), str) and item[field].strip() for field in _FROZEN_QUESTION_FIELDS)
        or item.get("intended_evidence_level") not in _EVIDENCE_LEVELS
        for item in questions
    ):
        raise QuestionSetError("frozen question-set item values are invalid")
    if len({item["question_id"] for item in questions}) != len(questions) or len({_identity_text(item["question"]) for item in questions}) != len(questions):
        raise QuestionSetError("frozen question-set IDs and question texts must be unique")
    if audit.get("frozen_question_set_sha256") != frozen.get("question_set_sha256") or audit.get("source_review_sha256") != frozen.get("source_review_sha256"):
        raise QuestionSetError("question-set review audit hashes do not match")
    reviewed = audit.get("reviewed_question_count")
    included = audit.get("included_question_count")
    excluded = audit.get("excluded_question_count")
    if not all(isinstance(value, int) and not isinstance(value, bool) and value >= 0 for value in (reviewed, included, excluded)) or included != len(questions) or reviewed != included + excluded:
        raise QuestionSetError("question-set review audit counts are invalid")
    level_counts = audit.get("included_evidence_level_counts")
    if not isinstance(level_counts, dict) or set(level_counts) != _EVIDENCE_LEVELS or any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in level_counts.values()) or sum(level_counts.values()) != included:
        raise QuestionSetError("question-set review audit evidence-level counts are invalid")
    if audit.get("freeze_gate") != "ready_for_question_level_evaluation_not_metrics":
        raise QuestionSetError("question-set review audit gate is invalid")


def _identity_text(value: str) -> str:
    return "".join(character.casefold() for character in value if character.isalnum())


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 71 and value.startswith("sha256:") and all(
        character in "0123456789abcdef" for character in value[7:]
    )


def _sha256(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _write_new_json(path: Path, payload: object) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
