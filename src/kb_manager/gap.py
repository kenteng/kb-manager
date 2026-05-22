"""
gap.py — 知识库缺口检测与询问策略

功能：
1. 扫描 kb/ 页面，识别空缺（有标题无内容、关键字段缺失、超期未更新）
2. 按价值评估打分排序
3. 输出结构化缺口报告（供 Agent 批量询问用户）
"""

import os
import json
import re
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional


# ──────────────────────────────────────────────
# 缺口类型定义
# ──────────────────────────────────────────────

GAP_EMPTY = "empty"            # 有页面但正文为空或极少
GAP_MISSING_FIELD = "missing_field"  # 缺少关键字段
GAP_STALE = "stale"            # 超过 N 天未更新
GAP_NO_PAGE = "no_page"        # 对话/上下文中提到但 kb 中无对应页面


# ──────────────────────────────────────────────
# 各类型页面的必需字段（可扩展）
# ──────────────────────────────────────────────

REQUIRED_FIELDS = {
    "clients": ["行业", "规模", "决策链", "合作历史"],
    "projects": ["目标", "周期", "团队", "技术栈"],
    "pitches": ["客户", "竞品", "方案概述", "结果"],
    "meetings": [],  # 会议纪要不强制要求特定字段
    "tech": ["架构", "技术选型", "决策依据"],
    "tools": [],
    "insights": [],
    "standards": [],
    "reviews": [],
    "patterns": [],
}

# 类型不参与缺口检测的目录
EXCLUDED_FROM_FIELD_CHECK = {"meetings", "tools", "insights", "standards", "reviews", "patterns"}

# 文件名前缀识别：这些是框架/方法论文件，不做字段检测
FRAMEWORK_PREFIXES = [
    "case-studies", "delivery-methodology", "mckinsey-methodology",
    "pricing-models", "pricing-strategy", "framework",
]

# 子目录名称识别：这些子目录下的文件是参考资料，不是实际比稿
FRAMEWORK_SUBDIRS = {"mckinsey-consulting-framework", "references", "benz-ma"}

# 文件名模式识别：学习/政策/行业概览类文件不做字段检测
LEARNING_FILE_PATTERNS = [
    "ai-policy", "ai-governance", "mcp-anniversary", "geo-optimization",
    "mcp-vs-a2a", "agent-security-compliance", "agent-security-governance",
    "multi-agent-orchestration",
]

# 不同类型页面的过期阈值（天）
STALE_DAYS = {
    "clients": 30,
    "projects": 30,
    "pitches": 30,
    "meetings": 60,
    "tech": 90,
    "tools": 90,
    "insights": 90,
    "patterns": 180,
    "standards": 180,
    "reviews": 180,
    "default": 60,
}


# ──────────────────────────────────────────────
# 价值评估权重
# ──────────────────────────────────────────────

TYPE_WEIGHT = {
    "clients": 1.5,
    "pitches": 1.3,
    "projects": 1.2,
    "meetings": 0.5,
    "tech": 0.9,
    "insights": 0.8,
    "tools": 0.3,
    "standards": 0.3,
    "reviews": 0.3,
    "patterns": 0.3,
    "default": 1.0,
}

GAP_SEVERITY = {
    GAP_EMPTY: 3,
    GAP_MISSING_FIELD: 2,
    GAP_STALE: 1,
    GAP_NO_PAGE: 2,
}


# ──────────────────────────────────────────────
# 语义映射：字段 → 可接受的关键词列表
# ──────────────────────────────────────────────

