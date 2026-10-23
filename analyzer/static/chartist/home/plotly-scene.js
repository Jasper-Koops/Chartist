// Plotly internals used by the logo overlay and image crop live here.
export const sceneContainer = (target) => target._fullLayout?.scene?._scene?.container;
export function sceneGeometry(target) {
  const scene = target._fullLayout?.scene?._scene;
  const camera = scene?.glplot?.cameraParams;
  if (!camera || !scene.container) return null;
  return { ...camera, box: scene.container.getBoundingClientRect() };
}
export function projector(target) {
  const scene = target._fullLayout?.scene?._scene;
  const camera = scene?.glplot?.cameraParams;
  if (!camera) return null;
  const { model, view, projection } = camera;
  const scale = scene.dataScale;
  const box = scene.container.getBoundingClientRect();
  const origin = target.getBoundingClientRect();
  const times = (m, v) => [0, 1, 2, 3].map((r) => m[r] * v[0] + m[4 + r] * v[1] + m[8 + r] * v[2] + m[12 + r] * v[3]);
  return (x, y, z) => {
    const v = times(projection, times(view, times(model, [x * scale[0], y * scale[1], z * scale[2], 1])));
    return {
      x: box.left - origin.left + ((v[0] / v[3] + 1) / 2) * box.width,
      y: box.top - origin.top + ((1 - v[1] / v[3]) / 2) * box.height,
      depth: v[2] / v[3],
      distance: v[3],  // from the camera
    };
  };
}
