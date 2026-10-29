#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cluster_large_concepts.py
将扁平堆叠的小概念卡片，按照学术体系归纳提炼出【大概念】父节点！
- 典型案例：本义、基本义、引申义、比喻义 -> 归纳为【词义衍生与类型】
- 联合复句、偏正复句、特殊句式、语音物理属性、二语习得过程假说、岁令节日等全面结构化归类
- 支持小节下深层树状多级展开，彻底解决“层级扁平、缺乏大分类”的问题！
"""

import json
import glob
import os
import re

BASE_DIR = "/data/user/0/cc.codroid/files/home/workspace/kaoyan_mindmap"
LEAVES_DIR = os.path.join(BASE_DIR, "out", "leaves")

# 学科大概念权威归纳字典: (大概念名称) -> 触发包含的小概念关键词列表
CONCEPT_HIERARCHY = [
    # --- 现代汉语通论 ---
    ("词义衍生与类型", ["本义", "基本义", "引申义", "比喻义"]),
    ("词义分析理论", ["义项", "义素", "义位", "义素分析法", "义项划分", "词义构成"]),
    ("词汇分类系统", ["同音词", "同形词", "单义词", "多义词", "同义词", "反义词", "同音同形词"]),
    ("词汇熟语系统", ["成语", "惯用语", "歇后语", "谚语", "熟语"]),
    ("构词法与造词法", ["构词法", "造词法", "单纯词", "合成词", "词根", "词缀", "重叠"]),
    ("语音物理属性", ["音高", "音强", "音长", "音色", "物理属性"]),
    ("语音生理与本质属性", ["生理属性", "社会属性", "发音器官"]),
    ("普通话音节系统", ["声母", "韵母", "声调", "音节", "零声母", "押韵"]),
    ("普通话语流音变", ["轻声", "儿化", "变调", "啊的音变", "音变"]),
    ("实词分类体系", ["名词", "动词", "形容词", "区别词", "数词", "量词", "代词", "副词", "实词"]),
    ("虚词分类体系", ["介词", "连词", "助词", "语气词", "叹词", "拟声词", "虚词"]),
    ("短语分类与结构", ["偏正短语", "述宾短语", "述补短语", "联合短语", "主谓短语", "“的”字结构", "所字结构", "固定短语", "短语"]),
    ("短语分析方法", ["层次分析法", "中心词分析法", "直接成分分析法", "层次分析"]),
    ("单句句型系统", ["主谓句", "非主谓句", "名词主谓句", "动词主谓句", "形容词主谓句", "句型"]),
    ("处置与被动句式", ["把字句", "被字句", "把字句的结构类型", "“把”字宾语的特点"]),
    ("复杂特殊句式", ["连动句", "兼语句", "存现句", "双宾语句", "主谓谓语句", "句式"]),
    ("句类语气系统", ["陈述句", "疑问句", "祈使句", "感叹句", "句类"]),
    ("联合复句", ["并列复句", "顺承复句", "递进复句", "选择复句"]),
    ("偏正复句", ["转折复句", "因果复句", "条件复句", "让步复句", "假设复句", "目的复句"]),
    ("多重复句与紧缩句", ["多重复句", "紧缩复句", "划线分析法", "多重复句分析"]),
    ("结构歧义分析", ["歧义现象", "表述歧义", "组合歧义", "歧义的消除", "歧义"]),
    ("言语行为理论", ["言语行为", "言内行为", "言外行为", "言后行为"]),
    ("会话原则与合作", ["合作原则", "礼貌原则", "会话含义", "数量准则", "质量准则"]),
    ("常见修辞辞格", ["比喻", "比拟", "借代", "夸张", "对偶", "排比", "辞格"]),
    ("病句修改原则", ["病句", "病句类型", "修改病句的原则"]),

    # --- 中国文化要略 ---
    ("岁首与春季节令", ["春节", "除夕", "元宵节", "立春"]),
    ("春夏季令节日", ["清明节", "端午节", "寒食节"]),
    ("秋冬季令节日", ["七夕节", "中秋节", "重阳节", "腊八节", "冬至"]),
    ("古代科举考试程序", ["童试", "乡试", "会试", "殿试", "科举制"]),
    ("科举功名与身份", ["生员", "秀才", "举人", "贡士", "进士", "状元", "榜眼", "探花"]),
    ("先秦儒家学派", ["孔子", "孟子", "荀子", "仁政", "礼治"]),
    ("先秦道家学派", ["老子", "庄子", "无为而治", "逍遥游"]),
    ("宋明理学心学", ["宋明理学", "程朱理学", "陆王心学", "朱熹", "王阳明"]),
    ("古代图书分类", ["经部", "史部", "子部", "集部", "四库全书"]),
    ("四大民间传说", ["牛郎织女", "孟姜女", "白蛇传", "梁山伯与祝英台"]),
    ("古代宫廷建筑", ["故宫", "太和殿", "中和殿", "保和殿", "前朝后寝"]),

    # --- 对外汉语教育学引论 ---
    ("第二语言习得过程理论", ["对比分析", "对比分析假说", "偏误分析", "中介语", "中介语理论", "石化现象"]),
    ("学习者个体情感因素", ["学习动机", "语言态度", "语言焦虑", "移情", "抑制"]),
    ("克拉申二语习得理论", ["输入假说", "情感过滤假说", "习得与学得假说", "自然顺序假说", "监控假说"]),
    ("第二语言教学法传统流派", ["语法翻译法", "直接法", "听说法", "视听法"]),
    ("第二语言教学法人本与交际流派", ["交际法", "认知法", "任务型教学法", "暗示法", "全身反应法"]),
    ("语言测试质量指标", ["信度", "效度", "区分度", "难度"]),
    ("语言测试分类体系", ["水平测试", "成绩测试", "诊断测试", "潜能测试"]),
]

def clean_t(s):
    if not s: return ""
    s = s.strip()
    s = re.sub(r'^(【名词解释】|名词解释：|名词解释)', '', s).strip()
    return re.sub(r'^[“"‘\'《](.*?)[”"’\'》]$', r'\1', s).strip()

def cluster_leaf(leaf_data):
    kps = leaf_data.get("kps", [])
    if len(kps) < 4:
        # 卡片数量较少时，无需过多层级，保持清晰直观
        return leaf_data

    assigned = set()
    groups = []

    for group_title, member_keywords in CONCEPT_HIERARCHY:
        matched_kps = []
        for i, kp in enumerate(kps):
            if i in assigned: continue
            t = clean_t(kp.get("title", ""))
            if any(k == t or (len(k) >= 2 and k in t) for k in member_keywords):
                matched_kps.append(kp)
                assigned.add(i)

        if len(matched_kps) >= 2: # 至少有两个子概念才聚集成大概念组
            groups.append({
                "title": group_title,
                "weight": "high" if any(k.get("weight") == "high" for k in matched_kps) else "normal",
                "kps": matched_kps
            })
        elif len(matched_kps) == 1:
            # 只有一个不孤立建组，退回独立卡片
            assigned.remove(kps.index(matched_kps[0]))

    remaining_kps = [kp for i, kp in enumerate(kps) if i not in assigned]

    if groups:
        leaf_data["groups"] = groups
        leaf_data["remaining_kps"] = remaining_kps
        print(f"  小节 [{leaf_data.get('title')}]: 成功归纳 {len(groups)} 个大概念组，独立卡片 {len(remaining_kps)} 张")
    else:
        leaf_data.pop("groups", None)
        leaf_data.pop("remaining_kps", None)

    return leaf_data

# 执行处理
clustered_sec_count = 0
total_groups_created = 0

for f in glob.glob(os.path.join(LEAVES_DIR, "*.json")):
    d = json.load(open(f, encoding="utf-8"))
    orig_has_groups = "groups" in d
    d = cluster_leaf(d)
    if "groups" in d:
        clustered_sec_count += 1
        total_groups_created += len(d["groups"])
    with open(f, "w", encoding="utf-8") as out_fp:
        json.dump(d, out_fp, ensure_ascii=False, indent=2)

print(f"\n🎉 大概念归类重构完毕！")
print(f"- 成功归纳大概念的小节数: {clustered_sec_count}")
print(f"- 全书提炼生成【大概念】父节点总数: {total_groups_created} 个！")