SEMANTIC_MAP = {
    "行业": ["行业", "领域", "domain", "indust", "sector", "垂直"],
    "规模": ["规模", "营收", "收入", "预算", "体量", "金额", "人天", "万", "亿", "size"],
    "决策链": ["决策链", "联系人", "对接人", "负责人", "关键人", "角色", "组织", "架构"],
    "合作历史": ["合作历史", "历史记录", "首次接触", "历史", "timeline", "时间线", "合作"],
    "目标": ["目标", "目的", "objective", "背景", "需求", "概况", "定位", "description"],
    "周期": ["周期", "时间", "阶段", "timeline", "截止日期", "deadline", "人天", "月份", "月", "周", "天", "迭代", "sprint", "duration"],
    "团队": ["团队", "人员", "成员", "参与", "负责", "角色", "客户", "client", "交付"],
    "技术栈": ["技术栈", "技术", "架构", "平台", "框架", "引擎", "系统"],
    "客户": ["客户", "甲方", "品牌", "企业", "公司", "集团"],
    "竞品": ["竞品", "竞争", "对手", "竞品分析", "comparison", "对标"],
    "方案概述": ["方案", "概述", "设计", "架构", "思路", "solution"],
    "结果": ["结果", "成效", "效果", "outcome", "复盘", "总结"],
    "架构": ["架构", "结构", "设计", "系统", "模块", "component", "组成", "框架", "层次", "分层", "体系", "层级", "模型"],
    "技术选型": ["选型", "选择", "对比", "方案", "决策", "技术栈", "工具", "platform", "技术", "框架", "引擎", "系统", "协议", "产品"],
    "决策依据": ["依据", "原因", "理由", "为什么", "考量", "考虑", "因为", "所以", "对比", "rationale", "why", "purpose", "目的", "优劣", "启示"],
}


# ──────────────────────────────────────────────
# 核心检测函数
# ──────────────────────────────────────────────

def _parse_frontmatter(content: str) -> Dict[str, Any]:
    """解析 YAML frontmatter（轻量实现，不依赖 yaml 库）"""
    fm = {}
    if not content.startswith("---"):
        return fm
    parts = content.split("---", 2)
    if len(parts) < 2:
        return fm
    raw = parts[1].strip()
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if val.startswith("[") and val.endswith("]"):
                val = [v.strip().strip('"').strip("'") for v in val[1:-1].split(",") if v.strip()]
            fm[key] = val
    return fm


def _get_body(content: str) -> str:
    """提取 frontmatter 之后的正文"""
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            return parts[2].strip()
    return content.strip()


def _has_field_semantic(body: str, field: str) -> bool:
    """语义化检查：命中任一关键词即认为存在"""
    body_lower = body.lower()
    keywords = SEMANTIC_MAP.get(field, [field])
    return any(kw in body_lower for kw in keywords)


def _check_gap_empty(filepath: Path, kb_dir: Path) -> Optional[Dict]:
    """检查页面是否为空或内容极少"""
    content = filepath.read_text(encoding="utf-8")
    body = _get_body(content)
    if len(body) < 50:  # 正文少于 50 字视为空
        fm = _parse_frontmatter(content)
        return {
            "type": GAP_EMPTY,
            "path": str(filepath.relative_to(kb_dir)),
            "title": fm.get("title", filepath.stem),
            "detail": f"正文仅 {len(body)} 字，需要补充内容",
        }
    return None


def _detect_page_type(rel: Path) -> str:
    """根据相对路径判断页面类型（支持任意层级子目录）"""
    parts = rel.parts
    if not parts:
        return "default"
    # 检查路径中是否有特殊类型目录名
    special_types = {"meetings", "tools", "insights", "standards", "reviews", "patterns"}
    for part in parts:
        if part in special_types:
            return part
    # 第一级目录是主类型
    return parts[0]


def _is_framework_file(rel: Path) -> bool:
    """判断是否为框架/方法论文件（不做字段检测）"""
    name = rel.name.lower().replace(".md", "")
    # 文件名前缀匹配
    if any(name.startswith(prefix) for prefix in FRAMEWORK_PREFIXES):
        return True
    # 子目录匹配（如 mckinsey-consulting-framework/SKILL.md）
    for part in rel.parts:
        if part in FRAMEWORK_SUBDIRS:
            return True
    return False


