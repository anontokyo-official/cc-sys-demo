# M0：阿里云 + Nginx + 博客 + CourseBot API 初版

## 有困难先找AI

AI Studio（免费Gemini 3.x Pro）：https://aistudio.google.com/prompts/new_chat

ChatGPT（已可用免费Codex）：https://chatgpt.com/

Gemini Business（免费大额度Gemini 3.x Pro，只需邮箱即可薅，有手就行）：https://business.gemini.google/

要点：问AI的时候包括完整上下文、报错等，若有截图尽量完整提供，不明之处继续追问。

用法举例：

- 问「怎么配置阿里云安全组放行所有端口」
- 问「Windows下如何使用ssh，常用命令是什么」
- 贴nginx配置文件、完整错误截图等，问「为什么反代/blog博客无法访问，XXX（具体问题）」
- **贴本文档全部内容，问「我完全是电脑小白，教我一步步完成这个作业」**
- **贴本文档全部内容，然后再单独贴其中某一句话，问「这句话啥意思」**

## 开通阿里云

### 领取高校学生权益

访问 [阿里云高校计划](https://university.aliyun.com/) ，按照页面指引登录并完成学生认证，领取高校学生通用权益（300元抵扣金）。

![](https://public.ptree.top/picgo/2026/03/1772415980/PixPin_2026-03-02_09-44-18.jpg)

### 购买云服务器

在上述页面中点击购买 ECS-e 实例（处理器与内存比 1:1），如图所示：

![](https://public.ptree.top/picgo/2026/03/1772416039/PixPin_2026-03-02_09-47-16.jpg)

配置如下：

- 交换机选择默认

- **操作系统选择 Ubuntu 22.04**（如果你更熟悉其他 Ubuntu 版本或 CentOS 等其他 Linux 发行版，可以自由选择）

- **勾选【分配公网 IPv4 地址】**，其他配置默认

- 完成密码配置后，点击【确认下单】

访问 [云服务器管理控制台](https://ecs.console.aliyun.com/home#/) ，查看购买的云服务器实例，查看云服务器的公网 IP

![](https://public.ptree.top/picgo/2026/03/1772416073/PixPin_2026-03-02_09-47-51.jpg)

登录云服务器。有多种方式登录到云服务器，你可以选择任意一种你喜欢的，只要能成功登录即可。以下是两种推荐的方式：

1. **使用 VS Code 的 Remote - SSH 插件**。阅读[相关资料](https://cloud.tencent.com/developer/article/2175073)进行操作。

2. **使用 SSH 命令。**自行查找相关资料，安装 SSH，并在 Terminal（如 Windows Powershell 等）中执行命令 `ssh root@公网IP` ，输入密码，出现以下界面即登录成功。

   ![](https://public.ptree.top/picgo/2026/03/1772416120/PixPin_2026-03-02_09-48-34.jpg)

   你还应该会看到类似下图的命令行提示符：

   ![](https://public.ptree.top/picgo/2026/03/1772416130/PixPin_2026-03-02_09-48-48.jpg)
   
3. 其他工具：如XShell、electerm等均可，自行探索。

---

**注意：虽然服务器产生的费用都由抵扣金抵扣，但为了节省费用，不使用服务器时可以选择【节省停机模式】暂时停机，使用时再启动，如图所示：**

![](https://public.ptree.top/picgo/2026/03/1772416150/PixPin_2026-03-02_09-49-08.jpg)

---

## 部署Nginx

### 安装 Nginx，查看服务状态

云服务器可以用来做许多好玩的事情。在云服务器部署自己的博客是最常见的应用方式。在本次作业中，我们将通过 Nginx 部署一个 HTML 页面，然后通过浏览器访问它。

登录到云服务器后，执行以下命令：

```bash
sudo apt update # 更新软件包列表（由于我们以root账户登录，sudo其实是不必要的）
sudo apt install -y nginx # 安装 nginx
```

安装完毕后，执行以下命令查看 Nginx 服务的运行状态：

```bash
systemctl status nginx
```

![](https://public.ptree.top/picgo/2026/03/1772416176/PixPin_2026-03-02_09-49-34.jpg)

可以看到服务处于 `active(running)` 状态，表示 Nginx 已经启动成功并正常运行在云服务器的 80 端口上。

此时我们可以在云服务器内部访问 80 端口处的页面：

```bash
curl localhost:80
```

![](https://public.ptree.top/picgo/2026/03/1772416200/PixPin_2026-03-02_09-49-58.jpg)

理论上，我们使用在自己电脑上的浏览器访问云服务器的公网IP（即 http://<你的服务器公网IP>），也显示与上图 HTML 文本相同的内容。

但经过测试发现，我们还不能打开页面。这是因为阿里云服务器对入方向（外界访问云服务器）的端口有严格的管理，默认情况下只开启了少量的端口，其中并不包括我们要使用的 80 端口。接下来我们还需要在云服务器控制台配置安全组规则，开启 80 端口。

### 配置安全组规则，开启 80 端口

阅读 [阿里云文档](https://help.aliyun.com/zh/ecs/user-guide/add-a-security-group-rule) ，按照其中的教程打开安全组页面，在【入方向】添加并保存规则，如下图所示：

![](https://public.ptree.top/picgo/2026/03/1772416220/PixPin_2026-03-02_09-50-19.jpg)

### 通过浏览器访问云服务器上的网页

规则添加完毕后，再次通过浏览器访问 http://<你的服务器公网IP>，如果一切顺利，应出现Nginx默认欢迎页。

![](https://public.ptree.top/picgo/2026/03/1772416239/PixPin_2026-03-02_09-50-37.jpg)

## CourseBot API 初版

根据课程实验大纲 M0，本次实验除云主机与博客外，还需要完成一个最小可用的 LLM API 服务（CourseBot 初版）。

### 参考目录结构（M0 版本）

```text
coursebot/
  apps/
    gateway/              # FastAPI 对外 API
  services/
    llm-adapter/          # 统一模型接口
  packages/
    common/               # 配置、日志、错误码、工具函数（可选）
  scripts/
    demo.sh               # 演示脚本（可选）
  README.md
```

### 实现要求

1. 创建 `apps/gateway`（推荐python+FastAPI，你用别的语言实现也行），至少实现 3 个接口：
   - `POST /v1/chat/completions`（要真能聊天，目前先接入openrouter）
   - `GET /healthz`
   - `GET /readyz`
   
2. 创建 `services/llm-adapter`，定义统一 Provider 接口，并实现：
   - `FakeProvider`（用于本地/测试环境：不调用任何外部模型接口，需严格实现统一 Provider 接口，并可通过配置与 `SaaSProvider` 无缝切换；可返回固定或可预测结果，用于验证你的抽象/解耦是否成立）
   - `SaaSProvider`（目前固定使用openrouter，可优先选择免费模型）
   
3. `POST /v1/chat/completions` 的响应中必须包含 `usage` 字段，至少包括：
   
   - `prompt_tokens`
   - `completion_tokens`
   - `latency_ms`
   
   **具体可参考OpenAI官方文档，或直接问AI「openai格式接口的/v1/chat/completions请求，response长什么样，usage中prompt_tokens、completion_tokens、latency_ms这三个东西放在哪，举例说明」**
   
   可以直接vibe coding（codex现在已经免费用了），不需要你写一行代码
   
   https://github.com/tukuaiai/vibe-coding-cn 这个也看看

### 演示方式

- 通过 `curl` 演示一次 `POST /v1/chat/completions` 调用并展示返回的 `usage`
  - 这个接口请求和响应体是啥，请自行问AI或看openai官方文档

- 演示 `GET /healthz` 与 `GET /readyz` 均可用（200）

### 关于openrouter

提供众多厂商模型中转，不乏许多免费模型。

提供的是标准的openai格式。

在这注册账号：https://openrouter.ai/

然后：https://openrouter.ai/settings/privacy

![PixPin_2026-03-02_10-28-15](https://public.ptree.top/picgo/2026/03/1772418498/PixPin_2026-03-02_10-28-15.jpg)

这个打开，不然用不了免费模型。

去这里找免费模型：https://openrouter.ai/models?fmt=cards&input_modalities=text&order=pricing-low-to-high

比如：https://openrouter.ai/openai/gpt-oss-20b:free

模型id：openai/gpt-oss-20b:free

设置里创建api key：https://openrouter.ai/settings/keys

![PixPin_2026-03-02_10-32-14](https://public.ptree.top/picgo/2026/03/1772418760/PixPin_2026-03-02_10-32-14.jpg)

接入Cherry Studio先试试（没有的话下个，这个客户端很好用）：

![PixPin_2026-03-02_10-29-49](https://public.ptree.top/picgo/2026/03/1772418601/PixPin_2026-03-02_10-29-49.jpg)

![PixPin_2026-03-02_10-29-57](https://public.ptree.top/picgo/2026/03/1772418607/PixPin_2026-03-02_10-29-57.jpg)

![PixPin_2026-03-02_10-31-23](https://public.ptree.top/picgo/2026/03/1772418685/PixPin_2026-03-02_10-31-23.jpg)

OK接口可用，之后由你自己写代码了。

## 作业要求

**任务一（30 分）：**

在完成以上步骤的基础上，将Nginx默认欢迎页**替换为你自己的页面**。

（提示：默认情况下，Nginx 会使用 `/var/www/html/` 目录下的 HTML 文件。你的页面需要命名为 index.html）

你的作业文档应包含以下内容：

- 一张浏览器截图，需要包括地址栏（应包含你的云服务器公网 IP）及页面内容（自由发挥，包含”SYSU-SSE“字样即可）

------

**任务二（30 分）：**

1. 在云服务器上搭建一个博客。你可以自由地选择博客框架（如 WordPress、Typecho、Hexo 等）以及搭建方式。
2. 通过 Nginx 配置反向代理，使得访问 `http://<云服务器IP>/blog ` 时即为你的博客首页。
3. 完成后，在博客发布一篇博文，其内容应包含"SYSU-SSE"字样。
4. 截图，包括地址栏、页面内容，放作业文档

------

**任务三（40 分）：CourseBot API（LLM）初版**

1. 在同一仓库中实现 `apps/gateway` 与 `services/llm-adapter`，并提供：
   - `POST /v1/chat/completions`（要真能聊，stream=True/False均可，接入openrouter，用啥模型无所谓）
   - `GET /healthz`
   - `GET /readyz`
2. 完成统一 Provider 接口，并同时支持：
   - `FakeProvider`
   - `SaaSProvider`（接openrouter）
3. `POST /v1/chat/completions` 返回中包含 `usage.prompt_tokens`、`usage.completion_tokens`、`usage.latency_ms`。
4. nginx把api反代到`http://<云服务器IP>/v1/chat/completions`
5. 作业文档中需包含：
   - 一段 `curl` 调用与返回结果截图（要访问公网+反代的地址）
   - `healthz`、`readyz` 调用结果（200）截图

---

# **提交 DDL 及提交方式**

请于【**2025.03.17 23:59**】前，将作业PDF文件（文件命名为 **姓名-学号.pdf**，如 张三-114514.pdf）（不超过5M，超了压缩下）提交到：https://docs.qq.com/form/page/DSm9uenNkc0tLd2pX

