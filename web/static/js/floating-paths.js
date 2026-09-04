/* ==================================================================
   AYUR-INTEL — Ambient Floating Paths Background
   Slow Organic Flow: Synchronized left-entry, ultra-slow 8-12x velocity desynchronization,
   and soft white contour lines moving strictly Left -> Right.
   ================================================================== */

(function () {
  "use strict";

  var canvas = document.getElementById("floating-paths-canvas");
  if (!canvas) {
    canvas = document.createElement("canvas");
    canvas.id = "floating-paths-canvas";
    canvas.className = "floating-paths-canvas";
    document.body.insertBefore(canvas, document.body.firstChild);
  }

  var ctx = canvas.getContext("2d");
  if (!ctx) return;

  var width = 0;
  var height = 0;
  var animId = null;

  // Ultra-slow base speed: ~0.08px per frame (8-12x slower than original)
  var baseSpeed = 0.08;

  // Path definitions: Deterministic per-path parameters starting together from left
  var paths = [
    { yRatio: 0.20, amp: 45, velMultiplier: 1.12, opacity: 0.035, width: 0.9, phase: 0.0, color: "255, 255, 255", x: 0 },
    { yRatio: 0.35, amp: 65, velMultiplier: 0.98, opacity: 0.025, width: 0.8, phase: 1.2, color: "245, 248, 245", x: 0 },
    { yRatio: 0.52, amp: 40, velMultiplier: 0.88, opacity: 0.038, width: 1.0, phase: 2.5, color: "255, 255, 255", x: 0 },
    { yRatio: 0.68, amp: 70, velMultiplier: 1.06, opacity: 0.030, width: 0.8, phase: 3.8, color: "240, 245, 242", x: 0 },
    { yRatio: 0.82, amp: 50, velMultiplier: 0.94, opacity: 0.035, width: 0.9, phase: 5.1, color: "255, 255, 255", x: 0 },
    { yRatio: 0.40, amp: 60, velMultiplier: 1.02, opacity: 0.022, width: 0.8, phase: 0.7, color: "245, 248, 245", x: 0 }
  ];

  function resize() {
    width = canvas.width = window.innerWidth;
    height = canvas.height = window.innerHeight;
  }

  function initPaths() {
    // Initial load: start together from the left side
    var initialLeftOffset = -width * 0.3;
    for (var i = 0; i < paths.length; i++) {
      // Small staggered offset so they form a subtle organic group entering from left edge
      paths[i].x = initialLeftOffset - (i * 25);
    }
  }

  function drawPath(p) {
    ctx.beginPath();
    var startY = height * p.yRatio;
    var numPoints = 8;
    var totalLength = width + 400;
    var step = totalLength / (numPoints - 1);

    for (var i = 0; i < numPoints; i++) {
      var x = p.x + (i * step);
      
      // Long, smooth, organic Bezier S-curve wave
      var wave1 = Math.sin((x * 0.0006) + p.phase);
      var wave2 = Math.cos((x * 0.00035) + p.phase * 0.7);
      var y = startY + wave1 * p.amp + wave2 * (p.amp * 0.35);

      if (i === 0) {
        ctx.moveTo(x, y);
      } else {
        var prevX = p.x + ((i - 1) * step);
        var cpX = (prevX + x) / 2;
        var cpY = y - wave2 * 15;
        ctx.quadraticCurveTo(cpX, cpY, x, y);
      }
    }

    ctx.strokeStyle = "rgba(" + p.color + ", " + p.opacity + ")";
    ctx.lineWidth = p.width;
    ctx.lineCap = "round";
    ctx.stroke();
  }

  function animate() {
    ctx.clearRect(0, 0, width, height);

    var isMobile = width <= 600;
    var activeCount = isMobile ? 4 : paths.length;

    for (var i = 0; i < activeCount; i++) {
      var p = paths[i];

      // Strict Left -> Right slow movement with subtle velocity desynchronization
      p.x += baseSpeed * p.velMultiplier;

      // Draw the path
      drawPath(p);

      // Recycling: When path tail clears the right edge, seamlessly restart at left edge
      if (p.x > width + 100) {
        p.x = -width * 0.5 - Math.random() * 80;
      }
    }

    // Respect prefers-reduced-motion
    if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      return; // Static frame for reduced motion
    }

    animId = requestAnimationFrame(animate);
  }

  window.addEventListener("resize", resize);
  resize();
  initPaths();
  animId = requestAnimationFrame(animate);
})();
