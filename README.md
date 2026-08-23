# Google Play 应用评论洞察 Agent

这是一个面向通用 Google Play 应用的用户评论分析 Agent。

输入一个 Google Play 应用包名，项目可以抓取或读取评论，自动发现用户主要问题，检索原始评论证据，并生成产品、运营或客服改进建议。

Deliveroo 法国区评论只是默认演示数据，不是项目的使用范围。通过更换 Google Play 包名，可以分析不同类别的应用。

## 项目亮点

- 支持配置 Google Play 包名、国家、评论语言和评论数量；
- 支持通过 LLM Tool Calling 查询统计、搜索评论、按评分筛选和按时间筛选；
- 不预设某个行业的固定类别，由 Agent 自动发现用户主题；
- 使用透明的主题优先级公式：

  ```text
  优先级 = 50% 主题占比 + 30% 问题严重度 + 20% 近期性
  ```

- 每个核心结论都保留原始评论 ID 和评论文本作为证据；
- 支持中文和英文报告；
- 没有 API Key 时，可以使用离线 Demo 模式；
- 使用 Deliveroo、金融、社交和教育四类样本进行评估。

## 本地运行

建议使用 Python 3.10 或更高版本创建新的虚拟环境。原项目中的 `venv` 已移除，不需要恢复。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

启动后，应用默认加载 `data/samples/deliveroo_reviews_fr.csv`。

在侧边栏可以选择：

- 使用缓存/演示数据；
- 根据 Google Play 包名抓取新评论；
- 上传自己的 CSV 文件。

如果没有配置 LLM API Key，应用会自动使用离线 Demo 模式，仍然可以展示主题发现、证据和报告导出功能。

## 配置 LLM

复制 `.env.example` 为 `.env`，填写以下配置中的任意一个 Key：

```text
LLM_API_KEY=你的_API_Key
OPENAI_API_KEY=你的_API_Key
LLM_MODEL=gpt-4o-mini
LLM_BASE_URL=
```

`LLM_BASE_URL` 可选，用于兼容 OpenAI 接口格式的其他模型服务。

不要把 `.env`、API Key 或账号信息提交到 GitHub。项目的 `.gitignore` 已经排除 `.env`。

## 命令行抓取评论

```powershell
python main.py --app-id com.example.app --country us --language en --count 500 --output data/cache/example.csv
```

参数说明：

- `--app-id`：Google Play 应用包名；
- `--country`：国家或地区代码；
- `--language`：评论语言代码；
- `--count`：抓取评论数量；
- `--sort`：`newest` 或 `relevant`；
- `--start-date`、`--end-date`：可选的日期范围。

Google Play 可能因为网络环境或访问频率限制而抓取失败。此时可以使用缓存数据或直接上传 CSV。

## 如何向他人演示

### 方式一：无 API Key 的稳定 Demo

这是最适合面试或现场展示的方式，不依赖模型账户和 Google Play 实时网络。

1. 按照上面的安装步骤启动应用：

   ```powershell
   streamlit run app.py
   ```

2. 在左侧选择 `Cached/demo`；
3. 保持默认的 Deliveroo 示例数据；
4. 将报告语言切换为中文；
5. 点击 `Analyze reviews`；
6. 展示总体评分、优先级主题、原始评论证据、事实/推断区分和报告下载。

可以直接使用这个问题：

```text
请找出该应用最重要的用户问题，按优先级排序，并为每个问题引用原始评论证据。
```

这种模式使用本地离线主题发现逻辑，优点是稳定、可重复；界面会明确显示 `Demo mode`，不要把它描述成真实的云端 LLM 调用。

### 方式二：真实 LLM Agent 演示

如果希望展示 Tool Calling：

1. 在 `.env` 中配置 `LLM_API_KEY` 或 `OPENAI_API_KEY`；
2. 可选配置 `LLM_MODEL`，例如 `gpt-5-mini`；
3. 重新启动 Streamlit；
4. 使用缓存评论或上传 CSV，避免现场等待 Google Play 抓取；
5. 点击 `Analyze reviews`；
6. 展开 `Agent tool trace`，展示 Agent 调用了哪些工具；
7. 展示每个主题对应的真实评论 ID、原文和产品建议。

演示时可以追问：

```text
哪些问题最严重？请分别说明数据事实、你的推断和建议，并引用评论原文。
```

### 推荐的 3 分钟讲解顺序

1. 先说明业务问题：用户评论很多，人工难以快速发现重复痛点；
2. 输入一个 App 评论数据集；
3. 让 Agent 自动发现主题，而不是使用 Deliveroo 专属分类；
4. 展示主题优先级公式和真实证据；
5. 展示 Tool Calling 轨迹；
6. 最后下载结构化报告，并说明当前限制是评论只来自 Google Play。

现场演示建议优先使用缓存数据。Google Play 实时抓取可能受到网络、地区或访问频率限制，不适合作为唯一演示路径。

## CSV 格式

标准字段如下：

```text
review_id,app_id,score,content,review_date,country,language
```

最少需要包含：

- `score` 或 `rating`；
- `content` 或 `review`。

如果没有 `review_id`，程序会根据应用、评分、日期和评论内容自动生成稳定 ID。

## 评估和测试

运行核心测试：

```powershell
python -m unittest discover -s tests -v
```

运行离线评估：

```powershell
python eval/run_evaluation.py
```

当前评估包含：

- 4 个不同数据集；
- 50 条带主题标签的评论；
- 10 个标准分析问题；
- JSON 结构校验；
- 证据引用一致性；
- 主题覆盖率。

## 旧版关键词 Baseline

原先的法语关键词分类逻辑已经移到 `legacy/analysis.py`，只用于和 Agent 结果进行对比，不属于主产品流程。

```powershell
python legacy/analysis.py --csv data/samples/deliveroo_reviews_fr.csv
```

## 项目结构

```text
app.py                 Streamlit 界面
main.py                Google Play 评论抓取命令
legacy/analysis.py     旧版关键词 Baseline
src/data.py            CSV 清洗、标准化和数据统计
src/tools.py           Agent 工具定义和执行
src/agent.py           Tool Calling 循环和证据校验
src/heuristic.py       离线 Demo 和透明评分逻辑
src/collector.py       Google Play 抓取接口
src/reporting.py       JSON 和 Markdown 报告导出
data/samples/          四个缓存 App 样本
eval/                  评估脚本、标签和标准问题
tests/                 核心测试
archive/               本地旧研究资料，已被 Git 忽略
```