def _check_gap_missing_field(filepath: Path, kb_dir: Path) -> List[Dict]:
    """检查页面是否缺少关键字段（语义化检测）"""
    content = filepath.read_text(encoding="utf-8")
    body = _get_body(content)
    rel = filepath.relative_to(kb_dir)
    page_type = _detect_page_type(rel)

    # 排除类型不做字段检测
    if page_type in EXCLUDED_FROM_FIELD_CHECK:
        return []
    # 框架/方法论文件不做字段检测
    if _is_framework_file(rel):
        return []
    # 学习/政策/行业概览类文件不做字段检测
    name = rel.name.lower().replace(".md", "")
    if any(pattern in name for pattern in LEARNING_FILE_PATTERNS):
        return []

    required = REQUIRED_FIELDS.get(page_type, [])
    if not required:
        return []

    missing = []
    for field in required:
        if not _has_field_semantic(body, field):
            missing.append(field)

    if missing:
        fm = _parse_frontmatter(content)
        return [{
            "type": GAP_MISSING_FIELD,
            "path": str(filepath.relative_to(kb_dir)),
            "title": fm.get("title", filepath.stem),
            "page_type": page_type,
            "detail": f"缺少关键字段：{', '.join(missing)}",
            "missing_fields": missing,
        }]
    return []


def _check_gap_stale(filepath: Path, kb_dir: Path, stale_days: int = 30) -> Optional[Dict]:
    """检查页面是否超期未更新（按类型使用不同阈值）"""
    content = filepath.read_text(encoding="utf-8")
    fm = _parse_frontmatter(content)
    updated_str = fm.get("updated", "")
    rel = filepath.relative_to(kb_dir)
    page_type = _detect_page_type(rel)
    # 按类型使用对应阈值
    effective_days = STALE_DAYS.get(page_type, STALE_DAYS["default"])
    if stale_days != 30:  # 用户自定义阈值时优先使用
        effective_days = stale_days
    if not updated_str:
        mtime = datetime.fromtimestamp(filepath.stat().st_mtime)
        days_old = (datetime.now() - mtime).days
        updated_str = mtime.strftime("%Y-%m-%d")
    else:
        try:
            updated_date = datetime.strptime(updated_str, "%Y-%m-%d")
            days_old = (datetime.now() - updated_date).days
        except ValueError:
            return None

    if days_old > effective_days:
        return {
            "type": GAP_STALE,
            "path": str(filepath.relative_to(kb_dir)),
            "title": fm.get("title", filepath.stem),
            "page_type": page_type,
            "detail": f"已 {days_old} 天未更新（阈值 {effective_days} 天，最后更新：{updated_str}）",
            "days_old": days_old,
        }
    return None


def scan_gaps(kb_root: Path, stale_days: int = 30, context_pages: Optional[List[str]] = None) -> List[Dict]:
    """
    扫描 kb/ 目录，识别所有类型的缺口
    """
    gaps = []
    kb_dir = kb_root / "kb"

    if not kb_dir.exists():
        return gaps

    for md_file in kb_dir.rglob("*.md"):
        rel = md_file.relative_to(kb_dir)
        if rel.name.startswith("."):
            continue
        if rel.parts and rel.parts[0] == "raw":
            continue

        page_type = _detect_page_type(rel)

        gap_empty = _check_gap_empty(md_file, kb_dir)
        if gap_empty:
            gap_empty["page_type"] = page_type
            gaps.append(gap_empty)

        gap_fields = _check_gap_missing_field(md_file, kb_dir)
        for gf in gap_fields:
            gf["page_type"] = page_type
        gaps.extend(gap_fields)

        gap_stale = _check_gap_stale(md_file, kb_dir, stale_days)
        if gap_stale:
            gap_stale["page_type"] = page_type
            gaps.append(gap_stale)

    # GAP_NO_PAGE 检测
    if context_pages:
        existing_titles = set()
        for md_file in kb_dir.rglob("*.md"):
            rel = md_file.relative_to(kb_dir)
            if rel.name.startswith(".") or (rel.parts and rel.parts[0] == "raw"):
                continue
            content = md_file.read_text(encoding="utf-8")
            fm = _parse_frontmatter(content)
            existing_titles.add(fm.get("title", md_file.stem).lower())

        for page_name in context_pages:
            if page_name.lower() not in existing_titles:
                gaps.append({
                    "type": GAP_NO_PAGE,
                    "path": None,
                    "title": page_name,
                    "page_type": "unknown",
                    "detail": f"对话中提到但 kb 中无对应页面",
                })

    # 按价值评分排序
    for gap in gaps:
        tw = TYPE_WEIGHT.get(gap.get("page_type", "default"), TYPE_WEIGHT["default"])
        sv = GAP_SEVERITY.get(gap["type"], 1)
        gap["_score"] = round(tw * sv, 2)

    gaps.sort(key=lambda g: g["_score"], reverse=True)
    return gaps


