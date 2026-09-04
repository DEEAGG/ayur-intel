/* ==================================================================
   AYUR-INTEL — Simple Growth Tree Animated Botanical Background
   Ambient procedural canvas botanical tree with wind sway & light opacity
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
  var animId = null;
  var branches = [];
  var leaves = [];
  var maxDepth = 9;
  var isGrowthComplete = false;

  // Wind Sway Controls
  window.targetWind = 0;
  window.currentWind = 0;

  window.addEventListener("mousemove", function (e) {
    if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      window.targetWind = 0;
      return;
    }
    var relX = (e.clientX / window.innerWidth) - 0.5;
    window.targetWind = relX * 0.05; // Max 0.05 rad sway (~2.8 deg)
  });

  window.addEventListener("mouseleave", function () {
    window.targetWind = 0;
  });

  function resize() {
    width = canvas.width = window.innerWidth;
    height = canvas.height = window.innerHeight;
    initTrees();
  }

  // Botanical Tree Generator
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
      speed: 0.035 + Math.random() * 0.025,
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

    var leftBaseX = width * 0.08;
    var leftBaseY = height + 10;
    var leftTrunkLength = Math.min(height * 0.24, 180);
    branches.push(createBranch(leftBaseX, leftBaseY, -Math.PI / 2.3, leftTrunkLength, 0, 6.5));

    var rightBaseX = width * 0.92;
    var rightBaseY = height + 10;
    var rightTrunkLength = Math.min(height * 0.20, 150);
    branches.push(createBranch(rightBaseX, rightBaseY, -Math.PI / 1.75, rightTrunkLength, 0, 5));

    animate();
  }

  function renderTreeFrame() {
    ctx.clearRect(0, 0, width, height);

    // Smooth Lerp Wind Sway
    window.currentWind += (window.targetWind - window.currentWind) * 0.04;

    for (var i = 0; i < branches.length; i++) {
      var b = branches[i];
      var windFactor = (b.depth + 1) * 0.30;
      var effectiveAngle = b.baseAngle + (window.currentWind * windFactor);

      var endX = b.x + Math.cos(effectiveAngle) * (b.length * b.progress);
      var endY = b.y + Math.sin(effectiveAngle) * (b.length * b.progress);

      b.currX = endX;
      b.currY = endY;

      ctx.beginPath();
      ctx.moveTo(b.x, b.y);
      ctx.lineTo(b.currX, b.currY);

      var alpha = Math.max(0.05, 0.16 - (b.depth * 0.015));
      var greenTone = Math.floor(190 + b.depth * 6);
      ctx.strokeStyle = "rgba(45, " + greenTone + ", 125, " + alpha + ")";
      ctx.lineWidth = Math.max(0.7, b.branchWidth * (1 - (b.depth / maxDepth) * 0.55));
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

    for (var l = 0; l < leaves.length; l++) {
      var lf = leaves[l];
      var parentBranch = branches[lf.branchIndex];
      if (parentBranch) {
        var lx = parentBranch.currX + lf.offsetX;
        var ly = parentBranch.currY + lf.offsetY;

        ctx.beginPath();
        ctx.arc(lx, ly, lf.radius, 0, Math.PI * 2);
        if (lf.isGold) {
          ctx.fillStyle = "rgba(212, 175, 55, " + (lf.opacity * 0.45) + ")";
        } else {
          ctx.fillStyle = "rgba(74, 222, 128, " + lf.opacity + ")";
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
          var numSub = 2 + (Math.random() > 0.7 ? 1 : 0);
          var angleSpread = 0.40 + Math.random() * 0.22;

          for (var s = 0; s < numSub; s++) {
            var dir = s === 0 ? -1 : 1;
            var newAngle = b.baseAngle + dir * (angleSpread * (0.6 + Math.random() * 0.5));
            var newLength = b.length * (0.70 + Math.random() * 0.18);
            var newWidth = b.branchWidth * 0.70;

            var newBranch = createBranch(b.currX, b.currY, newAngle, newLength, b.depth + 1, newWidth);
            branches.push(newBranch);
            b.childIndices.push(branches.length - 1);
          }

          if (b.depth >= 4) {
            leaves.push({
              branchIndex: i,
              offsetX: (Math.random() - 0.5) * 8,
              offsetY: (Math.random() - 0.5) * 8,
              radius: 1.8 + Math.random() * 2.8,
              opacity: 0,
              maxOpacity: b.depth >= 7 ? (0.09 + Math.random() * 0.07) : (0.07 + Math.random() * 0.06),
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
        lf.opacity += 0.015;
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

  window.addEventListener("DOMContentLoaded", resize);
  if (document.readyState === "complete" || document.readyState === "interactive") {
    resize();
  }
})();
