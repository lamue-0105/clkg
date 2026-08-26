# CL-Onto ↔ CIDOC-CRM 映射表

match: ✅exact 等价 · 🟢close 近义 · 🟡broad 上位/需建模 · ⚪none 项目扩展无直接对应
覆盖：✅3 🟢33 🟡20 ⚪37（共 93 项）


| CLKG 术语 | 种类 | CIDOC-CRM | match | 说明 |
|---|---|---|---|---|
| `clkg:Place` | Class | crm:E53_Place | 🟢 close | 地点 |
| `clkg:CulturalLandscapeUnit` | Class | crm:E27_Site | 🟢 close | 文化景观单元 |
| `clkg:Actor` | Class | crm:E39_Actor | 🟢 close | 行动者 |
| `clkg:Document` | Class | crm:E31_Document | 🟢 close | 文档 |
| `clkg:Event` | Class | crm:E5_Event | 🟢 close | 事件 |
| `clkg:DigitalImage` | Class | crm:E36_Visual_Item | 🟢 close | 图像 |
| `clkg:Evidence` | Class | prov:Entity | ✅ exact | PROV-O，非 CRM |
| `clkg:carriedOutBy` | ObjectProp | crm:P14_carried_out_by | ✅ exact |  |
| `clkg:containsPlace` | ObjectProp | crm:P89_falls_within | 🟢 close | 空间包含 |
| `clkg:hasDestinationPlace` | ObjectProp | crm:P26_moved_to | 🟡 broad | 寄达地(侨批) 若建模为 E9 Move |
| `clkg:hasOriginPlace` | ObjectProp | crm:P27_moved_from | 🟡 broad | 寄出地(侨批) 若建模为 E9 Move |
| `clkg:hasRecipient` | ObjectProp | — | ⚪ none | 收件人(侨批) 收件人；同上 |
| `clkg:hasSender` | ObjectProp | — | ⚪ none | 寄件人(侨批) 信件寄件人；CRM 需经 E7+P14 间接表达 |
| `clkg:locatedAt` | ObjectProp | crm:P168_place_is_defined_by | 🟢 close | → Geometry |
| `clkg:mentionsGroup` | ObjectProp | crm:P67_refers_to | 🟡 broad |  |
| `clkg:mentionsPlaceEntity` | ObjectProp | crm:P67_refers_to | 🟡 broad | 诗→提及地 |
| `clkg:tookPlaceIn` | ObjectProp | crm:P7_took_place_at | ✅ exact |  |
| `clkg:capturedAt` | DataProp | crm:P4_has_time-span | 🟡 broad | 拍摄时间 时间 → E52 |
| `clkg:hasAbstract` | DataProp | crm:P3_has_note / P190 | 🟢 close | 内容摘要 文本内容 |
| `clkg:hasAddress` | DataProp | crm:P87_is_identified_by | 🟡 broad | 地址 地名/地址 → E45/E48 |
| `clkg:hasAdminCode` | DataProp | crm:P1_is_identified_by | 🟢 close | → E42 Identifier |
| `clkg:hasAgent` | DataProp | — | ⚪ none | 行动主体 项目扩展，无直接 CRM |
| `clkg:hasAmount` | DataProp | — | ⚪ none | 金额(侨批) 项目扩展，无直接 CRM |
| `clkg:hasArea` | DataProp | — | ⚪ none | 项目扩展，无直接 CRM |
| `clkg:hasAuthor` | DataProp | crm:P14_carried_out_by | 🟡 broad | 作者创建者 创建活动 E65 |
| `clkg:hasBeneficiary` | DataProp | — | ⚪ none | 承受人 项目扩展，无直接 CRM |
| `clkg:hasCategoryType` | DataProp | crm:P2_has_type | 🟢 close | 遗产类别 → E55 Type |
| `clkg:hasChapter` | DataProp | — | ⚪ none | 章 项目扩展，无直接 CRM |
| `clkg:hasCollectionNumber` | DataProp | crm:P1_is_identified_by | 🟢 close | 馆藏号 → E42 Identifier |
| `clkg:hasConcept` | DataProp | crm:P3_has_note / P190 | 🟢 close | 概念 文本内容 |
| `clkg:hasConvertedAmount` | DataProp | — | ⚪ none | 折算(侨批) 项目扩展，无直接 CRM |
| `clkg:hasCountry` | DataProp | crm:P87_is_identified_by | 🟡 broad | 地名/地址 → E45/E48 |
| `clkg:hasCounty` | DataProp | crm:P87_is_identified_by | 🟡 broad | 县区 地名/地址 → E45/E48 |
| `clkg:hasCulturalValue` | DataProp | crm:P3_has_note / P190 | 🟢 close | 文化价值 文本内容 |
| `clkg:hasCurrency` | DataProp | — | ⚪ none | 币种(侨批) 项目扩展，无直接 CRM |
| `clkg:hasDescription` | DataProp | crm:P3_has_note / P190 | 🟢 close | 描述 文本内容 |
| `clkg:hasDistrict` | DataProp | crm:P87_is_identified_by | 🟡 broad | 地名/地址 → E45/E48 |
| `clkg:hasEmotion` | DataProp | — | ⚪ none | 情感极性 项目扩展，无直接 CRM |
| `clkg:hasEmotionScore` | DataProp | — | ⚪ none | 极性得分 项目扩展，无直接 CRM |
| `clkg:hasEmotionType` | DataProp | crm:P2_has_type | 🟢 close | 情绪类别 → E55 Type |
| `clkg:hasEnvironment` | DataProp | — | ⚪ none | 项目扩展，无直接 CRM |
| `clkg:hasEra` | DataProp | crm:P4_has_time-span | 🟡 broad | 年代 时间 → E52 |
| `clkg:hasEventType` | DataProp | crm:P2_has_type | 🟢 close | 事件类型 → E55 Type |
| `clkg:hasFileName` | DataProp | — | ⚪ none | 文件名 项目扩展，无直接 CRM |
| `clkg:hasFilePath` | DataProp | — | ⚪ none | 路径 项目扩展，无直接 CRM |
| `clkg:hasFileSize` | DataProp | — | ⚪ none | 项目扩展，无直接 CRM |
| `clkg:hasFileType` | DataProp | crm:P2_has_type | 🟢 close | 类型 → E55 Type |
| `clkg:hasFormalDate` | DataProp | crm:P4_has_time-span | 🟡 broad | 标准化日期 时间 → E52 |
| `clkg:hasFullText` | DataProp | crm:P3_has_note / P190 | 🟢 close | 全文转写 文本内容 |
| `clkg:hasGazettedBatch` | DataProp | crm:P1_is_identified_by | 🟢 close | → E42 Identifier |
| `clkg:hasGazettedDate` | DataProp | crm:P4_has_time-span | 🟡 broad | 时间 → E52 |
| `clkg:hasHeritageCode` | DataProp | crm:P1_is_identified_by | 🟢 close | → E42 Identifier |
| `clkg:hasHeritageLevel` | DataProp | — | ⚪ none | 保护级别 项目扩展，无直接 CRM |
| `clkg:hasIdentity` | DataProp | — | ⚪ none | 身份 项目扩展，无直接 CRM |
| `clkg:hasInitiator` | DataProp | — | ⚪ none | 发起人 项目扩展，无直接 CRM |
| `clkg:hasInstitution` | DataProp | — | ⚪ none | 屯垦制度 项目扩展，无直接 CRM |
| `clkg:hasInterviewer` | DataProp | — | ⚪ none | 采访人 项目扩展，无直接 CRM |
| `clkg:hasLayer` | DataProp | crm:P2_has_type | 🟢 close | 层级 → E55 Type |
| `clkg:hasName` | DataProp | crm:P1_is_identified_by | 🟢 close | 名称 → E41 Appellation |
| `clkg:hasNote` | DataProp | crm:P3_has_note / P190 | 🟢 close | 文本内容 |
| `clkg:hasNotes` | DataProp | crm:P3_has_note / P190 | 🟢 close | 备注 文本内容 |
| `clkg:hasObject` | DataProp | — | ⚪ none | 物 项目扩展，无直接 CRM |
| `clkg:hasObjectType` | DataProp | crm:P2_has_type | 🟢 close | → E55 Type |
| `clkg:hasPaidAmount` | DataProp | — | ⚪ none | 实付(侨批) 项目扩展，无直接 CRM |
| `clkg:hasParticipantName` | DataProp | — | ⚪ none | 人物 项目扩展，无直接 CRM |
| `clkg:hasPrefecture` | DataProp | crm:P87_is_identified_by | 🟡 broad | 省州 地名/地址 → E45/E48 |
| `clkg:hasPreservationState` | DataProp | — | ⚪ none | 项目扩展，无直接 CRM |
| `clkg:hasProfession` | DataProp | — | ⚪ none | 项目扩展，无直接 CRM |
| `clkg:hasProtectionFacility` | DataProp | — | ⚪ none | 项目扩展，无直接 CRM |
| `clkg:hasQualityFlag` | DataProp | — | ⚪ none | 项目扩展，无直接 CRM |
| `clkg:hasRecord` | DataProp | crm:P3_has_note / P190 | 🟢 close | 文本内容 |
| `clkg:hasRecorder` | DataProp | crm:P3_has_note / P190 | 🟢 close | 文本内容 |
| `clkg:hasReference` | DataProp | crm:P1_is_identified_by | 🟢 close | 著录参考 → E42 Identifier |
| `clkg:hasReplyDate` | DataProp | crm:P4_has_time-span | 🟡 broad | 回批日期(侨批) 时间 → E52 |
| `clkg:hasSection` | DataProp | — | ⚪ none | 节 项目扩展，无直接 CRM |
| `clkg:hasShapeArea` | DataProp | — | ⚪ none | 项目扩展，无直接 CRM |
| `clkg:hasShapeLength` | DataProp | — | ⚪ none | 项目扩展，无直接 CRM |
| `clkg:hasShownDate` | DataProp | crm:P4_has_time-span | 🟡 broad | 原件题署日期 时间 → E52 |
| `clkg:hasSignage` | DataProp | — | ⚪ none | 项目扩展，无直接 CRM |
| `clkg:hasSpeaker` | DataProp | — | ⚪ none | 口述者 项目扩展，无直接 CRM |
| `clkg:hasSpeakerRole` | DataProp | — | ⚪ none | 口述者身份 项目扩展，无直接 CRM |
| `clkg:hasSpecialUnit` | DataProp | — | ⚪ none | 项目扩展，无直接 CRM |
| `clkg:hasSubsection` | DataProp | — | ⚪ none | 小节 项目扩展，无直接 CRM |
| `clkg:hasSurveyDate` | DataProp | crm:P4_has_time-span | 🟡 broad | 调查日期 时间 → E52 |
| `clkg:hasSurveyHistory` | DataProp | crm:P3_has_note / P190 | 🟢 close | 文本内容 |
| `clkg:hasSurveyType` | DataProp | crm:P2_has_type | 🟢 close | → E55 Type |
| `clkg:hasTimeSpan` | DataProp | crm:P4_has_time-span | 🟡 broad | 时间 → E52 |
| `clkg:hasTitle` | DataProp | crm:P102_has_title | 🟢 close | 标题 → E35 Title |
| `clkg:hasTown` | DataProp | crm:P87_is_identified_by | 🟡 broad | 乡镇 地名/地址 → E45/E48 |
| `clkg:hasTrigger` | DataProp | — | ⚪ none | 触发词 项目扩展，无直接 CRM |
| `clkg:hasType` | DataProp | crm:P2_has_type | 🟢 close | 类型 → E55 Type |
| `clkg:hasVillage` | DataProp | crm:P87_is_identified_by | 🟡 broad | 村 地名/地址 → E45/E48 |
| `clkg:mentionsPlace` | DataProp | — | ⚪ none | 地名 项目扩展，无直接 CRM |