def format_gap_report(gaps: List[Dict], max_per_type: int = 5) -> str:
    """将缺口列表格式化为结构化报告"""
    if not gaps:
        return "✅ 知识库无显著缺口"

    grouped = {}
    for gap in gaps:
        t = gap["type"]
        grouped.setdefault(t, []).append(gap)

    lines = ["📋 知识库缺口报告", "=" * 40]

    type_labels = {
        GAP_EMPTY: "📭 空页面（有标题无内容）",
        GAP_MISSING_FIELD: "🔍 缺少关键字段",
        GAP_STALE: "⏰ 超期未更新",
        GAP_NO_PAGE: "❓ 缺失页面",
    }

    for gap_type in [GAP_EMPTY, GAP_MISSING_FIELD, GAP_STALE, GAP_NO_PAGE]:
        items = grouped.get(gap_type, [])
        if not items:
            continue
        label = type_labels.get(gap_type, gap_type)
        lines.append(f"\n{label}（{len(items)} 项）")
        lines.append("-" * 30)

        for gap in items[:max_per_type]:
            title = gap.get("title", "未知")
            detail = gap.get("detail", "")
            path = gap.get("path", "")
            path_str = f" ({path})" if path else ""
            lines.append(f"• {title}{path_str}")
            lines.append(f"  → {detail}")

            if gap_type == GAP_MISSING_FIELD and "missing_fields" in gap:
                fields = ", ".join(gap["missing_fields"])
                lines.append(f"  💬 建议问：「{title} 的 {fields} 是什么？」")
            elif gap_type == GAP_EMPTY:
                lines.append(f"  💬 建议问：「能否补充 {title} 的详细信息？」")

    total = len(gaps)
    lines.append(f"\n合计：{total} 个缺口待修复")
    return "\n".join(lines)


def save_gaps(gaps: List[Dict], output_path: Path) -> None:
    """保存缺口列表到 JSON 文件"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "scan_time": datetime.now().isoformat(),
            "total": len(gaps),
            "gaps": gaps,
        }, f, ensure_ascii=False, indent=2)


def load_gaps(input_path: Path) -> List[Dict]:
    """加载已保存的缺口列表"""
    if not input_path.exists():
        return []
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("gaps", [])


def cmd_gap(args, kb_root: Path) -> None:
    """CLI gap 子命令入口"""
    stale_days = getattr(args, "stale_days", 30)
    output = getattr(args, "output", None)
    context_file = getattr(args, "context", None)

    context_pages = []
    if context_file and Path(context_file).exists():
        with open(context_file, "r", encoding="utf-8") as f:
            context_pages = [line.strip() for line in f if line.strip()]

    gaps = scan_gaps(kb_root, stale_days=stale_days, context_pages=context_pages)
    report = format_gap_report(gaps)
    print(report)

    if output:
        save_gaps(gaps, Path(output))
        print(f"\n💾 缺口数据已保存到 {output}")
