// Online 3D Viewer for the part previews in fabrication.md.
//
// The viewer is fed an OBJ, not the STEP: OCCT does read STEP in the browser,
// but only by pulling in a multi-MB WASM build, and the two produce the same
// picture here because both come from the same merged geometry. `edgesettings`
// on the element is why this viewer is used at all - it draws an edge only
// where the dihedral angle exceeds the threshold, so the part's real edges
// show and the triangulation underneath them does not.
//
// Colours live on the element in fabrication.md. The background is transparent
// so the page shows through, which is what keeps one setting readable under
// both Material palettes - re-initialising the viewer when the scheme changes
// leaks a WebGL context and locks the tab up.
(function () {
  "use strict";

  // MkDocs rewrites the path of THIS script (it is a docs asset) but never
  // touches attributes inside raw HTML, so a hand-written "../_models/..." in
  // fabrication.md breaks the moment the site is served under a prefix - a
  // `mike` version directory, a project subpath, GitHub Pages. Recover the
  // site root from this script's own URL instead, and resolve `data-model`
  // against it. `document.currentScript` has to be read while the script body
  // is executing, hence up here.
  var SCRIPT = document.currentScript;

  function siteRoot() {
    if (!SCRIPT || !SCRIPT.src) {
      return "";
    }
    return SCRIPT.src.replace(/assets\/o3dv-init\.js(\?.*)?$/, "");
  }

  var TURN_MS = 45000; // one full revolution
  var TWO_PI = Math.PI * 2;

  // Rotate `point` around the axis `axis` through `origin` (Rodrigues), so the
  // camera orbits whatever the model calls up rather than a hardcoded Z.
  function orbit(point, origin, axis, angle) {
    var length = Math.sqrt(axis.x * axis.x + axis.y * axis.y + axis.z * axis.z);
    if (!length) {
      return;
    }
    var ux = axis.x / length;
    var uy = axis.y / length;
    var uz = axis.z / length;
    var x = point.x - origin.x;
    var y = point.y - origin.y;
    var z = point.z - origin.z;
    var cos = Math.cos(angle);
    var sin = Math.sin(angle);
    var dot = ux * x + uy * y + uz * z;
    point.x = origin.x + x * cos + (uy * z - uz * y) * sin + ux * dot * (1 - cos);
    point.y = origin.y + y * cos + (uz * x - ux * z) * sin + uy * dot * (1 - cos);
    point.z = origin.z + z * cos + (ux * y - uy * x) * sin + uz * dot * (1 - cos);
  }

  // Spin until the reader touches the viewer - once they start orbiting it
  // themselves, an animation fighting the drag is only in the way.
  function spin(viewer, element) {
    var stopped = false;
    var visible = true;
    var previous = null;

    ["pointerdown", "wheel"].forEach(function (event) {
      element.addEventListener(event, function () {
        stopped = true;
      });
    });

    if (typeof IntersectionObserver !== "undefined") {
      new IntersectionObserver(function (entries) {
        visible = entries[0].isIntersecting;
        previous = null; // do not jump by however long it was off screen
      }).observe(element);
    }

    function frame(now) {
      if (stopped) {
        return;
      }
      if (visible && previous !== null) {
        var camera = viewer.GetCamera();
        orbit(camera.eye, camera.center, camera.up, (TWO_PI * (now - previous)) / TURN_MS);
        viewer.SetCamera(camera); // this renders
      }
      previous = visible ? now : null;
      window.requestAnimationFrame(frame);
    }

    window.requestAnimationFrame(frame);
  }

  window.addEventListener("load", function () {
    var elements = document.getElementsByClassName("online_3d_viewer");
    if (typeof OV === "undefined" || !elements.length) {
      return;
    }
    var root = siteRoot();
    for (var e = 0; e < elements.length; e += 1) {
      var model = elements[e].getAttribute("data-model");
      if (model) {
        elements[e].setAttribute("model", root + model);
      }
    }
    var viewers = OV.Init3DViewerElements();
    for (var i = 0; i < viewers.length; i += 1) {
      if (viewers[i] && elements[i]) {
        spin(viewers[i].GetViewer(), elements[i]);
      }
    }
  });
})();
