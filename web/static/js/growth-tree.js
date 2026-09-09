/* ==================================================================
   AYUR-INTEL — Procedural Growth Tree Botanical Background
   Organic procedural canvas botanical tree with hover wind sway & ambient breathing
   ================================================================== */

(function () {
  "use strict";

  var canvas = document.getElementById("growth-tree-canvas");
  if (!canvas) {
    canvas = document.createElement("canvas");
    canvas.id = "growth-tree-canvas";
    canvas.className = "growth-tree-canvas";
    document.body.insertBefore(canvas, document.body.firstChild);
  }

  var ctx = canvas.getContext("2d");
  if (!ctx) return;

  var width = 0;
  var height = 0;
  var dpr = 1;
  var animId = null;
  var branches = [];
  var leaves = [];
  var maxDepth = 8;
  var isGrowthComplete = false;
  var time = 0;

  // Wind Sway Controls
  window.targetWind = 0;
  window.currentWind = 0;

  window.addEventListener("mousemove", function (e) {
    if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      window.targetWind = 0;
      return;
    }
    var relX = (e.clientX / window.innerWidth) - 0.5;
    window.targetWind = relX * 0.12; // Responsive wind angle offset
  });

  window.addEventListener("mouseleave", function () {
    window.targetWind = 0;
  });

  function resize() {
    dpr = window.devicePixelRatio || 1;
    width = window.innerWidth;
    height = window.innerHeight;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    canvas.style.width = width + "px";
    canvas.style.height = height + "px";
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    initTrees();
  }

  // Botanical Branch Object
  function createBranch(x, y, angle, length, depth, branchWidth) {
    return {
      x: x,
      y: y,
      currX: x,
      currY: y,
      baseAngle: angle,
      angle: angle,
      length: length,
      depth: depth,
      branchWidth: branchWidth,
      progress: 0,
      speed: 0.04 + Math.random() * 0.03,
      childrenSpawned: false,
      completed: false
    };
  }

  function initTrees() {
    if (animId) cancelAnimationFrame(animId);
    ctx.clearRect(0, 0, width, height);
    branches = [];
    leaves = [];
    isGrowthComplete = false;
    time = 0;

    // Left botanical tree
    var leftBaseX = width * 0.08;
    var leftBaseY = height + 10;
    var leftTrunkLength = Math.min(height * 0.28, 220);
    branches.push(createBranch(leftBaseX, leftBaseY, -Math.PI / 2.25, leftTrunkLength, 0, 7.5));

    // Right botanical tree
    var rightBaseX = width * 0.92;
    var rightBaseY = height + 10;
    var rightTrunkLength = Math.min(height * 0.24, 190);
    branches.push(createBranch(rightBaseX, rightBaseY, -Math.PI / 1.8, rightTrunkLength, 0, 6.0));

    // Center subtle accent branch
    var centerBaseX = width * 0.52;
    var centerBaseY = height + 10;
    var centerTrunkLength = Math.min(height * 0.18, 140);
    branches.push(createBranch(centerBaseX, centerBaseY, -Math.PI / 2.05, centerTrunkLength, 0, 4.5));

    animate();
  }

  function renderTreeFrame() {
    ctx.clearRect(0, 0, width, height);
    time += 0.02;

    // Ambient breathing oscillation + mouse-driven wind sway
    var ambientWind = Math.sin(time * 0.8) * 0.025 + Math.sin(time * 1.5) * 0.012;
    window.currentWind += (window.targetWind - window.currentWind) * 0.06;
    var totalWind = window.currentWind + ambientWind;

    // Draw Branches
    for (var i = 0; i < branches.length; i++) {
      var b = branches[i];
      var windFactor = (b.depth + 1) * 0.35;
      var effectiveAngle = b.baseAngle + (totalWind * windFactor);

      var endX = b.x + Math.cos(effectiveAngle) * (b.length * b.progress);
      var endY = b.y + Math.sin(effectiveAngle) * (b.length * b.progress);

      b.currX = endX;
      b.currY = endY;

      ctx.beginPath();
      ctx.moveTo(b.x, b.y);
      ctx.lineTo(b.currX, b.currY);

      var alpha = Math.max(0.12, 0.45 - (b.depth * 0.04));
      var greenTone = Math.floor(180 + b.depth * 8);
      ctx.strokeStyle = "rgba(45, " + greenTone + ", 125, " + alpha + ")";
      ctx.lineWidth = Math.max(0.8, b.branchWidth * (1 - (b.depth / maxDepth) * 0.5));
      ctx.lineCap = "round";
      ctx.stroke();

      if (b.childrenSpawned && b.childIndices) {
        for (var j = 0; j < b.childIndices.length; j++) {
          var child = branches[b.childIndices[j]];
          child.x = b.currX;
          child.y = b.currY;
        }
      }
    }

    // Draw Leaves
    for (var l = 0; l < leaves.length; l++) {
      var lf = leaves[l];
      var parentBranch = branches[lf.branchIndex];
      if (parentBranch) {
        var lx = parentBranch.currX + lf.offsetX + Math.sin(time * 1.2 + l) * 2;
        var ly = parentBranch.currY + lf.offsetY + Math.cos(time * 1.2 + l) * 2;

        ctx.beginPath();
        ctx.arc(lx, ly, lf.radius, 0, Math.PI * 2);
        if (lf.isGold) {
          ctx.fillStyle = "rgba(212, 175, 55, " + (lf.opacity * 0.65) + ")";
        } else {
          ctx.fillStyle = "rgba(52, 211, 153, " + (lf.opacity * 0.75) + ")";
        }
        ctx.fill();
      }
    }
  }

  function animate() {
    var growing = false;

    for (var i = 0; i < branches.length; i++) {
      var b = branches[i];
      if (!b.completed) {
        growing = true;
        b.progress += b.speed;
        if (b.progress >= 1) {
          b.progress = 1;
          b.completed = true;
        }

        if (b.completed && !b.childrenSpawned && b.depth < maxDepth) {
          b.childrenSpawned = true;
          b.childIndices = [];
          var numSub = 2 + (Math.random() > 0.65 ? 1 : 0);
          var angleSpread = 0.42 + Math.random() * 0.24;

          for (var s = 0; s < numSub; s++) {
            var dir = s === 0 ? -1 : (s === 1 ? 1 : (Math.random() > 0.5 ? -0.5 : 0.5));
            var newAngle = b.baseAngle + dir * (angleSpread * (0.6 + Math.random() * 0.5));
            var newLength = b.length * (0.72 + Math.random() * 0.16);
            var newWidth = b.branchWidth * 0.70;

            var newBranch = createBranch(b.currX, b.currY, newAngle, newLength, b.depth + 1, newWidth);
            branches.push(newBranch);
            b.childIndices.push(branches.length - 1);
          }

          if (b.depth >= 3) {
            leaves.push({
              branchIndex: i,
              offsetX: (Math.random() - 0.5) * 12,
              offsetY: (Math.random() - 0.5) * 12,
              radius: 2.0 + Math.random() * 3.2,
              opacity: 0,
              maxOpacity: b.depth >= 6 ? (0.25 + Math.random() * 0.2) : (0.2 + Math.random() * 0.15),
              isGold: Math.random() > 0.82
            });
          }
        }
      }
    }

    for (var l = 0; l < leaves.length; l++) {
      var lf = leaves[l];
      if (lf.opacity < lf.maxOpacity) {
        growing = true;
        lf.opacity += 0.02;
      }
    }

    renderTreeFrame();

    if (growing) {
      animId = requestAnimationFrame(animate);
    } else {
      isGrowthComplete = true;
      window.isGrowthComplete = true;
      runSwayLoop();
    }
  }

  function runSwayLoop() {
    renderTreeFrame();
    if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      return; // Static frame for reduced motion
    }
    animId = requestAnimationFrame(runSwayLoop);
  }

  var resizeTimeout;
  window.addEventListener("resize", function () {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(resize, 200);
  });

  document.addEventListener("visibilitychange", function () {
    if (document.hidden) {
      if (animId) { cancelAnimationFrame(animId); animId = null; }
    } else {
      if (!animId) {
        if (isGrowthComplete) runSwayLoop();
        else animate();
      }
    }
  });

  window.addEventListener("DOMContentLoaded", resize);
  if (document.readyState === "complete" || document.readyState === "interactive") {
    resize();
  }
})();

