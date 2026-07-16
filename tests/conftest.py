"""共享测试 fixtures 和 mock 对象"""
import pytest
from unittest.mock import MagicMock, patch


# ============================================================
#  模拟数据
# ============================================================

MOCK_FANGJI_DATA = [
    {
        "name": "麻黄汤",
        "pinyin": "Ma Huang Tang",
        "category": "解表剂",
        "ingredients": "麻黄6g 桂枝4g 杏仁9g 甘草3g",
        "usage": "水煎服，每日一剂，分两次温服",
        "functions": "发汗解表，宣肺平喘",
        "clinical_use": "外感风寒表实证。恶寒发热，头身疼痛，无汗而喘。",
        "contraindications": "表虚自汗、外感风热者忌用",
        "precautions": "麻黄含麻黄碱，高血压、心脏病患者慎用",
        "adverse_reactions": "",
    },
    {
        "name": "桂枝汤",
        "pinyin": "Gui Zhi Tang",
        "category": "解表剂",
        "ingredients": "桂枝9g 芍药9g 甘草6g 生姜9g 大枣12枚",
        "usage": "水煎服",
        "functions": "解肌发表，调和营卫",
        "clinical_use": "外感风寒表虚证。头痛发热，汗出恶风。",
        "contraindications": "",
        "precautions": "",
        "adverse_reactions": "",
    },
]

MOCK_HERB_DATA = [
    {
        "name": "人参",
        "latin_name": "Panax ginseng",
        "nature_taste_meridian": "甘、微苦，平。归脾、肺、心经",
        "functions": "大补元气，复脉固脱，补脾益肺，生津养血，安神益智",
        "usage": "煎服3-9g，另煎兑服",
        "source": "五加科植物人参的干燥根",
        "processing": "生晒、蒸制",
        "caution": "不宜与藜芦、五灵脂同用。实证、热证忌服。",
    },
    {
        "name": "附子",
        "latin_name": "Aconitum carmichaelii",
        "nature_taste_meridian": "辛、甘，大热。有毒。归心、肾、脾经",
        "functions": "回阳救逆，补火助阳，散寒止痛",
        "usage": "煎服3-15g，先煎0.5-1小时，至口尝无麻舌感",
        "source": "毛茛科植物乌头的子根加工品",
        "processing": "盐制、黑顺片",
        "caution": "孕妇禁用。不宜与半夏、瓜蒌、贝母、白蔹、白及同用。生品外用，内服须炮制。",
    },
]

MOCK_ACUPOINT_DATA = [
    {
        "name": "足三里",
        "pinyin": "Zu San Li",
        "meridian": "足阳明胃经",
        "location": "在小腿前外侧，当犊鼻下3寸，距胫骨前缘一横指",
        "method": "屈膝取穴",
        "efficacy": "健脾和胃，扶正培元，通经活络",
        "indications": "胃痛、呕吐、腹胀、泄泻、便秘等脾胃病症，虚劳羸瘦",
        "technique": "直刺1-2寸",
        "cautions": "",
    },
    {
        "name": "合谷",
        "pinyin": "He Gu",
        "meridian": "手阳明大肠经",
        "location": "在手背，第1、2掌骨间，当第二掌骨桡侧的中点处",
        "method": "以一手拇指指骨关节横纹对准另一手拇食指之间指蹼缘上",
        "efficacy": "疏风解表，行气活血，通络止痛",
        "indications": "头痛、牙痛、咽喉肿痛等头面五官病症",
        "technique": "直刺0.5-1寸",
        "cautions": "孕妇禁针",
    },
]

MOCK_CONSTITUTION_DATA = [
    {
        "type_name": "气虚质",
        "characteristics": "元气不足，以疲乏、气短、自汗等气虚表现为主要特征",
        "tendency": "易患感冒、内脏下垂等病",
        "regulation": "补气养气，培补元气",
        "diet_advice": "多食益气健脾的食物，如山药、莲子、大枣、小米等",
        "exercise_advice": "避免剧烈运动，宜散步、太极拳",
        "acupoint_advice": "可按摩气海、足三里",
    },
    {
        "type_name": "阳虚质",
        "characteristics": "阳气不足，以畏寒怕冷、手足不温等虚寒表现为主要特征",
        "tendency": "易患痰饮、肿胀、泄泻等病",
        "regulation": "温阳益气",
        "diet_advice": "宜食温热食物，如羊肉、韭菜、生姜等",
        "exercise_advice": "多做舒缓运动，如散步、太极拳",
        "acupoint_advice": "可艾灸关元、命门",
    },
]

