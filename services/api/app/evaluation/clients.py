"""SERVAnalyst (OpenServ SERV Reasoning) and ReppoClient (eval.reppo.xyz) adapters."""

from __future__ import annotations

import datetime
import hashlib
import json
import math
import os
import re
import time
from typing import Any, Optional
import httpx

from app.domain.models import (
    AdaptationEvent,
    ReppoEvaluationRecord,
    SERVProposal,
)


def _redact_secrets(text: str) -> str:
    """Redact any accidental bearer tokens, API keys, or private credentials before external submission."""
    for key in (os.environ.get("SERV_API_KEY", ""), os.environ.get("REPPO_API_KEY", "")):
        if key:
            text = text.replace(key, "[REDACTED_KEY]")
    cleaned = re.sub(r"(Bearer\s+)[A-Za-z0-9_\-\.]+", r"\1[REDACTED]", text)
    cleaned = re.sub(r"(sk-[A-Za-z0-9_\-\.]+)", "[REDACTED_KEY]", cleaned)
    return cleaned


class SERVAnalyst:
    """OpenServ SERV Reasoning adapter for bounded, schema-validated adaptation reasoning."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        self.api_key = (api_key if api_key is not None else os.environ.get("SERV_API_KEY", "")).strip()
        self.base_url = (
            base_url or os.environ.get("SERV_BASE_URL", "https://inference-api.openserv.ai/v1")
        ).rstrip("/")
        self.model = (model if model is not None else os.environ.get("SERV_MODEL", "")).strip()

    def is_configured(self) -> bool:
        return bool(self.api_key and self.model)

    @staticmethod
    def _response_schema() -> dict[str, Any]:
        return {
            "type": "json_schema",
            "json_schema": {
                "name": "aptura_serv_proposal",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "hypothesis": {"type": "string"},
                        "evidenceIds": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "suggestedWeights": {
                            "type": "object",
                            "properties": {
                                "momentum": {"type": "number"},
                                "reversal": {"type": "number"},
                            },
                            "required": ["momentum", "reversal"],
                            "additionalProperties": False,
                        },
                        "regimeDiagnosis": {
                            "type": "string",
                            "enum": ["TRENDING", "MEAN_REVERTING", "HIGH_VOLATILITY_CHOP", "UNCERTAIN"],
                        },
                        "buyThresholdDelta": {"type": "number"},
                        "assumptions": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "uncertainties": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": [
                        "hypothesis",
                        "evidenceIds",
                        "suggestedWeights",
                        "regimeDiagnosis",
                        "buyThresholdDelta",
                        "assumptions",
                        "uncertainties",
                    ],
                    "additionalProperties": False,
                },
            },
        }

    def build_bounded_prompt(
        self,
        observed_at: str,
        dataset_name: str,
        old_weights: list[float],
        candidate_weights: list[float],
        momentum_score: float,
        reversal_score: float,
        matured_count: int,
        allowed_evidence_ids: list[str],
        extra_context: Optional[dict[str, Any]] = None,
    ) -> tuple[str, str]:
        min_w = round(max(0.15, old_weights[0] - 0.25), 2)
        max_w = round(min(0.85, old_weights[0] + 0.25), 2)
        system_prompt = (
            "You are Aptura's SERV Reasoning Analyst in a causal market-supervision lab. "
            "Analyze the observed strategy telemetry strictly up to observedAtUtc. "
            "Do NOT assume future prices, holder counts, or unmeasured liquidity. "
            "Cite ONLY IDs from allowed_evidence_ids in evidenceIds. "
            "Propose new strategy weights independently from the trailing EWMA shadow returns: "
            f"suggestedWeights.momentum must be in [{min_w}, {max_w}], suggestedWeights.reversal = 1.0 - suggestedWeights.momentum, "
            "both within [0.15, 0.85], and |momentum - currentWeights.momentum| <= 0.25. "
            "Also classify regimeDiagnosis (TRENDING | MEAN_REVERTING | HIGH_VOLATILITY_CHOP | UNCERTAIN) "
            "and buyThresholdDelta in [-0.05, 0.05] (positive = stricter entry in chop/uncertainty, negative = slightly looser in clear regime). "
            "Return strictly a JSON object with exact keys: "
            "hypothesis, evidenceIds, suggestedWeights, regimeDiagnosis, buyThresholdDelta, assumptions, uncertainties."
        )
        user_payload: dict[str, Any] = {
            "observedAtUtc": observed_at,
            "dataset": dataset_name,
            "maturedOutcomeSampleSize": matured_count,
            "trailingEwmaShadowUtilityPct": {
                "momentum": round(momentum_score, 4),
                "reversal": round(reversal_score, 4),
            },
            "currentWeights": {"momentum": round(old_weights[0], 4), "reversal": round(old_weights[1], 4)},
            "constraints": {
                "weightMin": 0.15,
                "weightMax": 0.85,
                "maxStepDelta": 0.25,
                "sumMustEqual": 1.0,
                "buyThresholdDeltaRange": [-0.05, 0.05],
            },
            "allowed_evidence_ids": allowed_evidence_ids,
        }
        if extra_context:
            user_payload["agentContext"] = extra_context
        return system_prompt, json.dumps(user_payload, sort_keys=True)

    def _post_chat(
        self,
        client: httpx.Client,
        messages: list[dict[str, str]],
        use_json_schema: bool = True,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "response_format": self._response_schema() if use_json_schema else {"type": "json_object"},
        }
        temp_raw = os.environ.get("SERV_TEMPERATURE", "").strip()
        if temp_raw:
            try:
                payload["temperature"] = float(temp_raw)
            except ValueError:
                pass
        resp = client.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        if resp.status_code == 400 and use_json_schema:
            # Fallback to generic json_object if a specific model rejects json_schema
            payload["response_format"] = {"type": "json_object"}
            resp = client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        resp.raise_for_status()
        return resp.json()

    def generate_proposal(
        self,
        observed_at: str,
        dataset_name: str,
        old_weights: list[float],
        candidate_weights: list[float],
        momentum_score: float,
        reversal_score: float,
        matured_count: int,
        allowed_evidence_ids: list[str],
        extra_context: Optional[dict[str, Any]] = None,
    ) -> SERVProposal:
        """Call OpenServ SERV Reasoning if configured; validate output schema and evidence IDs strictly."""
        system_prompt, user_content = self.build_bounded_prompt(
            observed_at=observed_at,
            dataset_name=dataset_name,
            old_weights=old_weights,
            candidate_weights=candidate_weights,
            momentum_score=momentum_score,
            reversal_score=reversal_score,
            matured_count=matured_count,
            allowed_evidence_ids=allowed_evidence_ids,
            extra_context=extra_context,
        )

        if self.is_configured():
            started = time.perf_counter()
            try:
                with httpx.Client(timeout=35.0) as client:
                    messages = [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content},
                    ]
                    body = self._post_chat(client, messages, use_json_schema=True)
                    content = body["choices"][0]["message"]["content"]
                    try:
                        proposal = self.validate_and_parse_response(
                            raw_content=content,
                            allowed_evidence_ids=allowed_evidence_ids,
                            fallback_weights=candidate_weights,
                            observed_at=observed_at,
                            model_used=body.get("model", self.model),
                            provenance="SERV_GENERATED",
                        )
                        if not proposal.schemaValid:
                            raise ValueError("Returned weights or evidence IDs out of bounds")
                    except Exception as parse_err:
                        # One bounded schema-repair attempt before ever rejecting/falling back
                        repair_messages = messages + [
                            {"role": "assistant", "content": content},
                            {
                                "role": "user",
                                "content": (
                                    f"Your JSON failed strict schema validation ({parse_err}). "
                                    "Fix it and return ONLY valid JSON with exact keys: "
                                    "hypothesis, evidenceIds (subset of allowed_evidence_ids), "
                                    "suggestedWeights ({momentum, reversal} in [0.15, 0.85] summing to 1.0), "
                                    "regimeDiagnosis, buyThresholdDelta ([-0.05, 0.05]), assumptions, uncertainties."
                                ),
                            },
                        ]
                        body = self._post_chat(client, repair_messages, use_json_schema=True)
                        content = body["choices"][0]["message"]["content"]
                        proposal = self.validate_and_parse_response(
                            raw_content=content,
                            allowed_evidence_ids=allowed_evidence_ids,
                            fallback_weights=candidate_weights,
                            observed_at=observed_at,
                            model_used=body.get("model", self.model),
                            provenance="SERV_GENERATED",
                        )

                    proposal.latencyMs = round((time.perf_counter() - started) * 1000)
                    proposal.responseId = body.get("id")
                    return proposal
            except Exception as exc:
                # External API failures must never crash the replay or fabricate live verdicts
                return self._build_deterministic_proposal(
                    observed_at=observed_at,
                    dataset_name=dataset_name,
                    old_weights=old_weights,
                    candidate_weights=candidate_weights,
                    momentum_score=momentum_score,
                    reversal_score=reversal_score,
                    matured_count=matured_count,
                    allowed_evidence_ids=allowed_evidence_ids,
                    fallback_note=f"SERV API error ({type(exc).__name__}); deterministic bounded telemetry synthesis retained.",
                )

        return self._build_deterministic_proposal(
            observed_at=observed_at,
            dataset_name=dataset_name,
            old_weights=old_weights,
            candidate_weights=candidate_weights,
            momentum_score=momentum_score,
            reversal_score=reversal_score,
            matured_count=matured_count,
            allowed_evidence_ids=allowed_evidence_ids,
            fallback_note="SERV_API_KEY not configured in environment; deterministic bounded telemetry synthesis used.",
        )

    @staticmethod
    def validate_and_parse_response(
        raw_content: str,
        allowed_evidence_ids: list[str],
        fallback_weights: list[float],
        observed_at: str,
        model_used: str,
        provenance: str = "SERV_GENERATED",
    ) -> SERVProposal:
        """Strictly validate LLM JSON output: reject unknown evidence IDs or out-of-bounds weights."""
        cleaned = raw_content.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        parsed = json.loads(cleaned)

        if not isinstance(parsed, dict):
            raise ValueError("SERV response must be an object")
        required = {"hypothesis", "evidenceIds", "suggestedWeights", "assumptions", "uncertainties"}
        optional = {"regimeDiagnosis", "buyThresholdDelta"}
        if not required.issubset(parsed.keys()) or not set(parsed.keys()).issubset(required | optional):
            raise ValueError("SERV response has missing or unexpected fields")
        if not isinstance(parsed["hypothesis"], str) or not parsed["hypothesis"].strip():
            raise ValueError("SERV hypothesis must be nonempty")
        for field in ("evidenceIds", "assumptions", "uncertainties"):
            if not isinstance(parsed[field], list) or not parsed[field] or not all(isinstance(v, str) and v.strip() for v in parsed[field]):
                raise ValueError(f"SERV {field} must contain nonempty strings")
        allowed_set = set(allowed_evidence_ids)
        returned_ev = [e for e in parsed["evidenceIds"] if e in allowed_set]
        sw = parsed["suggestedWeights"]
        if not isinstance(sw, dict) or set(sw) != {"momentum", "reversal"}:
            raise ValueError("SERV weights must specify both strategies")
        if any(type(v) not in (float, int) or not math.isfinite(v) for v in sw.values()):
            raise ValueError("SERV weights must be finite numbers")
        w_mom, w_rev = round(float(sw["momentum"]), 4), round(float(sw["reversal"]), 4)
        schema_valid = bool(returned_ev) and set(parsed["evidenceIds"]) <= allowed_set
        if not (0.15 <= w_mom <= 0.85 and 0.15 <= w_rev <= 0.85) or abs(w_mom + w_rev - 1.0) > 1e-3:
            schema_valid = False
            w_mom, w_rev = fallback_weights
        else:
            w_rev = round(1.0 - w_mom, 4)

        regime = parsed.get("regimeDiagnosis")
        if regime not in ("TRENDING", "MEAN_REVERTING", "HIGH_VOLATILITY_CHOP", "UNCERTAIN"):
            regime = None

        raw_delta = parsed.get("buyThresholdDelta", 0.0)
        if type(raw_delta) in (float, int) and math.isfinite(raw_delta):
            threshold_delta = round(max(-0.05, min(0.05, float(raw_delta))), 4)
        else:
            threshold_delta = 0.0

        return SERVProposal(
            hypothesis=str(parsed.get("hypothesis", "Observed strategy regime shift in matured shadow returns.")),
            evidenceIds=returned_ev,
            suggestedWeights={"momentum": w_mom, "reversal": w_rev},
            assumptions=[str(x) for x in parsed.get("assumptions", [])][:4]
            or ["Next-bar execution friction remains within configured slippage bounds."],
            uncertainties=[str(x) for x in parsed.get("uncertainties", [])][:4]
            or ["Historical regime shift may revert if pool volume contracts sharply."],
            schemaValid=schema_valid,
            modelUsed=model_used,
            provenance="SERV_GENERATED" if provenance == "SERV_GENERATED" else "DETERMINISTIC_FALLBACK",
            generatedAt=observed_at,
            regimeDiagnosis=regime,
            buyThresholdDelta=threshold_delta,
        )

    @staticmethod
    def _build_deterministic_proposal(
        observed_at: str,
        dataset_name: str,
        old_weights: list[float],
        candidate_weights: list[float],
        momentum_score: float,
        reversal_score: float,
        matured_count: int,
        allowed_evidence_ids: list[str],
        fallback_note: str,
    ) -> SERVProposal:
        leading = "Reversal Scout" if reversal_score > momentum_score else "Momentum Scout"
        lagging = "Momentum Scout" if reversal_score > momentum_score else "Reversal Scout"
        spread = abs(reversal_score - momentum_score)
        return SERVProposal(
            hypothesis=(
                f"Across {matured_count} matured shadow evaluations on {dataset_name} up to {observed_at}, "
                f"{leading} outperformed {lagging} by {spread:.2f}% EWMA net return per horizon "
                f"(Momentum: {momentum_score:+.2f}%, Reversal: {reversal_score:+.2f}%). "
                f"Reallocating trust from {int(old_weights[0]*100)}/{int(old_weights[1]*100)} to "
                f"{int(candidate_weights[0]*100)}/{int(candidate_weights[1]*100)} reduces exposure to the deteriorating signal."
            ),
            evidenceIds=list(allowed_evidence_ids[:5]),
            suggestedWeights={"momentum": candidate_weights[0], "reversal": candidate_weights[1]},
            assumptions=[
                "Only closed candles and matured 4-bar shadow outcomes at or before t are included.",
                "Paper fills incur next-bar open execution plus configured fee and slippage basis points.",
            ],
            uncertainties=[
                "Past-segment validation does not guarantee outperformance if the pool regime shifts again.",
                fallback_note,
            ],
            schemaValid=True,
            modelUsed="aptura-bounded-telemetry-v1",
            provenance="DETERMINISTIC_FALLBACK",
            generatedAt=observed_at,
            regimeDiagnosis="MEAN_REVERTING" if reversal_score > momentum_score else "TRENDING",
            buyThresholdDelta=0.0,
        )


class ReppoClient:
    """Asynchronous Reppo Eval Router client (`https://eval.reppo.xyz/api/v1/agents/evals`)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        settlement_minutes: Optional[int] = None,
    ) -> None:
        self.api_key = (api_key if api_key is not None else os.environ.get("REPPO_API_KEY", "")).strip()
        self.base_url = (
            base_url or os.environ.get("REPPO_BASE_URL", "https://eval.reppo.xyz")
        ).rstrip("/")
        raw_min = settlement_minutes or int(os.environ.get("REPPO_SETTLEMENT_MINUTES", "15"))
        self.settlement_minutes = max(1, min(1440, raw_min))

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def build_sanitized_submission(self, event: AdaptationEvent, dataset_name: str) -> dict[str, Any]:
        """Construct a public-safe Reppo `/api/v1/agents/evals` `action` payload with no secrets or post-t leakage."""
        hypothesis = (
            event.servProposal.hypothesis
            if event.servProposal
            else event.rationale
        )
        assumptions = event.servProposal.assumptions if event.servProposal else []
        uncertainties = event.servProposal.uncertainties if event.servProposal else []
        val_summary = (
            event.validationResult.summary
            if event.validationResult
            else "Deterministic validation pending."
        )
        telemetry = {
            "application": "Aptura Adaptive Strategy Supervisor (Paper-Trading Research Lab)",
            "adaptationEventId": event.id,
            "observedAtUtc": event.detectedAt,
            "dataset": dataset_name,
            "fromConfigVersion": event.fromVersion,
            "proposedConfigVersion": event.proposedVersion,
            "oldWeights": {"momentum": event.oldWeights[0], "reversal": event.oldWeights[1]},
            "proposedWeights": (
                {"momentum": event.proposedWeights[0], "reversal": event.proposedWeights[1]}
                if event.proposedWeights
                else None
            ),
            "maturedSampleCount": event.maturedSampleCount,
            "trailingEwmaShadowUtilityPct": {
                "momentum": event.momentumTrailingScore,
                "reversal": event.reversalTrailingScore,
            },
            "evidenceIds": event.evidenceIds,
            "proposalHypothesis": _redact_secrets(hypothesis),
            "assumptions": [_redact_secrets(a) for a in assumptions],
            "uncertainties": [_redact_secrets(u) for u in uncertainties],
            "deterministicGateSummary": _redact_secrets(val_summary),
        }
        criteria = [
            "Does the proposed weight adjustment rely strictly on matured observations at or before observedAtUtc with zero look-ahead leakage?",
            "Are the proposed strategy weights bounded within [0.15, 0.85], normalized to 1.0, and within max step delta 0.25?",
            "Does the rationale explicitly acknowledge uncertainty and separate reasoning review from numerical backtest validation?",
        ]
        context = (
            "Aptura (OpenServ Hackathon 02 - Reppo Track): Auditable strategy-supervision action for "
            f"Solana market observations ({dataset_name}). Paper-trading simulation only; no live capital."
        )
        input_text = (
            f"User / System Goal: {context}\n\n"
            "Proposed Agent Action & Causal Telemetry:\n"
            f"{json.dumps(telemetry, indent=2, sort_keys=True)}\n\n"
            "Evaluation Rubric:\n"
            + "\n".join(f"- {c}" for c in criteria)
        )
        return {
            "taskType": "action",
            "input": input_text[:48000],
            "_payload_json": json.dumps(telemetry, indent=2, sort_keys=True),
            "_criteria": criteria,
            "_context": context,
        }

    @staticmethod
    def _map_status(raw_status: str) -> str:
        upper = raw_status.upper()
        if upper in ("QUEUED", "PROCESSING", "PENDING"):
            return "PENDING"
        if upper in ("COMPLETED", "SETTLED"):
            return "SETTLED"
        if upper in ("FAILED", "DENIED"):
            return "FAILED"
        return "PENDING"

    @staticmethod
    def _apply_eval_response(record: ReppoEvaluationRecord, data: dict[str, Any]) -> ReppoEvaluationRecord:
        raw_status = str(data.get("status", record.providerStatus or "QUEUED")).upper()
        record.providerStatus = raw_status
        record.status = ReppoClient._map_status(raw_status)
        if data.get("creditsCharged") is not None:
            record.creditsCharged = int(data["creditsCharged"])
        if data.get("completedAt"):
            record.settledAt = str(data["completedAt"])
        elif record.status == "SETTLED" and not record.settledAt:
            record.settledAt = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        result = data.get("result") or {}
        score_raw = result.get("score") if result.get("score") is not None else data.get("score")
        if score_raw is not None:
            record.score = float(score_raw)

        dec = result.get("decision")
        if dec in ("accept", "revise", "reject"):
            record.decision = dec

        conf = result.get("confidence")
        if conf in ("high", "medium", "low"):
            record.confidence = conf

        route = result.get("route") or data.get("route")
        if route:
            record.route = str(route)

        rubric_scores = result.get("rubric_scores") or {}
        verdicts: list[dict[str, Any]] = []
        if isinstance(rubric_scores, dict) and rubric_scores:
            clean_scores: dict[str, float] = {}
            for k, v in rubric_scores.items():
                if isinstance(v, (int, float)) and math.isfinite(v):
                    clean_scores[str(k)] = float(v)
                    verdicts.append({"criterion": str(k), "score": float(v), "critique": ""})
            record.rubricScores = clean_scores

        explain = result.get("explain") or {}
        route_reasons = explain.get("route_reasons") if isinstance(explain, dict) else None
        if isinstance(route_reasons, list):
            for reason in route_reasons:
                verdicts.append({"criterion": "route_reason", "score": record.score, "critique": str(reason)})
        if verdicts:
            record.verdicts = verdicts

        reason_text = result.get("reason")
        if reason_text:
            record.critique = str(reason_text)
        elif record.status == "FAILED" and data.get("error"):
            record.critique = f"Evaluation failed: {data['error']}"
        elif record.status == "FAILED" and result.get("reason"):
            record.critique = f"Evaluation failed: {result['reason']}"
        return record

    def submit_evaluation(
        self,
        event: AdaptationEvent,
        dataset_name: str,
    ) -> ReppoEvaluationRecord:
        submission = self.build_sanitized_submission(event, dataset_name)
        api_body = {"taskType": submission["taskType"], "input": submission["input"]}
        req_hash = hashlib.sha256(
            json.dumps(api_body, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        now_dt = datetime.datetime.now(datetime.timezone.utc)
        now_iso = now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        est_settle_iso = (now_dt + datetime.timedelta(seconds=90)).strftime("%Y-%m-%dT%H:%M:%SZ")

        if self.is_configured():
            try:
                with httpx.Client(timeout=15.0) as client:
                    resp = client.post(
                        f"{self.base_url}/api/v1/agents/evals",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                        },
                        json=api_body,
                    )
                    if resp.status_code in (200, 201):
                        data = resp.json()
                        eval_id = data.get("id") or data.get("evalId")
                        if not isinstance(eval_id, str) or not eval_id.strip():
                            raise ValueError("Provider did not return an evaluation ID")
                        rec = ReppoEvaluationRecord(
                            evalId=eval_id,
                            adaptationEventId=event.id,
                            runId=event.runId,
                            type="action",
                            status="PENDING",
                            submittedAt=data.get("createdAt") or now_iso,
                            minSettleAt=est_settle_iso,
                            settledAt=None,
                            payload=submission["_payload_json"],
                            criteria=submission["_criteria"],
                            context=submission["_context"],
                            requestHash=req_hash,
                            provenance="REPPO_LIVE",
                            providerStatus=str(data.get("status", "QUEUED")).upper(),
                        )
                        return self._apply_eval_response(rec, data)
                    if resp.status_code == 402:
                        return ReppoEvaluationRecord(
                            evalId=f"reppo_credits_{req_hash[:10]}",
                            adaptationEventId=event.id,
                            runId=event.runId,
                            type="action",
                            status="FAILED",
                            submittedAt=now_iso,
                            minSettleAt=est_settle_iso,
                            payload=submission["_payload_json"],
                            criteria=submission["_criteria"],
                            context=submission["_context"],
                            requestHash=req_hash,
                            critique="Reppo account has insufficient credits (HTTP 402; 440 credits required per text evaluation).",
                            provenance="REPPO_LIVE",
                            providerStatus="FAILED",
                        )
                    resp.raise_for_status()
                    raise ValueError("Unexpected submission response")
            except Exception as exc:
                return ReppoEvaluationRecord(
                    evalId=f"reppo_err_{req_hash[:10]}",
                    adaptationEventId=event.id,
                    runId=event.runId,
                    type="action",
                    status="FAILED",
                    submittedAt=now_iso,
                    minSettleAt=est_settle_iso,
                    payload=submission["_payload_json"],
                    criteria=submission["_criteria"],
                    context=submission["_context"],
                    requestHash=req_hash,
                    critique=f"Reppo API request failed ({type(exc).__name__}). Replay continues using deterministic validation gates only.",
                    provenance="REPPO_LIVE",
                    providerStatus="FAILED",
                )

        # Honest unconfigured state when REPPO_API_KEY is not set
        return ReppoEvaluationRecord(
            evalId=f"reppo_pending_{req_hash[:12]}",
            adaptationEventId=event.id,
            runId=event.runId,
            type="action",
            status="UNCONFIGURED",
            submittedAt=now_iso,
            minSettleAt=est_settle_iso,
            settledAt=None,
            payload=submission["_payload_json"],
            criteria=submission["_criteria"],
            context=submission["_context"],
            requestHash=req_hash,
            critique=(
                "Evaluation not submitted (set REPPO_API_KEY on server to transmit live requests). "
                "Unconfigured evaluations never override deterministic validation."
            ),
            provenance="REPPO_UNCONFIGURED",
        )

    def poll_evaluation(self, record: ReppoEvaluationRecord) -> ReppoEvaluationRecord:
        """Poll GET /api/v1/agents/evals/{id} on eval.reppo.xyz if configured and live."""
        if not self.is_configured():
            return record
        if record.evalId.startswith(("reppo_pending_", "reppo_queued_", "reppo_err_", "reppo_credits_")):
            return record

        try:
            with httpx.Client(timeout=12.0) as client:
                resp = client.get(
                    f"{self.base_url}/api/v1/agents/evals/{record.evalId}",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                if resp.status_code != 200:
                    return record
                data = resp.json()
                return self._apply_eval_response(record, data)
        except Exception:
            pass
        return record
