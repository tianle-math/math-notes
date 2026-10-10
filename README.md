# Notes on Analysis

A Quarto website for mathematical essays. The first essay is **The Basic Geometric Meaning of Frequency in Fourier Analysis (1)**, credited to the byline **Tian** supplied in the manuscript.

## 本地预览

在包含 `_quarto.yml` 的这一层文件夹打开终端：

```powershell
quarto preview
```

保持命令运行，在编辑器里修改并保存 `.qmd`，预览页面会更新。构建整个网站：

```powershell
quarto render
```

本项目已使用 Quarto 1.10.19 渲染。生产工作流固定使用同一版本。

## GitHub Pages 首次发布

1. 在准备公开使用的 GitHub 账号中创建网站仓库，建议名称 `math-notebook`。如果使用免费账号，GitHub Pages 需要公开仓库；确认仓库中只放本项目文件。
2. 将本文件夹中的源码上传到仓库 `main` 分支，包括 `.github/workflows/publish.yml`。不要上传本机的其他目录、凭据、缓存或 `.git` 文件夹。
3. 打开仓库 **Settings → Pages → Build and deployment → Source**，选择 **GitHub Actions**。
4. 打开 **Actions → Publish mathematical notebook → Run workflow**。后续提交到 `main` 会自动构建并发布。
5. 工作流成功后，到 **Settings → Pages** 查看真实发布网址。网页必须部署成功才算上线。

工作流从 GitHub Pages 自动获取公开基础网址，不需要手写账号名，不使用个人访问令牌，也不会将个人邮箱写入网页。它仅上传 `_site/`，不会将整个源码目录作为网页目录发布。

## 更新与新增文章

首篇文章位于 `essays/fourier-frequency-geometry-1.qmd`。修改它并保存即可更新本地预览；提交并推送后，线上网页自动更新。

新增文章时，将 `templates/article.qmd` 复制到 `essays/`，改成只含英文小写字母、数字和短横线的文件名，填写标题、日期、简介和正文。确认准备好发表后，把 `draft: true` 改成 `draft: false`。文章目录会自动收录。

生产构建使用 `draft-mode: gone`：`draft: true` 的文章只生成空白占位页，不发布正文，也不出现在文章目录、搜索索引或站点地图中；其网址可能仍存在。本地 `quarto preview` 仍会显示草稿。不要把私人草稿提交到公开仓库：这些设置只控制生成的网站，不保护公开仓库里的源码。

数学公式使用 `$...$` 和 `$$...$$`；元信息必须置于文件最开头的两行 `---` 之间。模板文件夹本身不会渲染成网页。

## 隐私范围

- 网站只使用稿件中已有的署名 Tian；没有个人简介、学校、真实姓名补全、邮箱、头像或社交账号。
- 无第三方统计、评论、追踪像素、远程字体、外部公式服务。公式使用浏览器原生 MathML。
- 没有个人访问令牌或其他凭据。部署使用 GitHub 提供的短期工作流权限。
- 源码中没有账号专用网址；部署时自动设置 `site-url`。GitHub Pages 的默认公开网址和仓库会显示其所属账号名，这一平台关联并不会被主题隐藏。
- Git 提交中的作者邮箱独立于网页。首次提交前，在 GitHub 的邮箱设置中启用隐藏私人邮箱，并使用 GitHub 提供的 `noreply` 地址；本地 Git 身份也应使用该地址。不要把私人邮箱填入本项目。
- 自动检查能识别常见邮箱、凭据格式和本地用户路径，但无法代替对文章内容的人工判断。GitHub 作为托管服务仍可能保留服务访问日志。

## 验证

```powershell
python scripts/check-site.py source
quarto render
python scripts/check-site.py output
```

检查源码和输出中的常见隐私泄漏、输出文件范围、本地链接及公式是否生成。不依赖第三方 Python 包。

## 页面

- `index.qmd`：首页与自动文章目录。
- `series.qmd`：傅里叶频率几何系列索引。
- `essays/`：正式文章。
- `assets/styles.scss`：页面样式。
- `.github/workflows/publish.yml`：自动构建与 GitHub Pages 发布。

## 官方参考

- [Quarto websites](https://quarto.org/docs/websites/)
- [Quarto and GitHub Pages](https://quarto.org/docs/publishing/github-pages.html)
- [GitHub Pages custom workflows](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)

未替作者授予新的内容许可；发布在 GitHub 不等于把文章变成公有领域作品。
