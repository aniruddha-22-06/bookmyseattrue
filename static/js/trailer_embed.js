(function () {
  "use strict";

  function buildEmbedUrl(videoId, autoplay) {
    var params = "rel=0&modestbranding=1&playsinline=1&autoplay=" + (autoplay ? "1" : "0");
    return "https://www.youtube.com/embed/" + videoId + "?" + params;
  }

  function renderUnavailable(container) {
    var fallback = container.querySelector("[data-trailer-fallback]");
    var placeholder = container.querySelector("[data-trailer-placeholder]");
    if (placeholder) placeholder.hidden = true;
    if (fallback) fallback.hidden = false;
  }

  function loadIframe(container, videoId, autoplay, onFail) {
    var frameHost = container.querySelector("[data-trailer-frame]");
    var placeholder = container.querySelector("[data-trailer-placeholder]");
    if (!frameHost) return;

    var iframe = document.createElement("iframe");
    iframe.width = "100%";
    iframe.height = "420";
    iframe.loading = "lazy";
    iframe.allowFullscreen = true;
    iframe.referrerPolicy = "strict-origin-when-cross-origin";
    iframe.setAttribute(
      "allow",
      "accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
    );
    iframe.setAttribute(
      "sandbox",
      "allow-scripts allow-same-origin allow-presentation allow-popups allow-popups-to-escape-sandbox allow-forms"
    );
    iframe.src = buildEmbedUrl(videoId, autoplay);
    iframe.title = container.getAttribute("data-trailer-title") || "Movie trailer";

    iframe.addEventListener("error", function () {
      frameHost.textContent = "";
      renderUnavailable(container);
      if (typeof onFail === "function") onFail();
    });

    if (placeholder) placeholder.hidden = true;
    frameHost.textContent = "";
    frameHost.appendChild(iframe);
  }

  function initTrailer(container) {
    var videoId = container.getAttribute("data-trailer-video-id");
    var playBtn = container.querySelector("[data-trailer-play]");
    if (!videoId || videoId.length !== 11) {
      renderUnavailable(container);
      return;
    }

    var loaded = false;

    function safeLoad(autoplay) {
      if (loaded) return;
      loaded = true;
      loadIframe(container, videoId, autoplay, function () {
        loaded = false;
      });
    }

    if (playBtn) {
      playBtn.addEventListener("click", function () {
        safeLoad(true);
      });
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    var blocks = document.querySelectorAll("[data-trailer-block]");
    blocks.forEach(initTrailer);
  });
})();
