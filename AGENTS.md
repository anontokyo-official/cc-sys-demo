# cc-sys-demo

- 课程实验大纲参见 `references/exp.md` （先看一下）
- k8s部署
  - 当要求进行k8s相关的操作时，先使用kubectl的read系列命令，获取当前集群尽可能详细的状态
  - 可以使用一切kubectl命令
  - 部署文件：`deploy/` （先列出）
    - 增删改部署文件的时候使用 $k8s-manifest-generator 技能
  - 集群：orbstack + k3d，集群名称：`dev`
  - 使用kubectl port-forward转发端口进行debug
- 写任何代码永远使用 $logging-best-practices 技能