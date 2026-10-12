/* Local page enhancements. Giscus is requested only after an explicit click. */
(() => {
  "use strict";

  const GISCUS_ORIGIN = "https://giscus.app";
  const messages = {
    en: {
      loading: "Loading comments…",
      ready: "Comments are ready. Sign in with GitHub to join the discussion.",
      empty: "Be the first to comment. Sign in with GitHub to join the discussion.",
      error: "Comments could not be loaded. Try again, or open the discussion on GitHub.",
      config: "Comments are not available yet. You can visit the discussions on GitHub.",
      retry: "Retry loading comments",
      frame: "Article comments — sign in with GitHub to comment",
    },
    "zh-CN": {
      loading: "正在加载评论……",
      ready: "评论已就绪。登录 GitHub 即可参与讨论。",
      empty: "还没有评论，欢迎交流。登录 GitHub 即可参与讨论。",
      error: "评论未能加载。请重试，或前往 GitHub 查看讨论。",
      config: "评论暂未开放。你可以前往 GitHub 查看讨论。",
      retry: "重新加载评论",
      frame: "文章评论——登录 GitHub 即可评论",
    },
    ja: {
      loading: "コメントを読み込んでいます…",
      ready: "コメントを読み込みました。GitHub にログインして議論に参加できます。",
      empty: "まだコメントはありません。GitHub にログインして、ぜひご意見をお聞かせください。",
      error: "コメントを読み込めませんでした。再試行するか、GitHub で議論をご覧ください。",
      config: "コメントはまだ利用できません。GitHub で議論をご覧いただけます。",
      retry: "コメントの読み込みを再試行",
      frame: "記事へのコメント — 投稿には GitHub へのログインが必要です",
    },
  };

  function preserveLanguageAnchors() {
    const links = document.querySelectorAll(".language-switch a[hreflang], a[data-language-link]");
    for (const link of links) {
      // Use the actual href as the base; never propagate authentication queries.
      const target = new URL(link.getAttribute("href"), location.href);
      if (target.origin !== location.origin) continue;
      const update = () => {
        target.hash = location.hash;
        link.href = target.href;
      };
      update();
      window.addEventListener("hashchange", update);
      link.addEventListener("click", update);
      link.addEventListener("auxclick", update);
    }
  }

  function initialiseComments(section) {
    const button = section.querySelector("[data-load-comments]");
    const status = section.querySelector('[role="status"]');
    const container = section.querySelector(".giscus");
    if (!button || !status || !container) return;

    const lang = Object.hasOwn(messages, section.dataset.lang) ? section.dataset.lang : "en";
    const text = messages[lang];
    let state = "idle";
    let timer;
    let script;
    let emptyDiscussion = false;
    let rendered = false;

    status.setAttribute("aria-live", "polite");
    status.setAttribute("aria-atomic", "true");
    button.type = "button";
    section.dataset.commentState = state;

    function frame() {
      return container.querySelector("iframe.giscus-frame");
    }

    function setState(next, message) {
      state = next;
      section.dataset.commentState = next;
      container.setAttribute("aria-busy", String(next === "loading"));
      status.textContent = message;
    }

    function failed(message = text.error) {
      window.clearTimeout(timer);
      setState("error", message);
      button.disabled = false;
      button.hidden = false;
      button.textContent = text.retry;
      // Keep a rendered widget in place: an API error must not erase a draft.
    }

    function ready(isEmpty) {
      const widget = frame();
      if (!widget) return;
      window.clearTimeout(timer);
      widget.title = text.frame;
      const hadFocus = document.activeElement === button;
      setState("ready", isEmpty ? text.empty : text.ready);
      button.hidden = true;
      if (hadFocus) widget.focus({ preventScroll: true });
    }

    window.addEventListener("message", (event) => {
      const widget = frame();
      if (state === "idle" || !widget || event.origin !== GISCUS_ORIGIN || event.source !== widget.contentWindow) return;
      const payload = event.data && typeof event.data === "object" && event.data.giscus;
      if (!payload || typeof payload !== "object") return;

      if (typeof payload.error === "string") {
        // A new article has no discussion until its first comment or reaction.
        if (payload.error.includes("Discussion not found")) {
          emptyDiscussion = true;
          if (rendered) ready(true);
        } else {
          emptyDiscussion = false;
          failed();
        }
        return;
      }

      if (Number.isFinite(payload.resizeHeight) && payload.resizeHeight > 0) {
        rendered = true;
        widget.title = text.frame;
        if (emptyDiscussion) ready(true);
      }

      const discussion = payload.discussion;
      if (discussion && typeof discussion === "object" && typeof discussion.id === "string" && discussion.id
          && discussion.repository?.nameWithOwner?.toLowerCase() === section.dataset.repo.toLowerCase()) {
        ready(false);
        // Replace the generic fallback link only with a verified discussion URL.
        const link = section.querySelector("[data-discussion-link]");
        if (link && typeof discussion.url === "string") {
          try {
            const url = new URL(discussion.url);
            const prefix = `/${section.dataset.repo.toLowerCase()}/discussions/`;
            if (url.origin === "https://github.com" && url.pathname.toLowerCase().startsWith(prefix)
                && /^\d+$/.test(url.pathname.slice(prefix.length))) link.href = url.href;
          } catch (_) { /* Retain the original fallback link. */ }
        }
      }
    });

    button.addEventListener("click", () => {
      if (state === "loading" || state === "ready") return;
      const config = section.dataset;
      if (![config.repo, config.repoId, config.category, config.categoryId, config.term].every(value => value?.trim())) {
        failed(text.config);
        return;
      }
      emptyDiscussion = false;
      rendered = false;
      button.disabled = true;
      setState("loading", text.loading);
      timer = window.setTimeout(() => failed(), 25000);

      const existingFrame = frame();
      if (existingFrame) {
        // Reuse the client and its event handlers when retrying a widget error.
        existingFrame.src = existingFrame.src;
        return;
      }

      if (script) script.remove();
      script = document.createElement("script");
      script.src = `${GISCUS_ORIGIN}/client.js`;
      script.async = true;
      script.crossOrigin = "anonymous";
      const attributes = {
        repo: config.repo,
        "repo-id": config.repoId,
        category: config.category,
        "category-id": config.categoryId,
        mapping: "specific",
        term: config.term,
        strict: "1",
        "reactions-enabled": "1",
        "emit-metadata": "1",
        "input-position": "top",
        theme: "light",
        lang,
        loading: "lazy",
      };
      for (const [name, value] of Object.entries(attributes)) script.setAttribute(`data-${name}`, value);
      script.addEventListener("error", () => failed());
      // No success handler here: downloading client.js is not proof of a working discussion.
      section.appendChild(script);
    });
  }

  function initialise() {
    preserveLanguageAnchors();
    // Each article has one shared thread, regardless of the page language.
    document.querySelectorAll(".article-comments").forEach(initialiseComments);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", initialise, { once: true });
  else initialise();
})();
