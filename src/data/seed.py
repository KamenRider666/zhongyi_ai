"""种子数据初始化 - 将示例数据写入 SQLite 和 Milvus"""

import sys
import io

# 修复 Windows GBK 编码问题
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from src.data.database import TCMDatabase


def init_fangji_data(db: TCMDatabase) -> None:
    """初始化方剂示例数据"""
    conn = db.get_conn()
    cursor = conn.cursor()

    fangjis = [
        {
            "name": "麻黄汤",
            "alias": "",
            "source": "《伤寒论》",
            "category": "解表剂",
            "composition": "麻黄9g、桂枝6g、杏仁9g、炙甘草3g",
            "usage_method": "水煎服，每日1剂，分2-3次温服。服后盖被取微汗。",
            "efficacy": "发汗解表，宣肺平喘",
            "indications": "外感风寒表实证。恶寒发热，头痛身疼，无汗而喘，舌苔薄白，脉浮紧。",
            "contraindications": "表虚自汗、外感风热、体虚者禁用。高血压患者慎用。",
            "notes": "麻黄为发汗峻药，不可过量使用。"
        },
        {
            "name": "桂枝汤",
            "alias": "阳旦汤",
            "source": "《伤寒论》",
            "category": "解表剂",
            "composition": "桂枝9g、白芍9g、炙甘草6g、生姜9g、大枣4枚",
            "usage_method": "水煎服，每日1剂。服后啜热稀粥，温覆取微汗。",
            "efficacy": "解肌发表，调和营卫",
            "indications": "外感风寒表虚证。头痛发热，汗出恶风，鼻鸣干呕，苔白不渴，脉浮缓或浮弱。",
            "contraindications": "外感风寒表实证禁用。",
            "notes": "《伤寒论》第一方，为群方之冠。"
        },
        {
            "name": "小柴胡汤",
            "alias": "",
            "source": "《伤寒论》",
            "category": "和解剂",
            "composition": "柴胡12g、黄芩9g、人参6g、半夏9g、炙甘草6g、生姜9g、大枣4枚",
            "usage_method": "水煎服，每日1剂，分2-3次温服。",
            "efficacy": "和解少阳",
            "indications": "少阳证。往来寒热，胸胁苦满，默默不欲饮食，心烦喜呕，口苦咽干，目眩，脉弦。",
            "contraindications": "阴虚血少者慎用。",
            "notes": "少阳病主方，临床应用极为广泛。"
        },
        {
            "name": "四君子汤",
            "alias": "",
            "source": "《太平惠民和剂局方》",
            "category": "补益剂",
            "composition": "人参9g、白术9g、茯苓9g、炙甘草6g",
            "usage_method": "水煎服，每日1剂。",
            "efficacy": "益气健脾",
            "indications": "脾胃气虚证。面色萎白，语声低微，气短乏力，食少便溏，舌淡苔白，脉虚弱。",
            "contraindications": "实证、热证慎用。",
            "notes": "补气基础方，四味药皆平和之品，不热不燥。"
        },
        {
            "name": "四物汤",
            "alias": "",
            "source": "《太平惠民和剂局方》",
            "category": "补益剂",
            "composition": "熟地黄12g、当归9g、白芍9g、川芎6g",
            "usage_method": "水煎服，每日1剂。",
            "efficacy": "补血和血",
            "indications": "营血虚滞证。心悸失眠，头晕目眩，面色无华，妇人月经不调，舌淡，脉细。",
            "contraindications": "脾胃虚寒、大便溏泄者慎用。",
            "notes": "补血基础方，后世众多补血方剂由此化裁。"
        },
        {
            "name": "六味地黄丸",
            "alias": "地黄丸",
            "source": "《小儿药证直诀》",
            "category": "补益剂",
            "composition": "熟地黄24g、山茱萸12g、山药12g、泽泻9g、牡丹皮9g、茯苓9g",
            "usage_method": "炼蜜为丸，每服6-9g，每日2-3次。亦可水煎服。",
            "efficacy": "滋阴补肾",
            "indications": "肾阴虚证。腰膝酸软，头晕目眩，耳鸣耳聋，盗汗遗精，手足心热，口燥咽干，舌红少苔，脉细数。",
            "contraindications": "脾虚泄泻者慎用。",
            "notes": "三补三泻，补而不滞，为滋补肾阴的代表方。"
        },
        {
            "name": "逍遥散",
            "alias": "",
            "source": "《太平惠民和剂局方》",
            "category": "和解剂",
            "composition": "柴胡9g、当归9g、白芍9g、白术9g、茯苓9g、炙甘草4.5g、煨生姜3g、薄荷3g",
            "usage_method": "水煎服，每日1剂。",
            "efficacy": "疏肝解郁，养血健脾",
            "indications": "肝郁血虚脾弱证。两胁作痛，头痛目眩，口燥咽干，神疲食少，或月经不调，乳房胀痛，脉弦而虚。",
            "contraindications": "阴虚阳亢者慎用。",
            "notes": "妇科调经常用方，疏肝解郁代表方。"
        },
        {
            "name": "二陈汤",
            "alias": "",
            "source": "《太平惠民和剂局方》",
            "category": "祛痰剂",
            "composition": "半夏9g、橘红9g、茯苓6g、炙甘草3g、生姜3g、乌梅1个",
            "usage_method": "水煎服，每日1剂。",
            "efficacy": "燥湿化痰，理气和中",
            "indications": "湿痰证。咳嗽痰多，色白易咯，胸膈痞闷，恶心呕吐，肢体困重，舌苔白滑，脉滑。",
            "contraindications": "阴虚燥咳、痰中带血者禁用。",
            "notes": "治痰通用方，为祛痰剂的基础方。"
        },
        {
            "name": "银翘散",
            "alias": "",
            "source": "《温病条辨》",
            "category": "解表剂",
            "composition": "金银花15g、连翘15g、桔梗9g、薄荷9g、淡竹叶6g、荆芥穗6g、牛蒡子9g、淡豆豉6g、甘草6g",
            "usage_method": "水煎服，每日1剂。宜武火急煎。",
            "efficacy": "辛凉透表，清热解毒",
            "indications": "温病初起。发热，微恶风寒，头痛口渴，咳嗽咽痛，舌尖红，苔薄白或薄黄，脉浮数。",
            "contraindications": "风寒感冒禁用。",
            "notes": "辛凉解表代表方，主治风热感冒。"
        },
        {
            "name": "藿香正气散",
            "alias": "",
            "source": "《太平惠民和剂局方》",
            "category": "祛湿剂",
            "composition": "藿香9g、紫苏6g、白芷6g、半夏曲9g、陈皮6g、白术9g、茯苓9g、厚朴6g、大腹皮6g、桔梗6g、甘草3g、生姜3g、大枣2枚",
            "usage_method": "水煎服，每日1剂。",
            "efficacy": "解表化湿，理气和中",
            "indications": "外感风寒，内伤湿滞证。恶寒发热，头痛，胸膈满闷，脘腹疼痛，恶心呕吐，肠鸣泄泻，舌苔白腻。",
            "contraindications": "阴虚火旺者慎用。",
            "notes": "夏季外感风寒、内伤湿滞常用方。"
        },
    ]

    for fj in fangjis:
        cursor.execute(
            """INSERT OR IGNORE INTO fangji
            (name, alias, source, category, composition, usage_method, efficacy, indications, contraindications, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (fj["name"], fj["alias"], fj["source"], fj["category"], fj["composition"],
             fj["usage_method"], fj["efficacy"], fj["indications"], fj["contraindications"], fj["notes"]),
        )

    conn.commit()
    conn.close()


def init_herb_data(db: TCMDatabase) -> None:
    """初始化药材示例数据"""
    conn = db.get_conn()
    cursor = conn.cursor()

    herbs = [
        {
            "name": "麻黄",
            "latin_name": "Ephedrae Herba",
            "alias": "龙沙、卑相",
            "nature": "温",
            "taste": "辛、微苦",
            "meridian": "肺、膀胱",
            "efficacy": "发汗解表，宣肺平喘，利水消肿",
            "indications": "风寒感冒，胸闷喘咳，风水浮肿",
            "dosage": "2-9g",
            "toxicity": "有毒，含麻黄碱",
            "contraindications": "表虚自汗、阴虚盗汗、高血压、心脏病患者禁用"
        },
        {
            "name": "桂枝",
            "latin_name": "Cinnamomi Ramulus",
            "alias": "柳桂",
            "nature": "温",
            "taste": "辛、甘",
            "meridian": "心、肺、膀胱",
            "efficacy": "发汗解肌，温通经脉，助阳化气",
            "indications": "风寒感冒，脘腹冷痛，血寒经闭，关节痹痛，痰饮水肿",
            "dosage": "3-9g",
            "toxicity": "无毒",
            "contraindications": "外感热病、阴虚火旺、血热妄行者禁用"
        },
        {
            "name": "人参",
            "latin_name": "Ginseng Radix et Rhizoma",
            "alias": "棒槌、神草",
            "nature": "微温",
            "taste": "甘、微苦",
            "meridian": "脾、肺、心、肾",
            "efficacy": "大补元气，复脉固脱，补脾益肺，生津养血，安神益智",
            "indications": "体虚欲脱，肢冷脉微，脾虚食少，肺虚喘咳，津伤口渴，内热消渴，惊悸失眠",
            "dosage": "3-9g",
            "toxicity": "无毒",
            "contraindications": "实证、热证、正气不虚者禁用。不宜与藜芦、五灵脂同用。"
        },
        {
            "name": "当归",
            "latin_name": "Angelicae Sinensis Radix",
            "alias": "秦归、云归",
            "nature": "温",
            "taste": "甘、辛",
            "meridian": "肝、心、脾",
            "efficacy": "补血活血，调经止痛，润肠通便",
            "indications": "血虚萎黄，月经不调，经闭痛经，虚寒腹痛，风湿痹痛，肠燥便秘",
            "dosage": "6-12g",
            "toxicity": "无毒",
            "contraindications": "湿盛中满、大便溏泄者慎用"
        },
        {
            "name": "黄芪",
            "latin_name": "Astragali Radix",
            "alias": "黄耆、绵芪",
            "nature": "微温",
            "taste": "甘",
            "meridian": "脾、肺",
            "efficacy": "补气升阳，固表止汗，利水消肿，生津养血，托毒排脓",
            "indications": "气虚乏力，食少便溏，中气下陷，久泻脱肛，表虚自汗，气虚水肿",
            "dosage": "9-30g",
            "toxicity": "无毒",
            "contraindications": "表实邪盛、气滞湿阻、阴虚阳亢者禁用"
        },
        {
            "name": "附子",
            "latin_name": "Aconiti Lateralis Radix Praeparata",
            "alias": "天雄、黑附子",
            "nature": "大热",
            "taste": "辛、甘",
            "meridian": "心、肾、脾",
            "efficacy": "回阳救逆，补火助阳，散寒止痛",
            "indications": "亡阳虚脱，肢冷脉微，心阳不足，肾阳虚衰，寒湿痹痛",
            "dosage": "3-15g，先煎30-60分钟",
            "toxicity": "有毒！含乌头碱，必须炮制后使用，必须先煎以减毒",
            "contraindications": "孕妇禁用。阴虚阳亢、真热假寒者禁用。不宜与半夏、瓜蒌、贝母、白及、白蔹同用。"
        },
        {
            "name": "甘草",
            "latin_name": "Glycyrrhizae Radix et Rhizoma",
            "alias": "国老、甜草",
            "nature": "平",
            "taste": "甘",
            "meridian": "心、肺、脾、胃",
            "efficacy": "补脾益气，清热解毒，祛痰止咳，缓急止痛，调和诸药",
            "indications": "脾胃虚弱，倦怠乏力，心悸气短，咳嗽痰多，脘腹四肢挛急疼痛，缓解药物毒性",
            "dosage": "2-10g",
            "toxicity": "无毒",
            "contraindications": "不宜与海藻、大戟、甘遂、芫花同用。长期大量服用可致水肿。"
        },
        {
            "name": "熟地黄",
            "latin_name": "Rehmanniae Radix Praeparata",
            "alias": "熟地",
            "nature": "微温",
            "taste": "甘",
            "meridian": "肝、肾",
            "efficacy": "补血滋阴，益精填髓",
            "indications": "血虚萎黄，心悸怔忡，月经不调，肝肾阴虚，腰膝酸软，盗汗遗精",
            "dosage": "9-15g",
            "toxicity": "无毒",
            "contraindications": "脾胃虚弱、气滞痰多、腹满便溏者慎用"
        },
        {
            "name": "金银花",
            "latin_name": "Lonicerae Japonicae Flos",
            "alias": "双花、忍冬花",
            "nature": "寒",
            "taste": "甘",
            "meridian": "肺、心、胃",
            "efficacy": "清热解毒，疏散风热",
            "indications": "痈肿疔疮，喉痹丹毒，风热感冒，温病发热",
            "dosage": "6-15g",
            "toxicity": "无毒",
            "contraindications": "脾胃虚寒、气虚疮疡脓清者慎用"
        },
        {
            "name": "茯苓",
            "latin_name": "Poria",
            "alias": "茯菟、云苓",
            "nature": "平",
            "taste": "甘、淡",
            "meridian": "心、肺、脾、肾",
            "efficacy": "利水渗湿，健脾宁心",
            "indications": "水肿尿少，痰饮眩悸，脾虚食少，便溏泄泻，心神不安，惊悸失眠",
            "dosage": "10-15g",
            "toxicity": "无毒",
            "contraindications": "虚寒精滑、气虚下陷者慎用"
        },
    ]

    for h in herbs:
        cursor.execute(
            """INSERT OR IGNORE INTO herb
            (name, latin_name, alias, nature, taste, meridian, efficacy, indications, dosage, toxicity, contraindications)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (h["name"], h["latin_name"], h["alias"], h["nature"], h["taste"],
             h["meridian"], h["efficacy"], h["indications"], h["dosage"], h["toxicity"], h["contraindications"]),
        )

    conn.commit()
    conn.close()


