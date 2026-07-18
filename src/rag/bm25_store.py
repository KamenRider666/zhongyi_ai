"""BM25 稀疏检索 — 基于内存索引，使用 jieba 中文分词

与 Qdrant 稠密向量检索互补：
  - 稠密检索擅长语义匹配（"手脚冰凉" → 阳虚）
  - BM25 擅长精确术语匹配（"麻黄汤" → 精确命中）

索引在启动时从 Qdrant 全量 payload 加载构建，运行时驻留内存。
"""

import logging
import re
from typing import Dict, List, Optional

import jieba
from rank_bm25 import BM25Okapi

from src.rag.qdrant_store import QdrantStore

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# 中医自定义分词词典
# jieba 默认会将"小柴胡汤"切成"小/柴胡/汤"，影响 BM25 精确匹配
# ──────────────────────────────────────────────

_TCM_CUSTOM_WORDS = [
    # 经典方剂
    "麻黄汤", "桂枝汤", "小柴胡汤", "大柴胡汤", "四君子汤", "四物汤",
    "六味地黄丸", "逍遥散", "银翘散", "藿香正气散", "温胆汤", "补中益气汤",
    "玉屏风散", "归脾汤", "龙胆泻肝汤", "血府逐瘀汤", "半夏泻心汤",
    "白虎汤", "承气汤", "理中丸", "真武汤", "五苓散", "越鞠丸",
    "保和丸", "平胃散", "二陈汤", "酸枣仁汤", "天王补心丹", "生化汤",
    # 常见药材（多字）
    "金银花", "连翘", "薄荷", "牛蒡子", "淡豆豉", "荆芥穗", "淡竹叶",
    "党参", "白术", "茯苓", "甘草", "熟地黄", "当归", "白芍", "川芎",
    "柴胡", "黄芩", "半夏", "生姜", "大枣", "陈皮", "枳实", "竹茹",
    "附子", "干姜", "人参", "黄芪", "升麻", "防风", "苍术", "厚朴",
    "黄连", "黄柏", "栀子", "牡丹皮", "泽泻", "车前子", "木通",
    "桃仁", "红花", "赤芍", "牛膝", "桔梗", "柴胡", "枳壳",
    "麦冬", "五味子", "酸枣仁", "柏子仁", "远志", "丹参",
    # 常见穴位
    "足三里", "三阴交", "合谷", "百会", "风池", "关元", "内关",
    "太冲", "太溪", "命门", "肾俞", "脾俞", "胃俞", "肝俞",
    "肺俞", "心俞", "膈俞", "气海", "中脘", "神阙", "涌泉",
    # 中医术语
    "活血化瘀", "清热解毒", "疏肝理气", "健脾益气", "温阳散寒",
    "滋阴降火", "化痰止咳", "祛风除湿", "补气养血", "调和营卫",
    "辨证论治", "八纲辨证", "脏腑辨证", "六经辨证", "卫气营血辨证",
    "君臣佐使", "辛温解表", "辛凉解表", "攻下逐水", "润肠通便",
]


def _init_jieba():
    """初始化 jieba 分词器，加载中医自定义词典"""
    for word in _TCM_CUSTOM_WORDS:
        jieba.add_word(word)
    logger.info(f"jieba 已加载 {len(_TCM_CUSTOM_WORDS)} 个中医自定义词")


# 从文档内容中提取中医实体名，补充到分词词典
_NAME_PATTERNS = [
    re.compile(r"【药名】(.+?)$"),
    re.compile(r"【方名】(.+?)$"),
    re.compile(r"【名称】(.+?)$"),
    re.compile(r"【症状】(.+?)$"),
    re.compile(r"【治法】(.+?)$"),
]


class BM25Store:
    """BM25 内存索引

    用法:
        store = BM25Store()
        store.build_from_qdrant(qdrant_store)  # 从 Qdrant 加载全量文档
        results = store.search("麻黄汤", top_k=20)

    索引大小: 约 5000 条文档 × 200 字 ≈ 5-10MB 内存
    检索延迟: 约 3-5ms
    """

    def __init__(self):
        _init_jieba()
        self.bm25: Optional[BM25Okapi] = None
        self.docs: List[Dict] = []

    @property
    def is_ready(self) -> bool:
        """索引是否已构建"""
        return self.bm25 is not None and len(self.docs) > 0

    @property
    def doc_count(self) -> int:
        return len(self.docs)

    def build_from_qdrant(self, qdrant_store: QdrantStore) -> int:
        """从 Qdrant 滚动加载全部文档 payload，构建 BM25 索引

        Args:
            qdrant_store: 已连接的 QdrantStore 实例

        Returns:
            索引文档数量
        """
        logger.info("开始从 Qdrant 加载文档构建 BM25 索引...")

        all_docs = qdrant_store.scroll_all()
        self.docs = all_docs

        if not all_docs:
            logger.warning("Qdrant 中无文档，BM25 索引为空")
            self.bm25 = None
            return 0

        # 从文档内容中提取中医实体名，补充到 jieba 词典
        extra_words = set()
        for doc in all_docs:
            content = doc.get("content", "")
            if not isinstance(content, str):
                continue
            for line in content.split("\n"):
                line = line.strip()
                for pattern in _NAME_PATTERNS:
                    m = pattern.match(line)
                    if m:
                        name = m.group(1).strip()
                        if 2 <= len(name) <= 20:
                            extra_words.add(name)
        for word in extra_words:
            jieba.add_word(word)
        if extra_words:
            logger.info(f"从文档中提取并加载 {len(extra_words)} 个额外中医实体名到分词词典")

        # 分词构建 BM25 索引
        tokenized = [self._tokenize(doc.get("content", "")) for doc in all_docs]
        self.bm25 = BM25Okapi(tokenized)

        logger.info(f"BM25 索引构建完成: {len(all_docs)} 篇文档")
        return len(all_docs)

    def search(
        self,
        query: str,
        top_k: int = 20,
        category: Optional[str] = None,
    ) -> List[Dict]:
        """BM25 关键词检索

        Args:
            query:   查询文本
            top_k:   返回结果数
            category: 按分类过滤（fangji/herb/acupoint/classic 等）

        Returns:
            排序后的文档列表，包含 content/source/category/score 字段
        """
        if not self.is_ready:
            return []

        tokens = self._tokenize(query)
        if not tokens:
            return []

        scores = self.bm25.get_scores(tokens)

        # 取所有非零分文档，按分数降序
        indexed = [(i, float(scores[i])) for i in range(len(scores)) if scores[i] > 0]
        indexed.sort(key=lambda x: -x[1])

        # 分类过滤
        results: List[Dict] = []
        for idx, score in indexed:
            doc = self.docs[idx]
            if category and doc.get("category") != category:
                continue
            doc_copy = doc.copy()
            doc_copy["score"] = score
            results.append(doc_copy)
            if len(results) >= top_k:
                break

        return results

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """jieba 分词，过滤标点和空白"""
        if not text:
            return []
        tokens = jieba.lcut(text)
        # 过滤单字标点、空白、纯数字（保留有意义的中医术语）
        return [
            t.strip() for t in tokens
            if t.strip() and len(t.strip()) > 0 and not t.strip().isspace()
            and t.strip() not in "，。、；：！？·…—（）()【】[]《》<>「」\"' \t\n\r"
        ]