MOCK_CONSTITUTION_LIST = [
    {"type_name": "平和质", "characteristics": "阴阳气血调和，以体态适中、面色润泽、精力充沛为主要特征"},
    {"type_name": "气虚质", "characteristics": "元气不足，以疲乏、气短、自汗等气虚表现为主要特征"},
    {"type_name": "阳虚质", "characteristics": "阳气不足，以畏寒怕冷、手足不温等虚寒表现为主要特征"},
    {"type_name": "阴虚质", "characteristics": "阴液亏少，以口燥咽干、手足心热等虚热表现为主要特征"},
    {"type_name": "痰湿质", "characteristics": "痰湿凝聚，以形体肥胖、腹部肥满、口黏苔腻等痰湿表现为主要特征"},
    {"type_name": "湿热质", "characteristics": "湿热内蕴，以面垢油光、口苦、苔黄腻等湿热表现为主要特征"},
    {"type_name": "血瘀质", "characteristics": "血行不畅，以肤色晦暗、舌质紫暗等血瘀表现为主要特征"},
    {"type_name": "气郁质", "characteristics": "气机郁滞，以神情抑郁、忧虑脆弱等气郁表现为主要特征"},
    {"type_name": "特禀质", "characteristics": "先天失常，以生理缺陷、过敏反应等为主要特征"},
]

MOCK_RAG_RESULTS = [
    {
        "category": "formula",
        "score": 0.85,
        "content": "四物汤：养血活血。组成：当归 川芎 白芍 熟地黄。用于血虚血瘀所致的月经不调、痛经。",
        "metadata": {"name": "四物汤", "source": "太平惠民和剂局方"},
    },
    {
        "category": "herb",
        "score": 0.72,
        "content": "川芎：活血行气，祛风止痛。用于血瘀气滞所致的胸痹心痛、头痛、风湿痹痛。",
        "metadata": {"name": "川芎", "meridian": "肝经、胆经、心包经"},
    },
    {
        "category": "formula",
        "score": 0.68,
        "content": "血府逐瘀汤：活血化瘀，行气止痛。用于胸中血瘀证。",
        "metadata": {"name": "血府逐瘀汤", "source": "医林改错"},
    },
]

MOCK_GRAPH_ENTITIES = [
    {
        "name": "麻黄汤",
        "type": "Formula",
        "properties": {
            "efficacy": "发汗解表，宣肺平喘",
            "composition": "麻黄 桂枝 杏仁 甘草",
            "indications": "外感风寒表实证",
            "contraindications": "表虚自汗者忌用",
        },
    },
    {
        "name": "桂枝",
        "type": "Herb",
        "properties": {
            "nature": "温",
            "taste": "辛、甘",
            "meridian": "心、肺、膀胱经",
            "efficacy": "发汗解肌，温通经脉",
            "dosage": "3-10g",
        },
    },
]

MOCK_GRAPH_RELATIONS = {
    "outgoing": [
        {"relation": "CONTAINS", "target": "桂枝"},
        {"relation": "CONTAINS", "target": "杏仁"},
    ],
    "incoming": [],
    "paths": [],
}

MOCK_TREATMENT_PATHS = [
    {
        "level1": {"name": "麻黄汤", "relation": "TREATS"},
        "level2": {"name": "桂枝", "relation": "CONTAINS"},
    },
    {
        "level1": {"name": "桂枝汤", "relation": "TREATS"},
        "level2": {"name": "芍药", "relation": "CONTAINS"},
    },
]


# ============================================================
#  Fixtures
# ============================================================

@pytest.fixture
def mock_db():
    """模拟 TCMDatabase"""
    db = MagicMock()
    db.search_fangji.return_value = MOCK_FANGJI_DATA
    db.search_herb.return_value = MOCK_HERB_DATA
    db.search_acupoint.return_value = MOCK_ACUPOINT_DATA
    db.get_constitution.return_value = MOCK_CONSTITUTION_DATA[0]
    db.list_constitutions.return_value = MOCK_CONSTITUTION_LIST
    return db


@pytest.fixture
def mock_empty_db():
    """模拟空数据库（无查询结果）"""
    db = MagicMock()
    db.search_fangji.return_value = []
    db.search_herb.return_value = []
    db.search_acupoint.return_value = []
    db.get_constitution.return_value = None
    db.list_constitutions.return_value = []
    return db


@pytest.fixture
def mock_retriever():
    """模拟 TCMRetriever"""
    retriever = MagicMock()
    retriever.retrieve.return_value = MOCK_RAG_RESULTS
    retriever.format_context.return_value = (
        "【相关中医知识】\n"
        "1. [formula] 四物汤：养血活血... (score: 0.85)\n"
        "2. [herb] 川芎：活血行气... (score: 0.72)\n"
    )
    return retriever


@pytest.fixture
def mock_graph_retriever():
    """模拟 GraphRetriever"""
    retriever = MagicMock()
    retriever.search_entities.return_value = MOCK_GRAPH_ENTITIES
    retriever.get_entity_relations.return_value = MOCK_GRAPH_RELATIONS
    retriever.find_related_entities.return_value = [
        {"name": "桂枝", "type": "Herb", "properties": {"efficacy": "发汗解肌"}},
        {"name": "杏仁", "type": "Herb", "properties": {"efficacy": "止咳平喘"}},
    ]
    retriever.find_treatment_path.return_value = MOCK_TREATMENT_PATHS
    retriever.format_context.return_value = (
        "【治疗路径】\n"
        "路径1: 麻黄汤 → 治疗 → 桂枝\n"
        "路径2: 桂枝汤 → 治疗 → 芍药\n"
    )
    return retriever
