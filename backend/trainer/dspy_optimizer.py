"""
DSPy 训练优化器 — ProcureAI Agent 训练模块
============================================

支持两种训练模式：

模式1: 前置训练（Agent 上线前）
  从采购人员收集"需求→理想推荐→原因"样例数据，优化 Agent 的评分逻辑。
  
模式2: 后置训练（Agent 上线后）
  从用户反馈（Memory 模块的 FeedbackRecord）提取信号，持续校准评分标准。

原理：
  不是改模型参数（我们用 API，不能 fine-tune），而是优化 prompt 和评分权重。
  DSPy 自动尝试不同的 prompt 写法，找到让匹配率最高的那一段。
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ═══════════════════════════════════════════════════════════════
# 训练样例格式
# ═══════════════════════════════════════════════════════════════

"""
前置训练样例（采购人员提供）：
[
  {
    "query": "找德国的挡水条供应商，IATF认证必须",
    "expected_supplier": "Cooper Standard France SAS",
    "expected_score": 90,
    "reason": "挡水条专业、有IATF、交期稳定、本地响应快"
  }
]

后置训练样例（从 FeedbackRecord 转换）：
[
  {
    "query": "找德国的玻璃胶供应商",
    "chosen_supplier": "Henkel AG & Co. KGaA",
    "quality": 5,       // 0-5 星
    "logistics": 4,
    "price_sat": 3,
    "service": 5,
    "comment": "质量好但贵"
  }
]
"""


class DSPyTrainer:
    """
    DSPy 训练器。

    前置训练：优化 Agent 的评分 prompt，让 matchScore 更接近人工判断。
    后置训练：从真实使用反馈中提取信号，持续校准。

    当前是占位实现（placeholder），等 DSPy 库安装后启用实际优化。
    """

    def __init__(self) -> None:
        self.pre_examples: list[dict[str, Any]] = []
        self.post_examples: list[dict[str, Any]] = []
        self.optimized_prompt: str | None = None

    # ── 前置训练 ─────────────────────────────────────────────────

    def load_examples(self, path: str | Path) -> int:
        """
        加载前置训练样例。

        参数:
            path: JSON 文件路径，格式为 [{query, expected_supplier, expected_score, reason}]

        返回:
            加载的样例数量
        """
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            raise ValueError("前置训练数据必须是一个数组")

        count = 0
        for item in data:
            required = ["query", "expected_supplier"]
            if all(k in item for k in required):
                self.pre_examples.append(item)
                count += 1

        print(f"[前置训练] 加载了 {count} 条训练样例（共 {len(data)} 条输入）")
        return count

    # ── 后置训练 ─────────────────────────────────────────────────

    def load_feedback(self, conversations: list[dict[str, Any]]) -> int:
        """
        从 Conversation 记录中提取反馈数据，转换为训练样例。

        参数:
            conversations: API 返回的 ConversationRecord 列表
                           每个记录可能包含 feedback 字段

        返回:
            提取的有效反馈数

        原理：
            用户搜索后选择了某个供应商并打了分，说明这个供应商是"正确答案"。
            后续训练时，Agent 会给这个供应商更高的 matchScore。
        """
        count = 0
        for conv in conversations:
            feedback = conv.get("feedback")
            query = conv.get("query", "")
            candidates = conv.get("candidateNames", [])

            if not feedback or not query:
                continue

            # 提取反馈信号
            chosen = feedback.get("chosenName", "")
            quality = feedback.get("quality", 0)
            logistics = feedback.get("logistics", 0)
            price_sat = feedback.get("priceSatisfaction", 0)
            service = feedback.get("service", 0)

            # 综合评分转成预期分数
            avg_rating = (quality + logistics + price_sat + service) / 4
            expected_score = int(avg_rating * 20)  # 0-5 → 0-100

            example = {
                "query": query,
                "chosen_supplier": chosen,
                "expected_score": expected_score,
                "quality": quality,
                "logistics": logistics,
                "price_sat": price_sat,
                "service": service,
                "candidates": candidates,
                "feedback_comment": feedback.get("comment", ""),
                "converted_at": datetime.now(timezone.utc).isoformat(),
            }
            self.post_examples.append(example)
            count += 1

        print(f"[后置训练] 从 {len(conversations)} 条对话中提取了 {count} 条有效反馈")
        return count

    # ── 训练执行 ─────────────────────────────────────────────────

    def optimize(self, mode: str = "pre") -> dict[str, Any]:
        """
        执行 DSPy 优化。

        参数:
            mode: "pre"（前置训练）或 "post"（后置训练）或 "both"

        返回:
            训练结果摘要

        当前为占位实现。实际 DSPy 优化步骤：
        1. 定义评分 metric（匹配率）
        2. 用 BootstrapFewShot 自动生成候选 prompt
        3. 在训练集上评估，选最优
        4. 保存最优 prompt 供 Agent 使用
        """
        examples = []
        if mode in ("pre", "both"):
            examples.extend(self.pre_examples)
        if mode in ("post", "both"):
            examples.extend(self.post_examples)

        if not examples:
            return {"status": "no_data", "message": "没有训练数据，请先加载样例"}

        # Placeholder: 实际 DSPy 优化逻辑
        self.optimized_prompt = self._generate_placeholder_prompt(examples, mode)

        result = {
            "status": "placeholder",
            "mode": mode,
            "total_examples": len(examples),
            "pre_examples": len(self.pre_examples),
            "post_examples": len(self.post_examples),
            "message": (
                "DSPy 实际优化尚未启用（占位模式）。"
                "当前基于训练数据生成了默认优化 prompt。"
                "安装 dspy-ai 后替换此方法即可。"
            ),
            "optimized_prompt_preview": self.optimized_prompt[:200] + "...",
        }

        print(f"\n[DSPy 训练] 模式={mode}, 样例数={len(examples)}")
        print(f"[DSPy 训练] 前置样例={len(self.pre_examples)}, 后置样例={len(self.post_examples)}")
        print(f"[DSPy 训练] {result['message']}")

        return result

    def _generate_placeholder_prompt(self, examples: list[dict], mode: str) -> str:
        """生成默认优化 prompt（占位，实际由 DSPy 生成）"""
        supplier_names = list({
            e.get("expected_supplier") or e.get("chosen_supplier", "")
            for e in examples
            if e.get("expected_supplier") or e.get("chosen_supplier")
        })

        return (
            "你是一个采购助手 Agent。根据用户需求，从候选供应商中选择最匹配的。\n"
            "评分时考虑以下维度（按优先级）：\n"
            "1. 品类匹配 — 供应商是否专注于该品类\n"
            "2. 认证要求 — 是否有用户要求的认证（IATF 16949 等）\n"
            "3. 地区偏好 — 是否在用户指定的国家\n"
            "4. 价格竞争力 — 价格是否在预算内\n"
            "5. 交期 — 是否满足交期要求\n"
            f"\n已知优秀供应商参考：{', '.join(supplier_names[:10])}"
        )

    def get_optimized_prompt(self) -> str | None:
        """返回当前最优 prompt"""
        return self.optimized_prompt

    def export_prompt(self, path: str | Path) -> None:
        """导出最优 prompt 到文件"""
        if not self.optimized_prompt:
            print("尚未优化，没有 prompt 可导出")
            return
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.optimized_prompt)
        print(f"优化 prompt 已导出到 {path}")


# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(
        description="ProcureAI DSPy 训练器 — 前置/后置训练"
    )
    parser.add_argument(
        "--mode",
        choices=["pre", "post", "both"],
        required=True,
        help="训练模式: pre=前置训练, post=后置训练, both=两种都跑",
    )
    parser.add_argument(
        "--input",
        type=Path,
        help="训练数据 JSON 文件路径",
    )
    parser.add_argument(
        "--feedback",
        type=Path,
        help="Conversation 反馈 JSON 文件路径（后置训练用）",
    )
    parser.add_argument(
        "--export",
        type=Path,
        default=Path("optimized_prompt.txt"),
        help="导出优化后的 prompt 到文件",
    )

    args = parser.parse_args()
    trainer = DSPyTrainer()

    if args.mode in ("pre", "both") and args.input:
        trainer.load_examples(args.input)

    if args.mode in ("post", "both") and args.feedback:
        with open(args.feedback, "r", encoding="utf-8") as f:
            feedback_data = json.load(f)
        if isinstance(feedback_data, dict):
            feedback_data = [feedback_data]
        trainer.load_feedback(feedback_data)

    result = trainer.optimize(mode=args.mode)

    if result["status"] != "no_data":
        trainer.export_prompt(args.export)

    print(f"\n训练完成。结果: {json.dumps(result, ensure_ascii=False, indent=2)}")


if __name__ == "__main__":
    main()
