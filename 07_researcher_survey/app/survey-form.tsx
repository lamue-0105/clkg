"use client";

import { FormEvent, ReactNode, useMemo, useState } from "react";
import "./survey.css";

type Answers = Record<string, string | string[] | boolean | Record<string, string>>;

const heritageGroups = [
  {
    heading: "A. 世界文化遗产／不可移动文化遗产",
    options: [
      "纪念物与建筑遗产", "建筑群、历史城镇与历史环境", "考古遗址与考古场所", "文化场所／文化遗址",
      "文化景观：设计型", "文化景观：有机演进型", "文化景观：关联型", "文化路线／线性遗产",
    ],
  },
  {
    heading: "B. 可移动文化财产／馆藏",
    options: [
      "考古出土物、古物、钱币、印章、碑刻等", "艺术品、宗教器物或历史物件", "民族志、民俗或社区生活相关物件",
      "科学技术、工业或社会历史相关藏品", "馆藏集合、标本或专题收藏",
    ],
  },
  {
    heading: "C. 文献遗产／世界记忆相关对象",
    options: [
      "手稿、古籍、珍本、报刊或出版物", "档案、书信、账簿、登记册或机构记录", "历史地图、图纸、照片或印刷图像",
      "录音、电影、录像及其他视听文献", "数字出生文献、数字档案或数字化文献集合",
    ],
  },
  {
    heading: "D. 非物质文化遗产／活态遗产",
    options: [
      "口头传统与表现形式，包括语言", "表演艺术", "社会实践、仪式与节庆活动",
      "有关自然界和宇宙的知识与实践", "传统手工艺技能",
    ],
  },
];

const difficulties = [
  "找到和定位原始材料", "清洗、转录或转换资料格式", "判断不同资料是否指向同一对象",
  "处理地名、地点、坐标或空间范围", "处理年代、时期或模糊时间表达", "保留材料来源与研究判断之间的关系",
  "处理互相矛盾或不确定的信息", "多人协作、版本管理或修改追踪", "将资料转化为可引用的研究成果",
];

const evidenceItems = [
  "原始材料来源、编号或引用信息", "数据采集、整理或修改的人员与时间", "数据处理、转换或判断的过程",
  "时间和空间信息的精度或不确定性", "不同解释、冲突记录或备选判断", "版权、授权与公开范围",
  "地图、统计或网络分析结果的生成方法",
];

const currentShortcomings = [
  "原始材料分散在个人电脑、纸质档案、云盘或不同机构，难以统一查找",
  "缺少稳定编号，难以识别同一地点、人物、事件或遗产对象",
  "不同来源的名称、时间、地点或分类标准不一致",
  "原始材料、整理数据与最终研究结论之间难以追溯",
  "无法方便记录不确定性、冲突信息或多个解释",
  "地名、历史时期、坐标、空间范围等时空信息难以统一处理",
  "多人协作时缺少版本、修改记录与审核过程",
  "图片、音频、文本、表格、GIS 等多模态材料难以关联",
  "数据版权、授权、隐私或敏感信息的管理不清晰",
  "地图、统计、网络分析等派生结果难以复现或说明生成过程",
  "数据难以共享、引用、迁移或被后续研究复用",
  "现有方式已基本满足需要",
];

function toggle(values: string[], value: string) {
  return values.includes(value) ? values.filter((item) => item !== value) : [...values, value];
}

function OtherNote({ active, value, onChange }: { active: boolean; value: string; onChange: (value: string) => void }) {
  if (!active) return null;
  return <textarea className="other-note" value={value} onChange={(event) => onChange(event.target.value)} maxLength={200} placeholder="请用一句话补充说明。" aria-label="其他补充说明" />;
}

function CheckboxGroup({ name, options, values, onChange, limit, otherValue, onOtherChange }: {
  name: string; options: string[]; values: string[]; onChange: (values: string[]) => void; limit?: number; otherValue?: string; onOtherChange?: (value: string) => void;
}) {
  return <><div className="check-grid">{options.map((option) => {
    const checked = values.includes(option);
    const disabled = !checked && limit !== undefined && values.length >= limit;
    return <label className={`check-card ${checked ? "selected" : ""}`} key={option}>
      <input type="checkbox" name={name} checked={checked} disabled={disabled} onChange={() => onChange(toggle(values, option))} />
      <span>{option}</span>
    </label>;
  })}</div><OtherNote active={values.includes("其他")} value={otherValue ?? ""} onChange={onOtherChange ?? (() => {})} /></>;
}

