// Online 3D Viewer for the part previews in fabrication.md.
//
// The viewer is fed an OBJ, not the STEP: OCCT does read STEP in the browser,
// but only by pulling in a multi-MB WASM build, and the two produce the same
// picture here because both come from the same merged geometry. `edgesettings`
// is why this viewer is used at all - it draws an edge only where the dihedral
// angle exceeds the threshold, so the part's real edges show and the
// triangulation underneath them does not.
//
// The page embeds a viewer per part table row AND per section - far more than
// the browser's WebGL context budget (~16). Chrome then starts dropping
// contexts, and a lost/restored context comes back with a black canvas. So
// viewers are created lazily: one is built when it scrolls near the viewport
// and destroyed again when it leaves, so only the handful on screen ever hold
// a WebGL context.
//
// Shared appearance lives in DEFAULTS below (solid white background, one grey,
// one edge setting) so fabrication.md only carries `data-model` and, where the
// default fit is wrong, a `camera`.
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

  // One look for every preview; an element can still override any of these
  // with its own attribute.
  var DEFAULTS = {
    backgroundcolor: "255,255,255,255",
    defaultcolor: "170,175,180",
    edgesettings: "on,45,45,45,20",
  };

  // Create viewers this far outside the viewport, so they are usually loaded
  // by the time the reader scrolls to them.
  var LOOKAHEAD = "400px 0px";

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
  // themselves, an animation fighting the drag is only in the way - or until
  // the viewer is destroyed (state.stopped).
  function spin(viewer, element, state) {
    ["pointerdown", "wheel"].forEach(function (event) {
      element.addEventListener(event, function () {
        state.stopped = true;
      });
    });

    var previous = null;

    function frame(now) {
      if (state.stopped) {
        return;
      }
      if (previous !== null) {
        var camera = viewer.GetCamera();
        orbit(camera.eye, camera.center, camera.up, (TWO_PI * (now - previous)) / TURN_MS);
        viewer.SetCamera(camera); // this renders
      }
      previous = now;
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
    Array.prototype.forEach.call(elements, function (element) {
      var model = element.getAttribute("data-model");
      if (model) {
        element.setAttribute("model", root + model);
      }
      Object.keys(DEFAULTS).forEach(function (attribute) {
        if (!element.hasAttribute(attribute)) {
          element.setAttribute(attribute, DEFAULTS[attribute]);
        }
      });
    });

    var states = new Map(); // element -> { embedded, stopped }

    function create(element) {
      if (states.has(element)) {
        return;
      }
      var convert = OV.ParameterConverter;
      var urls = convert.StringToModelUrls(element.getAttribute("model"));
      if (!urls) {
        return;
      }
      var camera = element.getAttribute("camera");
      var background = convert.StringToRGBAColor(element.getAttribute("backgroundcolor"));
      var embedded = OV.Init3DViewerFromUrlList(element, urls, {
        camera: camera ? convert.StringToCamera(camera) : null,
        backgroundColor: background,
        defaultColor: convert.StringToRGBColor(element.getAttribute("defaultcolor")),
        edgeSettings: convert.StringToEdgeSettings(element.getAttribute("edgesettings")),
      });
      var state = { embedded: embedded, stopped: false };
      states.set(element, state);
      spin(embedded.GetViewer(), element, state);

      // If the browser drops and restores this canvas' WebGL context (too many
      // contexts page-wide), the restored context comes back clearing to black
      // - put the background back.
      var canvas = element.querySelector("canvas");
      if (canvas) {
        canvas.addEventListener("webglcontextrestored", function () {
          if (states.get(element) === state) {
            embedded.GetViewer().SetBackgroundColor(background);
          }
        });
      }
    }

    function destroy(element) {
      var state = states.get(element);
      if (!state) {
        return;
      }
      state.stopped = true;
      state.embedded.Destroy();
      // The embedded viewer's own window `resize` listener survives Destroy
      // and would call Resize on the disposed renderer.
      state.embedded.Resize = function () {};
      states.delete(element);
      element.textContent = ""; // drop the dead canvas
    }

    // A clean click (no drag) on a preview expands it into a lightbox: a
    // fresh, big viewer of the same model, so orbit-by-drag in the small one
    // keeps working. Esc, the x or a click on the backdrop closes it.
    function openLightbox(source) {
      var overlay = document.createElement("div");
      overlay.className = "o3dv-lightbox";

      var big = document.createElement("div");
      big.className = "online_3d_viewer";
      ["model", "camera", "backgroundcolor", "defaultcolor", "edgesettings"].forEach(function (attribute) {
        var value = source.getAttribute(attribute);
        if (value) {
          big.setAttribute(attribute, value);
        }
      });

      var close = document.createElement("button");
      close.className = "o3dv-lightbox-close";
      close.type = "button";
      close.textContent = "×";

      overlay.appendChild(big);
      overlay.appendChild(close);
      document.body.appendChild(overlay);
      create(big);

      function shut() {
        destroy(big);
        overlay.remove();
        document.removeEventListener("keydown", onKey);
      }
      function onKey(event) {
        if (event.key === "Escape") {
          shut();
        }
      }
      close.addEventListener("click", shut);
      overlay.addEventListener("click", function (event) {
        if (event.target === overlay) {
          shut();
        }
      });
      document.addEventListener("keydown", onKey);
    }

    function expandOnClick(element) {
      var down = null;
      element.addEventListener("pointerdown", function (event) {
        down = [event.clientX, event.clientY];
      });
      element.addEventListener("pointerup", function (event) {
        if (!down) {
          return;
        }
        var moved = Math.abs(event.clientX - down[0]) + Math.abs(event.clientY - down[1]);
        down = null;
        if (moved < 5) {
          openLightbox(element);
        }
      });
    }

    Array.prototype.forEach.call(elements, expandOnClick);

    if (typeof IntersectionObserver === "undefined") {
      Array.prototype.forEach.call(elements, create); // old browser: eager
      return;
    }

    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          (entry.isIntersecting ? create : destroy)(entry.target);
        });
      },
      { rootMargin: LOOKAHEAD }
    );
    Array.prototype.forEach.call(elements, function (element) {
      observer.observe(element);
    });
  });
})();