def init_acupoint_data(db: TCMDatabase) -> None:
    """初始化穴位示例数据"""
    conn = db.get_conn()
    cursor = conn.cursor()

    acupoints = [
        {
            "name": "足三里",
            "pinyin": "Zúsānlǐ",
            "meridian": "足阳明胃经",
            "location": "在小腿外侧，犊鼻下3寸，胫骨前嵴外1横指处",
            "method": "屈膝取穴",
            "efficacy": "健脾和胃，扶正培元，通经活络",
            "indications": "胃痛呕吐，腹胀腹泻，便秘，下肢痿痹，虚劳诸证",
            "technique": "直刺1-2寸；可灸",
            "cautions": "孕妇慎用"
        },
        {
            "name": "合谷",
            "pinyin": "Hégǔ",
            "meridian": "手阳明大肠经",
            "location": "在手背，第1、2掌骨间，当第2掌骨桡侧的中点处",
            "method": "以一手拇指指骨关节横纹，放在另一手拇、食指之间的指蹼缘上，当拇指尖下是穴",
            "efficacy": "疏风解表，行气活血，通络止痛",
            "indications": "头痛目赤，鼻衄齿痛，口眼歪斜，耳聋，发热恶寒，经闭滞产",
            "technique": "直刺0.5-1寸；可灸",
            "cautions": "孕妇禁针"
        },
        {
            "name": "内关",
            "pinyin": "Nèiguān",
            "meridian": "手厥阴心包经",
            "location": "在前臂前区，腕掌侧远端横纹上2寸，掌长肌腱与桡侧腕屈肌腱之间",
            "method": "伸臂仰掌取穴",
            "efficacy": "宁心安神，理气止痛",
            "indications": "心痛心悸，胸闷胁痛，胃痛呕吐，失眠眩晕，偏头痛",
            "technique": "直刺0.5-1寸；可灸",
            "cautions": ""
        },
        {
            "name": "三阴交",
            "pinyin": "Sānyīnjiāo",
            "meridian": "足太阴脾经",
            "location": "在小腿内侧，内踝尖上3寸，胫骨内侧缘后际",
            "method": "正坐或仰卧取穴",
            "efficacy": "健脾利湿，调补肝肾，调经止带",
            "indications": "月经不调，带下阴挺，不孕滞产，遗精阳痿，失眠眩晕",
            "technique": "直刺1-1.5寸；可灸",
            "cautions": "孕妇禁针"
        },
        {
            "name": "太冲",
            "pinyin": "Tàichōng",
            "meridian": "足厥阴肝经",
            "location": "在足背，第1、2跖骨间，跖骨底结合部前方凹陷中",
            "method": "正坐或仰卧取穴",
            "efficacy": "平肝息风，疏肝理气，通络止痛",
            "indications": "头痛眩晕，目赤肿痛，胁痛腹胀，月经不调，小儿惊风",
            "technique": "直刺0.5-1寸；可灸",
            "cautions": ""
        },
        {
            "name": "关元",
            "pinyin": "Guānyuán",
            "meridian": "任脉",
            "location": "在下腹部，脐中下3寸，前正中线上",
            "method": "仰卧取穴",
            "efficacy": "培补元气，导赤通淋",
            "indications": "遗精阳痿，月经不调，带下不孕，遗尿尿频，腹痛腹泻",
            "technique": "直刺1-1.5寸；可灸",
            "cautions": "孕妇慎用"
        },
        {
            "name": "百会",
            "pinyin": "Bǎihuì",
            "meridian": "督脉",
            "location": "在头部，前发际正中直上5寸",
            "method": "正坐，两耳尖连线中点处",
            "efficacy": "升阳举陷，醒脑开窍",
            "indications": "头痛眩晕，中风失语，癫狂痫证，脱肛阴挺，失眠健忘",
            "technique": "平刺0.5-0.8寸；可灸",
            "cautions": "小儿囟门未闭者禁针"
        },
        {
            "name": "涌泉",
            "pinyin": "Yǒngquán",
            "meridian": "足少阴肾经",
            "location": "在足底，屈足卷趾时足心最凹陷处",
            "method": "仰卧或正坐，卷足取穴",
            "efficacy": "滋阴益肾，平肝息风，醒脑开窍",
            "indications": "头痛眩晕，失眠多梦，咽喉肿痛，小便不利，小儿惊风",
            "technique": "直刺0.5-1寸；可灸",
            "cautions": ""
        },
    ]

    for ap in acupoints:
        cursor.execute(
            """INSERT OR IGNORE INTO acupoint
            (name, pinyin, meridian, location, method, efficacy, indications, technique, cautions)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (ap["name"], ap["pinyin"], ap["meridian"], ap["location"],
             ap["method"], ap["efficacy"], ap["indications"], ap["technique"], ap["cautions"]),
        )

    conn.commit()
    conn.close()


def init_constitution_data(db: TCMDatabase) -> None:
    """初始化体质数据"""
    conn = db.get_conn()
    cursor = conn.cursor()

    constitutions = [
        {
            "type_name": "平和质",
            "characteristics": "体形匀称健壮，面色红润，精力充沛，睡眠良好，二便正常，舌淡红苔薄白，脉和缓有力",
            "tendency": "平素患病较少，适应能力强",
            "regulation": "重在维护，饮食有节，劳逸结合，坚持锻炼",
            "diet_advice": "饮食宜规律，不宜过饥过饱，不宜过冷过热，荤素搭配合理",
            "exercise_advice": "可根据个人爱好选择跑步、游泳、球类等运动",
            "acupoint_advice": "足三里、涌泉，每日按摩5-10分钟"
        },
        {
            "type_name": "气虚质",
            "characteristics": "肌肉松软，语声低弱，气短懒言，易疲乏，易出汗，舌淡红边有齿痕，脉弱",
            "tendency": "易患感冒、内脏下垂等病",
            "regulation": "益气健脾，培补元气",
            "diet_advice": "多食益气健脾食物：小米、山药、土豆、鸡肉、牛肉、大枣、香菇。少食耗气食物：萝卜、空心菜",
            "exercise_advice": "宜选择太极拳、八段锦等柔缓运动，避免剧烈运动",
            "acupoint_advice": "足三里、气海、关元，可艾灸"
        },
        {
            "type_name": "阳虚质",
            "characteristics": "形体白胖，畏寒怕冷，手足不温，喜热饮食，精神不振，舌淡胖嫩，脉沉迟",
            "tendency": "易患痰饮、肿胀、泄泻等病",
            "regulation": "温阳补气，温里散寒",
            "diet_advice": "多食温阳食物：羊肉、韭菜、生姜、核桃、桂圆。少食生冷寒凉食物：西瓜、梨、苦瓜",
            "exercise_advice": "宜在阳光充足时进行户外活动，如散步、慢跑",
            "acupoint_advice": "关元、命门、足三里，宜艾灸"
        },
        {
            "type_name": "阴虚质",
            "characteristics": "体形偏瘦，手足心热，口燥咽干，喜冷饮，大便干燥，舌红少津，脉细数",
            "tendency": "易患虚劳、不寐等病",
            "regulation": "滋阴降火，养阴润燥",
            "diet_advice": "多食滋阴食物：银耳、百合、梨、鸭肉、甲鱼、蜂蜜。少食辛辣燥热食物：辣椒、花椒、羊肉",
            "exercise_advice": "宜选择游泳、太极拳等中小强度运动，避免大量出汗",
            "acupoint_advice": "太溪、三阴交、涌泉，以按摩为主"
        },
        {
            "type_name": "痰湿质",
            "characteristics": "体形肥胖，腹部肥满松软，面部油脂多，多汗且黏，胸闷痰多，舌苔白腻，脉滑",
            "tendency": "易患消渴、中风、胸痹等病",
            "regulation": "健脾利湿，化痰泄浊",
            "diet_advice": "多食健脾化湿食物：薏米、冬瓜、赤小豆、山药。少食肥甘厚腻：甜食、油炸、肥肉",
            "exercise_advice": "宜进行长时间有氧运动：快走、慢跑、游泳",
            "acupoint_advice": "丰隆、足三里、阴陵泉，可艾灸"
        },
    ]

    for c in constitutions:
        cursor.execute(
            """INSERT OR IGNORE INTO constitution
            (type_name, characteristics, tendency, regulation, diet_advice, exercise_advice, acupoint_advice)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (c["type_name"], c["characteristics"], c["tendency"], c["regulation"],
             c["diet_advice"], c["exercise_advice"], c["acupoint_advice"]),
        )

    conn.commit()
    conn.close()


def init_all(db_path: str = "data/tcm.db") -> None:
    """初始化所有种子数据"""
    db = TCMDatabase(db_path)
    db.init_db()
    init_fangji_data(db)
    init_herb_data(db)
    init_acupoint_data(db)
    init_constitution_data(db)
    print("✓ 中医数据库初始化完成")
    print(f"  - 方剂: 10 条")
    print(f"  - 药材: 10 条")
    print(f"  - 穴位: 8 条")
    print(f"  - 体质: 5 条")


if __name__ == "__main__":
    init_all()
