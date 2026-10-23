import { displayedVariance } from "./data.js";
import { sceneContainer } from "./plotly-scene.js";

export function registerMapExport(landscape) {
  // Save the map as a PNG, at twice the screen resolution. Plotly's own
  // picture holds the points and grid; the logos and the flat map's axis
  // labels are a layer above it, so they are painted onto the picture at
  // the places they have on screen.
  async function downloadView() {
    if (!landscape.has3d || !window.Plotly) return;
    const flat = landscape.flat;
    const share = displayedVariance(landscape.variance, flat);
    const SCALE = 2;
    const target = document.getElementById("plot-3d");
    const width = target.clientWidth;
    const height = target.clientHeight;
    // The paper is behind the graph, not in it: paint it in, then go back
    // to transparent.
    await Plotly.relayout(target, { paper_bgcolor: css("--hero-bg") });
    let picture;
    try {
      picture = await Plotly.toImage(target, { format: "png", width, height, scale: SCALE });
    } finally {
      Plotly.relayout(target, { paper_bgcolor: "rgba(0, 0, 0, 0)" });
    }
    const canvas = el("canvas", { width: width * SCALE, height: height * SCALE });
    const ctx = canvas.getContext("2d");
    ctx.drawImage(await loadImage(picture), 0, 0);
    ctx.scale(SCALE, SCALE);
    const origin = target.getBoundingClientRect();
    const box = (node) => {
      const r = node.getBoundingClientRect();
      return { x: r.left - origin.left, y: r.top - origin.top, w: r.width, h: r.height };
    };
    if (landscape.marks === "logos") {
      // Back to front, as on screen.
      const links = [...document.querySelectorAll("#map-logos .map-logo")]
        .sort((a, b) => Number(a.style.zIndex) - Number(b.style.zIndex));
      for (const link of links) {
        const frame = link.querySelector(".logo");
        const f = box(frame);
        const faded = getComputedStyle(link).opacity;
        ctx.globalAlpha = Number(faded);
        ctx.fillStyle = getComputedStyle(frame).backgroundColor;
        ctx.strokeStyle = css("--border");
        ctx.beginPath();
        ctx.roundRect(f.x, f.y, f.w, f.h, 4);
        ctx.fill();
        ctx.stroke();
        const img = frame.querySelector("img");
        if (img?.naturalWidth) {
          // As object-fit: contain does in the frame.
          const r = box(img);
          const fit = Math.min(r.w / img.naturalWidth, r.h / img.naturalHeight);
          const w = img.naturalWidth * fit;
          const h = img.naturalHeight * fit;
          ctx.drawImage(img, r.x + (r.w - w) / 2, r.y + (r.h - h) / 2, w, h);
        } else {
          const style = getComputedStyle(frame);
          ctx.fillStyle = style.color;
          ctx.font = `${style.fontWeight} ${parseFloat(style.fontSize) * (f.h / frame.offsetHeight)}px ${style.fontFamily}`;
          ctx.textAlign = "center";
          ctx.textBaseline = "middle";
          ctx.fillText(frame.textContent, f.x + f.w / 2, f.y + f.h / 2);
        }
        ctx.globalAlpha = 1;
      }
    }
    // The flat map's axis labels, without the link arrow.
    for (const label of document.querySelectorAll(".map-axis:not([hidden])")) {
      const text = label.textContent.replace(/\s*→\s*$/, "");
      const r = box(label);
      ctx.save();
      ctx.fillStyle = css("--ink-2");
      ctx.font = `600 13px ${css("--font-sans")}`;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.translate(r.x + r.w / 2, r.y + r.h / 2);
      if (label.classList.contains("vertical")) ctx.rotate(-Math.PI / 2);
      ctx.fillText(text, 0, 0);
      ctx.restore();
    }
    // Cropped to the map (with room for its axis labels): on screen the
    // column beside it is part of the same area.
    const scene = box(sceneContainer(target));
    const MARGIN = 48;
    const crop = {
      x: Math.max(0, scene.x - MARGIN),
      y: Math.max(0, scene.y - MARGIN / 2),
    };
    crop.w = Math.min(width, scene.x + scene.w + MARGIN / 2) - crop.x;
    crop.h = Math.min(height, scene.y + scene.h + MARGIN / 2) - crop.y;
    const caption = `${flat ? "2D" : "3D"} · ${t("Combined, the axes explain {share} of the differences.", { share: pct(share, 1) })}`;
    ctx.font = `13px ${css("--font-sans")}`;
    const lines = [""];
    for (const word of caption.split(" ")) {
      const last = lines.length - 1;
      const text = lines[last] ? `${lines[last]} ${word}` : word;
      if (lines[last] && ctx.measureText(text).width > crop.w - 32) lines.push(word);
      else lines[last] = text;
    }
    const footerHeight = 24 + lines.length * 18;
    const cropped = el("canvas", { width: Math.round(crop.w * SCALE), height: Math.round((crop.h + footerHeight) * SCALE) });
    const output = cropped.getContext("2d");
    output.fillStyle = css("--hero-bg");
    output.fillRect(0, 0, cropped.width, cropped.height);
    output.drawImage(
      canvas, crop.x * SCALE, crop.y * SCALE, crop.w * SCALE, crop.h * SCALE, 0, 0, crop.w * SCALE, crop.h * SCALE);
    output.scale(SCALE, SCALE);
    output.fillStyle = css("--ink-2");
    output.font = `13px ${css("--font-sans")}`;
    output.textBaseline = "top";
    lines.forEach((line, index) => output.fillText(line, 16, crop.h + 12 + index * 18));
    const stamp = new Date().toISOString().slice(0, 10);
    el("a", {
      href: cropped.toDataURL("image/png"),
      download: `chartist-map-${flat ? "2d" : "3d"}-${landscape.marks}-${stamp}.png`,
    }).click();
  }
  const loadImage = (src) => new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = reject;
    image.src = src;
  });
  document.getElementById("download").addEventListener("click", downloadView);

}