function SingleChoice({ name, options, value, onChange, otherValue, onOtherChange }: { name: string; options: string[]; value: string; onChange: (value: string) => void; otherValue?: string; onOtherChange?: (value: string) => void }) {
  return <><div className="choice-stack">{options.map((option) => <label key={option} className="radio-line">
    <input type="radio" name={name} value={option} checked={value === option} onChange={() => onChange(option)} /> <span>{option}</span>
  </label>)}</div><OtherNote active={value === "其他"} value={otherValue ?? ""} onChange={onOtherChange ?? (() => {})} /></>;
}

function RatingTable({ rows, value, onChange, labels, includeNotApplicable = true }: { rows: string[]; value: Record<string, string>; onChange: (next: Record<string, string>) => void; labels: string[]; includeNotApplicable?: boolean }) {
  return <div className="rating-table" role="group"><div className="rating-scale" aria-hidden="true"><span>{labels[0]}</span><i>1</i><i>2</i><i>3</i><i>4</i><i>5</i><span>{labels[4]}</span></div>{rows.map((row) => <fieldset key={row}>
    <legend>{row}</legend>
    <div>{labels.map((label, index) => <label key={label} title={label}>
      <input type="radio" name={row} checked={value[row] === String(index + 1)} onChange={() => onChange({ ...value, [row]: String(index + 1) })} />
      <span>{index + 1}</span>
    </label>)}{includeNotApplicable && <label className="na"><input type="radio" name={row} checked={value[row] === "NA"} onChange={() => onChange({ ...value, [row]: "NA" })} /><span>不适用</span></label>}</div>
  </fieldset>)}</div>;
}

function Question({ number, title, hint, children }: { number: string; title: string; hint?: string; children: ReactNode }) {
  return <section className="question"><div className="question-title"><span>{number}</span><h2>{title}</h2></div>{hint && <p className="hint">{hint}</p>}{children}</section>;
}

