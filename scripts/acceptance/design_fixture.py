"""Explicitly synthetic numeric/export fixtures, not autonomous research acceptance."""

from eiqas_research.models import Plan
from eiqas_research.planning import DataAssessment, PlanningService
from eiqas_research.service import digest


def approve_synthetic_plan(evidence, rid, saved, dataset):
    """Simulate a final human approval only for a labelled, disposable test study."""
    content = saved["content"]
    content.update(
        decision_use="明确标注的合成数值与导出回归；不代表真实业务研究或人工试读",
        scope="仅使用自制合成输入，验证指定计算和离线材料",
        research_questions=[{"id": "test-question", "text": content["question"]}],
        question_decisions=[
            {
                "question_id": "test-question",
                "status": "answer",
                "explanation": "合成输入可支持指定数值回归；不声称真实商业结论",
            }
        ],
        data_constraints=["仅有明确标注的合成数据"],
    )
    for index, method in enumerate(content["methods"]):
        method.update(
            id=f"test-method-{index}",
            selected=True,
            role="primary",
            question_ids=["test-question"],
            basis="指定算术方法的独立复算回归",
            calculation=f"按 {method['operation']} 的已实现定义计算，并独立复算",
            applicability="仅用于本合成样例；真实业务需重新判断数据条件",
            expected_outputs=content["outputs"],
        )
    content["data_requirements"] = [
        {
            "id": "test-data",
            "title": "自制合成输入",
            "method_ids": [m["id"] for m in content["methods"]],
            "kind": "quantitative",
            "required": True,
            "category": "public",
            "fields": ["主体", "期间", "指标", "原值", "单位"],
            "metrics": sorted({o["metric"] for o in dataset["observations"]}),
            "grain": "以合成输入的主体与期间为观察单位",
            "period": "以合成样例的明确期间为限",
            "units": "输入原单位",
            "channels": ["自制可再分发合成样例"],
            "impact_if_missing": "不能执行数值回归",
            "fallback": "测试失败，不生成业务结论",
        }
    ]
    saved = evidence.research.save_plan(rid, Plan.model_validate(content))
    refs = []
    for source_id in dict.fromkeys(o["source_id"] for o in dataset["observations"]):
        obs = next(o for o in dataset["observations"] if o["source_id"] == source_id)
        refs.append(
            {
                "source_id": source_id,
                "extraction_id": obs["extraction_id"],
                "locator_key": obs["locator_key"],
                "quote": obs["raw_text"],
                "explanation": "合成输入定位，非企业原始数据",
            }
        )
    PlanningService(evidence).assess(
        rid,
        DataAssessment(
            requirement_id="test-data",
            requirement_hash=digest(saved["content"]["data_requirements"][0]),
            status="available",
            reason="实际保存合成原件、定位数据与冻结输入",
            next_action="运行独立计算检查",
            evidence=refs,
            dataset_ids=[dataset["id"]],
        ),
    )
    return evidence.research.confirm_plan(rid, saved["hash"])
