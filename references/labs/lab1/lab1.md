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
- 贴本文档全部内容，问「教我一步步完成这个作业」

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

## 作业要求

**任务一（60 分）：**

在完成以上步骤的基础上，将Nginx默认欢迎页**替换为你自己的页面**。

（提示：默认情况下，Nginx 会使用 `/var/www/html/` 目录下的 HTML 文件。你的页面需要命名为 index.html）

你的作业文档应包含以下内容：

- 一张浏览器截图，需要包括地址栏（应包含你的云服务器公网 IP）及页面内容（自由发挥，包含”SYSU-SSE“字样即可）

------

**任务二（40 分）：**

1. 在云服务器上搭建一个博客。你可以自由地选择博客框架（如 WordPress、Typecho、Hexo 等）以及搭建方式。
2. 通过 Nginx 配置反向代理，使得访问 `http://<云服务器IP>/blog ` 时即为你的博客首页。
3. 完成后，在博客发布一篇博文，其内容应包含"SYSU-SSE"字样。
4. **将这篇博文的链接写进作业文档**（请确保该链接在本次作业提交DDL之后的至少3天内可访问，即云服务器需要处于启动状态），无需其他文字及配图 。

---

**提交 DDL 及提交方式**：

请于【**2025.03.12 23:59**】前，将作业PDF文件（文件命名为 **姓名-学号-第一次作业**，如 张三-23232323-第一次作业.pdf）发送至邮箱 【**[dengzl11@163.com](mailto:dengzl11@163.com)】**，邮件标题格式： **姓名-学号-第一次作业**

---

## 注意：云服务器保留至 3月16日 即可，之后请及时释放云服务器实例，避免持续扣费