export function SurveyForm() {
  const [step, setStep] = useState(0);
  const [answers, setAnswers] = useState<Answers>({ consent: false, role: [], stage: "", researchQuestion: "", reworkStage: "", heritage: [], outputs: [], modalities: [], sources: [], workflow: [], tools: [], priorities: [], problems: [], uncertainty: [], approvals: [], risks: [], capabilities: [], acceptance: [], shortcomings: [], difficulty: {}, evidenceImportance: {}, responsibilities: {} });
  const [other, setOther] = useState<Record<string, string>>({});
  const [status, setStatus] = useState<"idle" | "sending" | "success" | "error">("idle");
  const [message, setMessage] = useState("");
  const steps = ["研究任务", "材料与流程", "困难与证据", "治理与成果"];
  const getList = (key: string) => (answers[key] as string[]) ?? [];
  const getText = (key: string) => (answers[key] as string) ?? "";
  const getRecord = (key: string) => (answers[key] as Record<string, string>) ?? {};
  const update = (key: string, value: Answers[string]) => setAnswers((current) => ({ ...current, [key]: value }));
  const updateOther = (key: string, value: string) => setOther((current) => ({ ...current, [key]: value }));
  const requiredReady = Boolean(answers.consent && getList("role").length && answers.stage && getList("heritage").length && getText("researchQuestion"));
  const percent = useMemo(() => Math.round(((step + 1) / steps.length) * 100), [step]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!requiredReady) { setStatus("error"); setMessage("请完成带 * 的必答内容，并确认知情同意。 "); return; }
    setStatus("sending"); setMessage("");
    try {
      const response = await fetch("/api/responses", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ answers: { ...answers, other, submittedAtClient: new Date().toISOString() }, honeypot: "" }) });
      const result = await response.json() as { error?: string };
      if (!response.ok) throw new Error(result.error ?? "提交失败，请稍后再试。");
      setStatus("success"); setMessage("感谢您的参与。您的匿名答卷已成功提交。 ");
    } catch (error) {
      setStatus("error"); setMessage(error instanceof Error ? error.message : "提交失败，请稍后再试。");
    }
  }

  if (status === "success") return <main className="survey-shell"><div className="success-card"><span className="eyebrow">CLKG · 调研完成</span><h1>感谢您的参与</h1><p>{message}</p><p>您的回答将用于理解跨类型文化遗产研究中的数据组织需求，并支持后续研究设计。</p></div></main>;

  return <main className="survey-shell"><header className="hero"><img className="cover-image" src="/clkg-heritage-cover.png" alt="考古遗址、历史建筑、文化景观、文献、馆藏与口述资料相互关联的插画" /><span className="eyebrow">CLKG · 研究者需求调研</span><h1>文化遗产跨类型数据组织与研究需求调查</h1><p>请以近两年一项真实的文化遗产研究任务为例作答。全程约 12–15 分钟，不收集姓名、联系方式或原始敏感材料。</p><div className="ethics"><strong>填写前请知悉：</strong>参与完全自愿；请勿在开放题中填写个人信息、精确脆弱遗址坐标或受限制的社区知识。</div></header>
    <form className="survey-card" onSubmit={submit}>
      <nav aria-label="问卷进度"><div className="progress-label"><span>第 {step + 1} / {steps.length} 步</span><strong>{steps[step]}</strong></div><div className="progress-track"><i style={{ width: `${percent}%` }} /></div></nav>
      {step === 0 && <>
        <Question number="Q0" title="知情同意" hint="* 必答"><label className="consent"><input type="checkbox" checked={answers.consent === true} onChange={(event) => update("consent", event.target.checked)} />我已了解本调查用于学术研究与需求分析，并同意匿名参与。</label></Question>
        <Question number="Q1" title="您在该研究任务中的主要角色是？" hint="* 必答；可多选"><CheckboxGroup name="role" values={getList("role")} onChange={(value) => update("role", value)} otherValue={other.role} onOtherChange={(value) => updateOther("role", value)} options={["项目负责人／课题主持人", "文化遗产领域研究者", "田野调查或资料采集人员", "档案、文献或馆藏管理人员", "GIS／空间分析人员", "数据整理、数字人文或技术支持人员", "研究生", "其他"]} /></Question>
        <Question number="Q2" title="这项任务目前处于什么阶段？" hint="* 必答"><SingleChoice name="stage" value={getText("stage")} onChange={(value) => update("stage", value)} otherValue={other.stage} onOtherChange={(value) => updateOther("stage", value)} options={["材料收集阶段", "整理、转录或数据清洗阶段", "分析与解释阶段", "论文、报告或成果制作阶段", "已完成，正在保存、共享或复用成果", "其他"]} /></Question>
        <Question number="Q3" title="该任务涉及哪些文化遗产类型？" hint="* 可多选；跨类别请选择全部相关项">{heritageGroups.map((group) => <div className="heritage-group" key={group.heading}><h3>{group.heading}</h3><CheckboxGroup name="heritage" options={group.options} values={getList("heritage")} onChange={(value) => update("heritage", value)} /></div>)}</Question>
        <Question number="Q4" title="这项任务最主要希望形成什么成果？" hint="最多选 3 项"><CheckboxGroup name="outputs" limit={3} values={getList("outputs")} onChange={(value) => update("outputs", value)} otherValue={other.outputs} onOtherChange={(value) => updateOther("outputs", value)} options={["学术论文、专著或研究报告", "可引用的数据集或数字档案", "地图、空间分布图、路线图或时序图", "人物、事件、地点或对象关系分析", "遗产保护、监测或管理建议", "展示、教育或公众传播成果", "后续研究可复用的资料基础", "其他"]} /></Question>
        <Question number="Q5" title="该任务要解决的核心问题属于哪一类？" hint="* 必答"><SingleChoice name="researchQuestion" value={getText("researchQuestion")} onChange={(value) => update("researchQuestion", value)} otherValue={other.researchQuestion} onOtherChange={(value) => updateOther("researchQuestion", value)} options={["整合、补充或规范某类遗产资料", "识别不同材料中指向同一人、地、物、事件或文献的记录", "追踪遗产对象、人员、物资、知识或实践的时空变化与流动", "解释不同材料之间的关联、历史脉络或文化意义", "整合文本、图像、音频、表格、GIS 等多模态材料", "构建可追溯、可引用、可复用的研究数据集或数字档案", "为遗产保护、监测、管理、展示或教育提供依据", "其他"]} /></Question>
      </>}
      {step === 1 && <>
        <Question number="Q6" title="您实际使用过哪些材料或数据？" hint="可多选"><CheckboxGroup name="modalities" values={getList("modalities")} onChange={(value) => update("modalities", value)} otherValue={other.modalities} onOtherChange={(value) => updateOther("modalities", value)} options={["文献、档案、目录或登记资料", "表格或数据库记录", "历史地图、现代地图或 GIS 图层", "遥感、航拍、测绘或定位数据", "图片、视频或数字影像", "录音、口述史或访谈材料", "转录文本、笔记或田野日志", "三维模型、点云或模型成果", "实物、馆藏或现场观察记录", "其他"]} /></Question>
        <Question number="Q7" title="这些材料主要来自哪里？" hint="可多选"><CheckboxGroup name="sources" values={getList("sources")} onChange={(value) => update("sources", value)} otherValue={other.sources} onOtherChange={(value) => updateOther("sources", value)} options={["个人田野调查或项目自采", "档案馆、图书馆、博物馆或研究机构", "政府部门或公共数据平台", "社区成员、传承人或受访者", "既有论文、专著或研究成果", "网络公开资源", "合作单位或其他研究团队", "其他"]} /></Question>
        <Question number="Q8" title="您是否需要关联多个来源或多种模态的材料？"><SingleChoice name="crossLink" value={getText("crossLink")} onChange={(value) => update("crossLink", value)} options={["必须关联，且关联是研究核心", "需要关联，但不是核心", "偶尔需要", "基本不需要", "不确定"]} /></Question>
        <Question number="Q9" title="从获取原始材料到形成研究成果，您实际经历过哪些步骤？" hint="可多选"><CheckboxGroup name="workflow" values={getList("workflow")} onChange={(value) => update("workflow", value)} options={["登记材料来源、编号或采集背景", "扫描、转录、数字化或格式转换", "清洗、去重、补全或规范字段", "将不同材料中的同一对象进行识别或合并", "确定地名、地点、坐标或空间范围", "确定年代、时期或时间范围", "关联人物、事件、地点、文献或实物", "与专家、社区成员或合作方核对", "制图、统计、网络分析或可视化", "撰写论文、报告或解释性文本", "数据归档、共享或发布"]} /></Question>
        <Question number="Q10" title="哪一个环节最容易反复修改？" hint="请选择最主要的一项"><SingleChoice name="reworkStage" value={getText("reworkStage")} onChange={(value) => update("reworkStage", value)} otherValue={other.reworkStage} onOtherChange={(value) => updateOther("reworkStage", value)} options={["来源、编号或采集背景登记", "扫描、转录、数字化或格式转换", "清洗、去重、补全或字段规范化", "跨来源识别或合并同一对象", "地名、地点、坐标或空间范围判断", "年代、时期或时间范围判断", "关联人物、事件、地点、文献或实物", "证据溯源、冲突或不确定性处理", "制图、统计、网络分析或可视化", "协作、版本管理或审核", "数据归档、共享或发布", "其他"]} /></Question>
        <Question number="Q11" title="您主要依靠哪些工具或方式组织资料？" hint="可多选"><CheckboxGroup name="tools" values={getList("tools")} onChange={(value) => update("tools", value)} otherValue={other.tools} onOtherChange={(value) => updateOther("tools", value)} options={["Excel、WPS 表格或个人文件夹", "GIS 软件", "文献管理软件", "数据库", "云盘、协作平台或项目共享文件夹", "手工笔记、纸质档案或人工目录", "自行编写脚本或程序", "专门的遗产、档案或馆藏管理系统", "其他"]} /></Question>
      </>}
      {step === 2 && <>
        <Question number="Q12" title="请评价下列环节的困难程度。" hint="1 几乎无困难 · 5 非常困难"><RatingTable rows={difficulties} value={getRecord("difficulty")} onChange={(value) => update("difficulty", value)} labels={["几乎无困难", "较小困难", "一般", "较大困难", "非常困难"]} /></Question>
        <Question number="Q13" title="您最希望优先改善哪三项？" hint="最多选 3 项"><CheckboxGroup name="priorities" limit={3} values={getList("priorities")} onChange={(value) => update("priorities", value)} options={difficulties} /></Question>
        <Question number="Q14" title="您遇到过哪些资料关联或质量问题？" hint="可多选"><CheckboxGroup name="problems" values={getList("problems")} onChange={(value) => update("problems", value)} options={["同一对象在不同材料中名称不同", "同一地名对应多个地点，或历史地名无法准确定位", "时间只能判断到朝代、世纪或大致时期", "多条材料之间存在矛盾", "原始材料与整理后的数据难以对应", "分析图、统计结果无法追溯到原始材料", "资料散落在个人电脑、聊天记录或不同机构", "没有明确的数据管理或更新责任人", "未遇到上述情况"]} /></Question>
        <Question number="Q15" title="以下信息在研究数据组织中有多重要？" hint="完全不重要 1 2 3 4 5 非常重要"><RatingTable rows={evidenceItems} value={getRecord("evidenceImportance")} onChange={(value) => update("evidenceImportance", value)} labels={["完全不重要", "较不重要", "一般", "较重要", "非常重要"]} includeNotApplicable={false} /></Question>
        <Question number="Q16" title="材料存在矛盾、不完整或不确定时，您通常如何处理？" hint="可多选"><CheckboxGroup name="uncertainty" values={getList("uncertainty")} onChange={(value) => update("uncertainty", value)} otherValue={other.uncertainty} onOtherChange={(value) => updateOther("uncertainty", value)} options={["保留多种说法及其来源", "选择最可信的一种说法", "暂不纳入分析", "请领域专家确认", "请资料提供者、社区成员或传承人确认", "在论文或报告中说明不确定性", "没有稳定处理方式", "其他"]} /></Question>
      </>}
      {step === 3 && <>
        <Question number="Q17" title="哪些判断必须由研究者或领域专家最终确认？" hint="可多选"><CheckboxGroup name="approvals" values={getList("approvals")} onChange={(value) => update("approvals", value)} otherValue={other.approvals} onOtherChange={(value) => updateOther("approvals", value)} options={["对象身份或类别判断", "历史地名、现代地名或地点对应", "年代、时期或时间范围判断", "空间范围、边界或坐标选择", "材料可信度与证据权重", "不同材料冲突的解释", "口述史、社区材料的使用与公开范围", "研究结论是否可以发表或发布", "其他"]} /></Question>
        <Question number="Q18" title="该任务涉及哪些数据使用风险或限制？" hint="可多选"><CheckboxGroup name="risks" values={getList("risks")} onChange={(value) => update("risks", value)} otherValue={other.risks} onOtherChange={(value) => updateOther("risks", value)} options={["档案、图片、地图或馆藏版权", "口述史知情同意或隐私保护", "社区知识、传统知识或敏感叙事", "遗址、墓葬或脆弱遗产的精确位置", "数据共享权限或机构管理要求", "跨境数据、民族宗教或政治敏感性", "无明显限制", "不确定", "其他"]} /></Question>
        <Question number="Q19" title="如果有一个研究数据组织平台，哪些能力对您的任务最有价值？" hint="最多选 3 项"><CheckboxGroup name="capabilities" limit={3} values={getList("capabilities")} onChange={(value) => update("capabilities", value)} otherValue={other.capabilities} onOtherChange={(value) => updateOther("capabilities", value)} options={["跨材料识别同一地点、人物、事件或遗产对象", "保存原始材料与研究结论之间的证据链", "管理历史地名、模糊时间和不确定信息", "整合 GIS、表格、文献、影像、音频等多模态材料", "支持资料的版本、修改记录和协作审核", "控制不同资料的查看、使用和公开权限", "生成可追溯的地图、统计或关系分析结果", "形成可引用、可共享、可复用的数据集", "其他"]} /></Question>
        <Question number="Q20" title="什么条件下，一条整理后的研究数据可以进入论文、报告或正式成果？" hint="可多选"><CheckboxGroup name="acceptance" values={getList("acceptance")} onChange={(value) => update("acceptance", value)} otherValue={other.acceptance} onOtherChange={(value) => updateOther("acceptance", value)} options={["有明确的原始来源或引用信息", "经过领域专家核对", "有清晰的时间、地点或对象说明", "不确定性和限制条件已被标注", "数据处理过程可说明或可复查", "获得资料提供方或机构授权", "与其他材料交叉验证", "其他"]} /></Question>
        <Question number="Q21" title="谁最适合承担资料质量与公开决策责任？"><SingleChoice name="owner" value={getText("owner")} onChange={(value) => update("owner", value)} options={["研究者", "领域专家", "资料机构人员", "数据管理员或技术人员", "社区或资料提供者", "共同承担", "不确定"]} /></Question>
        <Question number="Q22" title="您认为现有资料组织方式的主要不足是什么？" hint="最多选 3 项；随后可补充具体案例"><CheckboxGroup name="shortcomings" limit={3} values={getList("shortcomings")} onChange={(value) => update("shortcomings", value)} options={currentShortcomings} /><textarea value={getText("shortcomingCase")} onChange={(event) => update("shortcomingCase", event.target.value)} maxLength={1000} placeholder="可选：请描述一个具体案例及其对研究造成的影响（100–200 字即可）。" /></Question>
      </>}
      <div className="form-actions"><button type="button" className="secondary" onClick={() => setStep((current) => Math.max(0, current - 1))} disabled={step === 0}>上一步</button>{step < steps.length - 1 ? <button type="button" onClick={() => setStep((current) => Math.min(steps.length - 1, current + 1))}>下一步</button> : <button type="submit" disabled={status === "sending"}>{status === "sending" ? "正在提交…" : "提交匿名答卷"}</button>}</div>
      {status === "error" && <p className="message error" role="alert">{message}</p>}
    </form>
    <footer>CLKG 文化遗产跨类型数据组织与研究需求调查 · 本问卷不用于评价个人或机构。</footer>
  </main>;
}
