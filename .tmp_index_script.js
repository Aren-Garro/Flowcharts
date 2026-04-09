
    const state = {
      cacheKey: null,
      workflows: [],
      selectedWorkflowIds: [],
      workflowTexts: {},
      currentMermaidCode: "",
      currentWorkflowText: "",
      currentWorkflowTitle: "",
      currentNodeConfidence: [],
      currentZoom: 1,
      layoutEditMode: false,
      currentFlowchartData: null,
      manualLayout: {},
      selectedLayoutTarget: null,
      nodeEditsByWorkflow: {},
      history: [],
      loadedSourceLabel: "",
      capabilities: null,
      workflowSummary: null,
      activeUpgradeJobId: null
    };

    function $(id) { return document.getElementById(id); }

    function debounce(fn, wait) {
      let timeout;
      return function(...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => fn.apply(this, args), wait);
      };
    }


    function escapeHtml(value) {
      return String(value || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/\"/g, "&quot;")
        .replace(/'/g, "&#39;");
    }

    function resetManualLayout(options = {}) {
      state.manualLayout = {};
      state.selectedLayoutTarget = null;
      if (options.disableEditMode) {
        state.layoutEditMode = false;
      }
      syncLayoutButtons();
    }

    function cloneManualLayout(layout) {
      const source = layout && typeof layout === "object" ? layout : {};
      return JSON.parse(JSON.stringify(source));
    }

    function hasManualLayout() {
      return Object.keys(state.manualLayout || {}).length > 0;
    }

    function syncCurrentHistoryLayout() {
      const currentCode = String(state.currentMermaidCode || "");
      const entry = state.history.find((item) => String(item.code || "") === currentCode);
      if (!entry) return;
      entry.manualLayout = cloneManualLayout(state.manualLayout);
      entry.flowchartData = state.currentFlowchartData;
    }

    function getSelectedGroupName() {
      if (!state.currentFlowchartData) return "";
      if (state.selectedLayoutTarget && state.selectedLayoutTarget.kind === "group") {
        return String(state.selectedLayoutTarget.id || "");
      }
      if (state.selectedLayoutTarget && state.selectedLayoutTarget.kind === "node") {
        const node = (state.currentFlowchartData.nodes || []).find((item) => item.id === state.selectedLayoutTarget.id);
        return String((node && node.group) || "");
      }
      return "";
    }

    function getGroupedFlowchartNodes() {
      const flowchart = state.currentFlowchartData;
      const direction = String((flowchart && flowchart.direction) || "LR").toUpperCase();
      const groups = new Map();
      (flowchart && Array.isArray(flowchart.nodes) ? flowchart.nodes : []).forEach((node) => {
        const groupName = String(node.group || "");
        if (!groupName) return;
        if (!groups.has(groupName)) {
          groups.set(groupName, []);
        }
        groups.get(groupName).push({
          node,
          metric: getLayoutNodeMetrics(node, direction),
        });
      });
      return groups;
    }

    function syncLayoutButtons() {
      const selectedGroupName = getSelectedGroupName();
      const phaseReflowDisabled = !state.currentFlowchartData || !state.layoutEditMode || !selectedGroupName;
      const groupedPhaseCount = getGroupedFlowchartNodes().size;
      const allPhaseReflowDisabled = !state.currentFlowchartData || !state.layoutEditMode || groupedPhaseCount < 2;
      $("layoutEditBtn").classList.toggle("active-edit", Boolean(state.layoutEditMode));
      $("layoutEditBtn").textContent = state.layoutEditMode ? "Stop Editing" : "Edit Layout";
      $("layoutResetBtn").disabled = !state.currentFlowchartData;
      $("layoutEditBtn").disabled = !state.currentFlowchartData;
      $("layoutPhaseHorizontalBtn").disabled = phaseReflowDisabled;
      $("layoutPhaseVerticalBtn").disabled = phaseReflowDisabled;
      $("layoutAllPhasesHorizontalBtn").disabled = allPhaseReflowDisabled;
      $("layoutAllPhasesVerticalBtn").disabled = allPhaseReflowDisabled;
      $("diagramView").classList.toggle("layout-editing", Boolean(state.layoutEditMode));
      document.body.classList.toggle("layout-focus", Boolean(state.layoutEditMode));
    }

    function getLayoutNodeShape(type) {
      if (type === "decision") return "decision";
      if (type === "terminator") return "terminator";
      if (type === "io") return "io";
      return "rect";
    }

    function wrapLayoutLabel(label, maxChars = 24) {
      const words = String(label || "").replace(/<br\s*\/?>/gi, "\n").split(/\s+/);
      const lines = [];
      let current = "";
      words.forEach((word) => {
        if (!word) return;
        if (word.includes("\n")) {
          const parts = word.split("\n");
          parts.forEach((part, index) => {
            const candidate = [current, part].filter(Boolean).join(" ").trim();
            if (candidate) {
              lines.push(candidate);
            }
            current = "";
            if (index < parts.length - 1) {
              current = "";
            }
          });
          return;
        }
        const next = [current, word].filter(Boolean).join(" ").trim();
        if (next.length > maxChars && current) {
          lines.push(current);
          current = word;
        } else {
          current = next;
        }
      });
      if (current) lines.push(current);
      return lines.length ? lines : [String(label || "")];
    }

    function getBaseNodePosition(node, direction) {
      const position = Array.isArray(node.position) ? node.position : [0, 0];
      if (String(direction || "LR").toUpperCase() === "LR") {
        return { x: Number(position[1] || 0), y: Number(position[0] || 0) };
      }
      return { x: Number(position[0] || 0), y: Number(position[1] || 0) };
    }

    function getLayoutNodeMetrics(node, direction, layoutOverride = state.manualLayout) {
      const base = getBaseNodePosition(node, direction);
      const manual = layoutOverride[node.id] || {};
      const lines = wrapLayoutLabel(node.label || "", 26);
      const shape = getLayoutNodeShape(String(node.type || "process"));
      const width = shape === "decision" ? 210 : (shape === "terminator" ? 190 : 220);
      const height = Math.max(58, 28 + lines.length * 16);
      return {
        id: node.id,
        label: String(node.label || ""),
        type: String(node.type || "process"),
        group: node.group || "",
        shape,
        width,
        height,
        lines,
        x: (Number.isFinite(manual.x) ? Number(manual.x) : base.x) + 80,
        y: (Number.isFinite(manual.y) ? Number(manual.y) : base.y) + 80,
      };
    }

    function getMetricsMapForFlowchart(flowchart, layoutOverride = state.manualLayout) {
      const direction = String((flowchart && flowchart.direction) || "LR").toUpperCase();
      const metricsMap = new Map();
      (flowchart && Array.isArray(flowchart.nodes) ? flowchart.nodes : []).forEach((node) => {
        metricsMap.set(node.id, getLayoutNodeMetrics(node, direction, layoutOverride));
      });
      return metricsMap;
    }

    function createSvgEl(name, attrs = {}) {
      const el = document.createElementNS("http://www.w3.org/2000/svg", name);
      Object.entries(attrs).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          el.setAttribute(key, String(value));
        }
      });
      return el;
    }

    function overlapAmount(aStart, aEnd, bStart, bEnd) {
      return Math.max(0, Math.min(aEnd, bEnd) - Math.max(aStart, bStart));
    }

    function rectOverlap(first, second) {
      const overlapX = overlapAmount(first.x, first.x + first.width, second.x, second.x + second.width);
      const overlapY = overlapAmount(first.y, first.y + first.height, second.y, second.y + second.height);
      return { overlapX, overlapY, collides: overlapX > 0 && overlapY > 0 };
    }

    function getNodeAnchor(metrics, side) {
      if (side === "left") return { x: metrics.x, y: metrics.y + metrics.height / 2 };
      if (side === "right") return { x: metrics.x + metrics.width, y: metrics.y + metrics.height / 2 };
      return { x: metrics.x + metrics.width / 2, y: metrics.y + metrics.height / 2 };
    }

    function connectionPath(fromMetrics, toMetrics) {
      const from = getNodeAnchor(fromMetrics, fromMetrics.x <= toMetrics.x ? "right" : "left");
      const to = getNodeAnchor(toMetrics, fromMetrics.x <= toMetrics.x ? "left" : "right");
      const delta = Math.max(40, Math.abs(to.x - from.x) * 0.45);
      return {
        d: `M ${from.x} ${from.y} C ${from.x + delta} ${from.y}, ${to.x - delta} ${to.y}, ${to.x} ${to.y}`,
        midX: (from.x + to.x) / 2,
        midY: (from.y + to.y) / 2,
      };
    }

    function setSelectedLayoutTarget(target) {
      state.selectedLayoutTarget = target || null;
    }

    function getGroupNodeIds(flowchart, groupName) {
      return (flowchart && Array.isArray(flowchart.nodes) ? flowchart.nodes : [])
        .filter((node) => String(node.group || "") === String(groupName || ""))
        .map((node) => node.id);
    }

    function applyLayoutDelta(target, deltaX, deltaY) {
      const flowchart = state.currentFlowchartData;
      if (!flowchart || !target || (!deltaX && !deltaY)) return;
      let nodeIds = [];
      if (target.kind === "group") {
        nodeIds = getGroupNodeIds(flowchart, target.id);
      } else if (target.kind === "node" && target.id) {
        nodeIds = [target.id];
      }
      nodeIds.forEach((nodeId) => {
        const node = flowchart.nodes.find((candidate) => candidate.id === nodeId);
        if (!node) return;
        const base = getBaseNodePosition(node, String(flowchart.direction || "LR").toUpperCase());
        const current = state.manualLayout[nodeId] || { x: base.x, y: base.y };
        state.manualLayout[nodeId] = {
          x: Math.round(current.x + deltaX),
          y: Math.round(current.y + deltaY),
        };
      });
      syncCurrentHistoryLayout();
    }

    function reflowSelectedPhase(orientation) {
      const flowchart = state.currentFlowchartData;
      const groupName = getSelectedGroupName();
      if (!flowchart || !groupName) return false;
      const direction = String(flowchart.direction || "LR").toUpperCase();
      const groupNodes = (flowchart.nodes || []).filter((node) => String(node.group || "") === groupName);
      if (groupNodes.length < 2) return false;

      const metrics = groupNodes.map((node) => ({
        node,
        metric: getLayoutNodeMetrics(node, direction),
      }));
      const sorted = metrics.sort((left, right) => {
        if (String(orientation || "horizontal") === "horizontal") {
          if (left.metric.y !== right.metric.y) return left.metric.y - right.metric.y;
          return left.metric.x - right.metric.x;
        }
        if (left.metric.x !== right.metric.x) return left.metric.x - right.metric.x;
        return left.metric.y - right.metric.y;
      });

      const minX = Math.min(...sorted.map((item) => item.metric.x));
      const minY = Math.min(...sorted.map((item) => item.metric.y));
      const maxX = Math.max(...sorted.map((item) => item.metric.x + item.metric.width));
      const maxY = Math.max(...sorted.map((item) => item.metric.y + item.metric.height));
      const centerX = (minX + maxX) / 2;
      const centerY = (minY + maxY) / 2;
      const gap = 56;
      const isHorizontal = String(orientation || "horizontal") === "horizontal";
      const totalPrimary = sorted.reduce((sum, item) => {
        return sum + (isHorizontal ? item.metric.width : item.metric.height);
      }, 0) + gap * Math.max(0, sorted.length - 1);
      let cursor = (isHorizontal ? centerX : centerY) - (totalPrimary / 2);

      sorted.forEach((entry) => {
        const width = entry.metric.width;
        const height = entry.metric.height;
        const nextX = isHorizontal ? cursor : (centerX - width / 2);
        const nextY = isHorizontal ? (centerY - height / 2) : cursor;
        state.manualLayout[entry.node.id] = {
          x: Math.round(nextX - 80),
          y: Math.round(nextY - 80),
        };
        cursor += (isHorizontal ? width : height) + gap;
      });
      syncCurrentHistoryLayout();
      return true;
    }

    function reflowAllPhases(orientation) {
      const groups = Array.from(getGroupedFlowchartNodes().entries());
      if (groups.length < 2) return false;

      const isHorizontal = String(orientation || "horizontal") === "horizontal";
      const phaseGap = 120;
      const sortedGroups = groups.map(([groupName, entries]) => {
        const minX = Math.min(...entries.map((entry) => entry.metric.x));
        const minY = Math.min(...entries.map((entry) => entry.metric.y));
        const maxX = Math.max(...entries.map((entry) => entry.metric.x + entry.metric.width));
        const maxY = Math.max(...entries.map((entry) => entry.metric.y + entry.metric.height));
        return {
          groupName,
          entries,
          minX,
          minY,
          maxX,
          maxY,
          width: maxX - minX,
          height: maxY - minY,
          centerX: (minX + maxX) / 2,
          centerY: (minY + maxY) / 2,
        };
      }).sort((left, right) => {
        if (isHorizontal) {
          if (left.centerY !== right.centerY) return left.centerY - right.centerY;
          return left.centerX - right.centerX;
        }
        if (left.centerX !== right.centerX) return left.centerX - right.centerX;
        return left.centerY - right.centerY;
      });

      const minPrimary = Math.min(...sortedGroups.map((group) => isHorizontal ? group.minX : group.minY));
      const secondaryCenter = sortedGroups.reduce((sum, group) => {
        return sum + (isHorizontal ? group.centerY : group.centerX);
      }, 0) / sortedGroups.length;
      let cursor = minPrimary;

      sortedGroups.forEach((group) => {
        const nextMinX = isHorizontal ? cursor : Math.round(secondaryCenter - (group.width / 2));
        const nextMinY = isHorizontal ? Math.round(secondaryCenter - (group.height / 2)) : cursor;
        group.entries.forEach((entry) => {
          const offsetX = entry.metric.x - group.minX;
          const offsetY = entry.metric.y - group.minY;
          state.manualLayout[entry.node.id] = {
            x: Math.round(nextMinX + offsetX - 80),
            y: Math.round(nextMinY + offsetY - 80),
          };
        });
        cursor += (isHorizontal ? group.width : group.height) + phaseGap;
      });

      syncCurrentHistoryLayout();
      return true;
    }

    function buildPolishedExportLayout() {
      const flowchart = state.currentFlowchartData;
      if (!flowchart || !Array.isArray(flowchart.nodes) || !flowchart.nodes.length) {
        return cloneManualLayout(state.manualLayout);
      }

      const polishedLayout = cloneManualLayout(state.manualLayout);
      const direction = String(flowchart.direction || "LR").toUpperCase();
      const getGroupBoxes = () => {
        const metricsMap = getMetricsMapForFlowchart(flowchart, polishedLayout);
        const grouped = new Map();
        (flowchart.nodes || []).forEach((node) => {
          const groupName = String(node.group || "");
          if (!groupName) return;
          if (!grouped.has(groupName)) grouped.set(groupName, []);
          const metric = metricsMap.get(node.id);
          if (metric) grouped.get(groupName).push({ node, metric });
        });
        return { metricsMap, grouped };
      };

      const shiftNode = (nodeId, deltaX, deltaY) => {
        const node = flowchart.nodes.find((candidate) => candidate.id === nodeId);
        if (!node) return;
        const base = getBaseNodePosition(node, direction);
        const current = polishedLayout[nodeId] || { x: base.x, y: base.y };
        polishedLayout[nodeId] = {
          x: Math.round(current.x + deltaX),
          y: Math.round(current.y + deltaY),
        };
      };

      const clusterByAxis = (entries, axis, threshold) => {
        const sorted = entries.slice().sort((left, right) => left.metric[axis] - right.metric[axis]);
        const clusters = [];
        sorted.forEach((entry) => {
          const value = entry.metric[axis];
          const last = clusters[clusters.length - 1];
          if (!last || Math.abs(value - last.anchor) > threshold) {
            clusters.push({ anchor: value, items: [entry] });
            return;
          }
          last.items.push(entry);
          last.anchor = last.items.reduce((sum, item) => sum + item.metric[axis], 0) / last.items.length;
        });
        return clusters;
      };

      const normalizeGroupLanes = (entries) => {
        if (entries.length < 2) return;
        const minX = Math.min(...entries.map((entry) => entry.metric.x));
        const maxX = Math.max(...entries.map((entry) => entry.metric.x + entry.metric.width));
        const minY = Math.min(...entries.map((entry) => entry.metric.y));
        const maxY = Math.max(...entries.map((entry) => entry.metric.y + entry.metric.height));
        const horizontalDominant = (maxX - minX) >= (maxY - minY);

        if (horizontalDominant) {
          const rowClusters = clusterByAxis(entries, "y", 96);
          let rowCursor = minY;
          rowClusters.forEach((cluster) => {
            const rowHeight = Math.max(...cluster.items.map((item) => item.metric.height));
            const rowCenterY = rowCursor + rowHeight / 2;
            const sortedRow = cluster.items.slice().sort((left, right) => left.metric.x - right.metric.x);
            let xCursor = minX;
            sortedRow.forEach((entry, index) => {
              if (index > 0) {
                xCursor += 72;
              }
              const targetX = xCursor;
              const targetY = rowCenterY - entry.metric.height / 2;
              shiftNode(entry.node.id, targetX - entry.metric.x, targetY - entry.metric.y);
              entry.metric.x = targetX;
              entry.metric.y = targetY;
              xCursor += entry.metric.width;
            });
            rowCursor += rowHeight + 54;
          });
          return;
        }

        const columnClusters = clusterByAxis(entries, "x", 120);
        let columnCursor = minX;
        columnClusters.forEach((cluster) => {
          const columnWidth = Math.max(...cluster.items.map((item) => item.metric.width));
          const columnCenterX = columnCursor + columnWidth / 2;
          const sortedColumn = cluster.items.slice().sort((left, right) => left.metric.y - right.metric.y);
          let yCursor = minY;
          sortedColumn.forEach((entry, index) => {
            if (index > 0) {
              yCursor += 46;
            }
            const targetX = columnCenterX - entry.metric.width / 2;
            const targetY = yCursor;
            shiftNode(entry.node.id, targetX - entry.metric.x, targetY - entry.metric.y);
            entry.metric.x = targetX;
            entry.metric.y = targetY;
            yCursor += entry.metric.height;
          });
          columnCursor += columnWidth + 68;
        });
      };

      const { grouped } = getGroupBoxes();
      grouped.forEach((entries) => {
        if (entries.length < 2) return;
        normalizeGroupLanes(entries);
        const minX = Math.min(...entries.map((entry) => entry.metric.x));
        const maxX = Math.max(...entries.map((entry) => entry.metric.x + entry.metric.width));
        const minY = Math.min(...entries.map((entry) => entry.metric.y));
        const maxY = Math.max(...entries.map((entry) => entry.metric.y + entry.metric.height));
        const horizontalDominant = (maxX - minX) >= (maxY - minY);
        const sorted = entries.slice().sort((left, right) => {
          if (horizontalDominant) {
            if (left.metric.x !== right.metric.x) return left.metric.x - right.metric.x;
            return left.metric.y - right.metric.y;
          }
          if (left.metric.y !== right.metric.y) return left.metric.y - right.metric.y;
          return left.metric.x - right.metric.x;
        });

        for (let index = 1; index < sorted.length; index += 1) {
          const previous = sorted[index - 1].metric;
          const current = sorted[index].metric;
          if (horizontalDominant) {
            const crossOverlap = overlapAmount(previous.y, previous.y + previous.height, current.y, current.y + current.height);
            if (crossOverlap > Math.min(previous.height, current.height) * 0.28) {
              const requiredX = previous.x + previous.width + 46;
              if (current.x < requiredX) {
                shiftNode(sorted[index].node.id, requiredX - current.x, 0);
                sorted[index].metric.x = requiredX;
              }
            }
          } else {
            const crossOverlap = overlapAmount(previous.x, previous.x + previous.width, current.x, current.x + current.width);
            if (crossOverlap > Math.min(previous.width, current.width) * 0.24) {
              const requiredY = previous.y + previous.height + 38;
              if (current.y < requiredY) {
                shiftNode(sorted[index].node.id, 0, requiredY - current.y);
                sorted[index].metric.y = requiredY;
              }
            }
          }
        }
      });

      for (let pass = 0; pass < 2; pass += 1) {
        const { grouped: passGroups } = getGroupBoxes();
        const groupBoxes = Array.from(passGroups.entries()).map(([groupName, entries]) => {
          const minX = Math.min(...entries.map((entry) => entry.metric.x)) - 28;
          const minY = Math.min(...entries.map((entry) => entry.metric.y)) - 42;
          const maxX = Math.max(...entries.map((entry) => entry.metric.x + entry.metric.width)) + 28;
          const maxY = Math.max(...entries.map((entry) => entry.metric.y + entry.metric.height)) + 28;
          return { groupName, entries, minX, minY, maxX, maxY, width: maxX - minX, height: maxY - minY };
        });
        if (groupBoxes.length < 2) break;

        const spreadX = Math.max(...groupBoxes.map((box) => box.maxX)) - Math.min(...groupBoxes.map((box) => box.minX));
        const spreadY = Math.max(...groupBoxes.map((box) => box.maxY)) - Math.min(...groupBoxes.map((box) => box.minY));
        const horizontalDominant = spreadX >= spreadY;
        const sortedGroups = groupBoxes.sort((left, right) => {
          if (horizontalDominant) {
            if (left.minX !== right.minX) return left.minX - right.minX;
            return left.minY - right.minY;
          }
          if (left.minY !== right.minY) return left.minY - right.minY;
          return left.minX - right.minX;
        });

        for (let index = 1; index < sortedGroups.length; index += 1) {
          const previous = sortedGroups[index - 1];
          const current = sortedGroups[index];
          if (horizontalDominant) {
            const crossOverlap = overlapAmount(previous.minY, previous.maxY, current.minY, current.maxY);
            if (crossOverlap > 46) {
              const requiredX = previous.maxX + 92;
              if (current.minX < requiredX) {
                const deltaX = requiredX - current.minX;
                current.entries.forEach((entry) => shiftNode(entry.node.id, deltaX, 0));
                current.minX += deltaX;
                current.maxX += deltaX;
              }
            }
          } else {
            const crossOverlap = overlapAmount(previous.minX, previous.maxX, current.minX, current.maxX);
            if (crossOverlap > 120) {
              const requiredY = previous.maxY + 76;
              if (current.minY < requiredY) {
                const deltaY = requiredY - current.minY;
                current.entries.forEach((entry) => shiftNode(entry.node.id, 0, deltaY));
                current.minY += deltaY;
                current.maxY += deltaY;
              }
            }
          }
        }
      }

      const { grouped: bandGroups } = getGroupBoxes();
      const bandBoxes = Array.from(bandGroups.entries()).map(([groupName, entries]) => {
        const minX = Math.min(...entries.map((entry) => entry.metric.x)) - 28;
        const minY = Math.min(...entries.map((entry) => entry.metric.y)) - 42;
        const maxX = Math.max(...entries.map((entry) => entry.metric.x + entry.metric.width)) + 28;
        const maxY = Math.max(...entries.map((entry) => entry.metric.y + entry.metric.height)) + 28;
        return { groupName, entries, minX, minY, maxX, maxY, width: maxX - minX, height: maxY - minY };
      }).sort((left, right) => {
        if (direction === "LR") {
          if (left.minY !== right.minY) return left.minY - right.minY;
          return left.minX - right.minX;
        }
        if (left.minX !== right.minX) return left.minX - right.minX;
        return left.minY - right.minY;
      });

      if (bandBoxes.length > 1) {
        if (direction === "LR") {
          let bandCursor = bandBoxes[0].minY;
          bandBoxes.forEach((band, index) => {
            if (index === 0) {
              bandCursor = band.maxY + 86;
              return;
            }
            if (band.minY < bandCursor) {
              const deltaY = bandCursor - band.minY;
              band.entries.forEach((entry) => shiftNode(entry.node.id, 0, deltaY));
              band.minY += deltaY;
              band.maxY += deltaY;
            }
            bandCursor = band.maxY + 86;
          });
        } else {
          let bandCursor = bandBoxes[0].minX;
          bandBoxes.forEach((band, index) => {
            if (index === 0) {
              bandCursor = band.maxX + 104;
              return;
            }
            if (band.minX < bandCursor) {
              const deltaX = bandCursor - band.minX;
              band.entries.forEach((entry) => shiftNode(entry.node.id, deltaX, 0));
              band.minX += deltaX;
              band.maxX += deltaX;
            }
            bandCursor = band.maxX + 104;
          });
        }
      }

      const globalDirectionIsHorizontal = direction === "LR";
      const collisionPadding = { x: 56, y: 44 };
      for (let pass = 0; pass < 6; pass += 1) {
        const metricsMap = getMetricsMapForFlowchart(flowchart, polishedLayout);
        const ordered = Array.from(metricsMap.values()).sort((left, right) => {
          if (globalDirectionIsHorizontal) {
            if (left.x !== right.x) return left.x - right.x;
            return left.y - right.y;
          }
          if (left.y !== right.y) return left.y - right.y;
          return left.x - right.x;
        });
        let movedThisPass = false;

        for (let index = 0; index < ordered.length; index += 1) {
          const current = ordered[index];
          for (let nextIndex = index + 1; nextIndex < ordered.length; nextIndex += 1) {
            const other = ordered[nextIndex];
            const overlap = rectOverlap(
              {
                x: current.x - collisionPadding.x / 2,
                y: current.y - collisionPadding.y / 2,
                width: current.width + collisionPadding.x,
                height: current.height + collisionPadding.y,
              },
              {
                x: other.x,
                y: other.y,
                width: other.width,
                height: other.height,
              }
            );
            if (!overlap.collides) continue;

            const pushX = overlap.overlapX + collisionPadding.x;
            const pushY = overlap.overlapY + collisionPadding.y;
            if (globalDirectionIsHorizontal) {
              if (pushX <= pushY * 1.3) {
                shiftNode(other.id, pushX, 0);
                other.x += pushX;
              } else {
                shiftNode(other.id, 0, pushY);
                other.y += pushY;
              }
            } else {
              if (pushY <= pushX * 1.3) {
                shiftNode(other.id, 0, pushY);
                other.y += pushY;
              } else {
                shiftNode(other.id, pushX, 0);
                other.x += pushX;
              }
            }
            movedThisPass = true;
          }
        }

        if (!movedThisPass) {
          break;
        }
      }

      return polishedLayout;
    }

    function getCurrentFlowchartSvgMarkup() {
      const svgEl = $("diagramView").querySelector("svg");
      if (!svgEl) return "";
      const clone = svgEl.cloneNode(true);
      if (state.currentFlowchartData && (state.layoutEditMode || hasManualLayout())) {
        const exportLayout = buildPolishedExportLayout();
        const metricsMap = getMetricsMapForFlowchart(state.currentFlowchartData, exportLayout);
        clone.querySelectorAll(".layout-node[data-node-id]").forEach((nodeEl) => {
          const nodeId = nodeEl.getAttribute("data-node-id");
          const metric = metricsMap.get(nodeId);
          if (!metric) return;
          nodeEl.setAttribute("transform", `translate(${metric.x} ${metric.y})`);
        });

        const groupedMetrics = new Map();
        metricsMap.forEach((metric) => {
          if (!metric.group) return;
          if (!groupedMetrics.has(metric.group)) groupedMetrics.set(metric.group, []);
          groupedMetrics.get(metric.group).push(metric);
        });
        clone.querySelectorAll(".layout-group-box[data-group-name]").forEach((boxEl) => {
          const groupName = boxEl.getAttribute("data-group-name") || "";
          const items = groupedMetrics.get(groupName) || [];
          if (!items.length) return;
          const minX = Math.min(...items.map((item) => item.x)) - 28;
          const minY = Math.min(...items.map((item) => item.y)) - 42;
          const maxX = Math.max(...items.map((item) => item.x + item.width)) + 28;
          const maxY = Math.max(...items.map((item) => item.y + item.height)) + 28;
          boxEl.setAttribute("x", String(minX));
          boxEl.setAttribute("y", String(minY));
          boxEl.setAttribute("width", String(maxX - minX));
          boxEl.setAttribute("height", String(maxY - minY));
        });
        clone.querySelectorAll(".layout-group-label[data-group-name]").forEach((labelEl) => {
          const groupName = labelEl.getAttribute("data-group-name") || "";
          const items = groupedMetrics.get(groupName) || [];
          if (!items.length) return;
          const minX = Math.min(...items.map((item) => item.x)) - 28;
          const minY = Math.min(...items.map((item) => item.y)) - 42;
          labelEl.setAttribute("x", String(minX + 14));
          labelEl.setAttribute("y", String(minY + 22));
        });
        (state.currentFlowchartData.connections || []).forEach((connection, index) => {
          const fromMetrics = metricsMap.get(connection.from);
          const toMetrics = metricsMap.get(connection.to);
          if (!fromMetrics || !toMetrics) return;
          const pathInfo = connectionPath(fromMetrics, toMetrics);
          const pathEl = clone.querySelector(`.layout-edges path[data-connection-index="${index}"]`);
          if (pathEl) {
            pathEl.setAttribute("d", pathInfo.d);
          }
          const labelEl = clone.querySelector(`.layout-edges text[data-connection-index="${index}"]`);
          if (labelEl) {
            labelEl.setAttribute("x", String(pathInfo.midX));
            labelEl.setAttribute("y", String(pathInfo.midY - 8));
          }
        });
      }
      clone.removeAttribute("style");
      const baseViewBox = clone.getAttribute("viewBox");
      let minX = 0;
      let minY = 0;
      let width = 0;
      let height = 0;
      if (baseViewBox) {
        const parts = baseViewBox.split(/\s+/).map((value) => Number(value));
        if (parts.length === 4 && parts.every((value) => Number.isFinite(value))) {
          [minX, minY, width, height] = parts;
        }
      }
      if (!width || !height) {
        const box = svgEl.viewBox && svgEl.viewBox.baseVal
          ? svgEl.viewBox.baseVal
          : { x: 0, y: 0, width: svgEl.clientWidth || 1600, height: svgEl.clientHeight || 1200 };
        minX = Number(box.x || 0);
        minY = Number(box.y || 0);
        width = Number(box.width || 1600);
        height = Number(box.height || 1200);
      }
      const padding = Math.max(36, Math.round(Math.min(width, height) * 0.03));
      clone.setAttribute("viewBox", `${minX - padding} ${minY - padding} ${width + padding * 2} ${height + padding * 2}`);
      clone.setAttribute("width", String(Math.round(width + padding * 2)));
      clone.setAttribute("height", String(Math.round(height + padding * 2)));
      clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
      const bg = createSvgEl("rect", {
        x: minX - padding,
        y: minY - padding,
        width: width + padding * 2,
        height: height + padding * 2,
        fill: "#ffffff",
      });
      clone.insertBefore(bg, clone.firstChild);
      return new XMLSerializer().serializeToString(clone);
    }

    function svgMarkupToPngBlob(svgMarkup) {
      return new Promise((resolve, reject) => {
        if (!svgMarkup) {
          reject(new Error("No rendered SVG available yet."));
          return;
        }
        const svgBlob = new Blob([svgMarkup], { type: "image/svg+xml;charset=utf-8" });
        const url = URL.createObjectURL(svgBlob);
        const img = new Image();
        img.onload = () => {
          const parser = new DOMParser();
          const doc = parser.parseFromString(svgMarkup, "image/svg+xml");
          const svgRoot = doc.documentElement;
          let exportWidth = Number(svgRoot.getAttribute("width") || 0);
          let exportHeight = Number(svgRoot.getAttribute("height") || 0);
          if ((!exportWidth || !exportHeight) && svgRoot.hasAttribute("viewBox")) {
            const parts = svgRoot.getAttribute("viewBox").split(/\s+/).map((value) => Number(value));
            if (parts.length === 4 && parts.every((value) => Number.isFinite(value))) {
              exportWidth = parts[2];
              exportHeight = parts[3];
            }
          }
          exportWidth = Math.max(1, exportWidth || img.width || 1600);
          exportHeight = Math.max(1, exportHeight || img.height || 1000);
          const targetMax = 4200;
          const scale = Math.min(1.75, targetMax / Math.max(exportWidth, exportHeight));
          const width = Math.max(1, Math.round(exportWidth * scale));
          const height = Math.max(1, Math.round(exportHeight * scale));
          const canvas = document.createElement("canvas");
          canvas.width = width;
          canvas.height = height;
          const ctx = canvas.getContext("2d");
          ctx.fillStyle = "#ffffff";
          ctx.fillRect(0, 0, width, height);
          ctx.drawImage(img, 0, 0, width, height);
          canvas.toBlob((blob) => {
            URL.revokeObjectURL(url);
            if (!blob) {
              reject(new Error("Could not rasterize the current diagram."));
              return;
            }
            resolve(blob);
          }, "image/png");
        };
        img.onerror = () => {
          URL.revokeObjectURL(url);
          reject(new Error("Could not load the current diagram for export."));
        };
        img.src = url;
      });
    }

    function toast(message, level = "good") {
      const wrap = $("toastWrap");
      const t = document.createElement("div");
      t.className = "toast " + (level || "good");
      t.textContent = message;
      wrap.appendChild(t);
      window.setTimeout(() => t.remove(), 3600);
    }

    function toggleHistory() {
      $("historyDrawer").classList.toggle("open");
    }

    function toggleAdvanced() {
      $("advancedCard").classList.toggle("show");
    }

    /* ── Phase 2: Guided UI Logic ── */
    function closeOnboarding() {
      $("onboardingOverlay").classList.remove("show");
      localStorage.setItem("flowchart_onboarded", "true");
    }

    function updateStepper(stepNum) {
      for (let i = 1; i <= 3; i++) {
        const el = $("step" + i);
        el.classList.remove("active", "done");
        if (i < stepNum) el.classList.add("done");
        if (i === stepNum) el.classList.add("active");
      }
    }

    function showTab(which) {
      const isDiagram = which === "diagram";
      $("diagramTab").classList.toggle("active", isDiagram);
      $("codeTab").classList.toggle("active", !isDiagram);
      $("diagramView").style.display = isDiagram ? "flex" : "none";
      $("codeView").style.display = isDiagram ? "none" : "block";
      if (isDiagram && !state.currentMermaidCode) {
        $("emptyState").style.display = "flex";
      } else {
        $("emptyState").style.display = "none";
      }
    }

    function updateProgress(show, pct = 0, msg = "Working...") {
      const box = $("progressBox");
      box.classList.toggle("show", Boolean(show));
      $("progressFill").style.width = Math.max(0, Math.min(100, Number(pct))) + "%";
      $("progressMsg").textContent = msg;
    }

    function setWorkflowSelection(ids) {
      const availableIds = new Set(state.workflows.map((wf) => wf.id));
      const next = ids.filter((id) => availableIds.has(id));
      if (!next.length && state.workflows.length) {
        next.push(state.workflows[0].id);
      }
      state.selectedWorkflowIds = Array.from(new Set(next));
      state.currentNodeConfidence = [];
      renderNodeReview([]);
      renderWorkflowCards();
      $("batchBtn").style.display = state.selectedWorkflowIds.length > 1 ? "inline-block" : "none";
      // NEW: Update main button text if merging
      $("generateBtn").textContent = state.selectedWorkflowIds.length > 1 ? "Generate Flowchart (Merged)" : "Generate Flowchart";
    }

    function showWorkflowSection() {
      $("workflowSection").style.display = "block";
    }

    function clearWorkflowState() {
      state.cacheKey = null;
      state.workflows = [];
      state.selectedWorkflowIds = [];
      state.workflowTexts = {};
      state.workflowSummary = null;
      state.currentNodeConfidence = [];
      state.currentWorkflowText = "";
      state.currentWorkflowTitle = "";
      state.currentFlowchartData = null;
      resetManualLayout({ disableEditMode: true });
      $("workflowList").innerHTML = "";
      $("statsRow").innerHTML = "";
      $("workflowSection").style.display = "none";
      renderNodeReview([]);
    }

    function renderStats(stats) {
      if (!stats) {
        $("statsRow").innerHTML = "";
        return;
      }
      const html = [
        `<div class="stat-box"><div class="value">${Number(stats.total_workflows || 0)}</div><div class="label">Detected</div></div>`,
        `<div class="stat-box"><div class="value">${Number(state.selectedWorkflowIds.length || 0)}</div><div class="label">Selected</div></div>`,
        `<div class="stat-box"><div class="value">${Number(stats.total_steps || 0)}</div><div class="label">Total Steps</div></div>`,
        `<div class="stat-box"><div class="value">${Number(stats.avg_confidence || 0).toFixed(2)}</div><div class="label">Avg Confidence</div></div>`
      ].join("");
      $("statsRow").innerHTML = html;
    }

    function renderWorkflowCards() {
      const list = $("workflowList");
      if (!state.workflows.length) {
        list.innerHTML = `<div style="font-size:12px;color:#334155;">No workflows detected yet.</div>`;
        return;
      }
      list.innerHTML = state.workflows.map((wf) => {
        const selected = state.selectedWorkflowIds.includes(wf.id);
        return `
          <div class="workflow-item ${selected ? "active" : ""}" data-wf-id="${escapeHtml(wf.id)}">
            <div class="title">
              <span>${escapeHtml(wf.title || wf.id)}</span>
              <span class="pick-pill">${selected ? "Selected" : "Pick"}</span>
            </div>
            <div class="meta">
              <span>${Number(wf.step_count || 0)} steps</span>
              <span>${Number(wf.decision_count || 0)} decisions</span>
              <span>confidence ${Number(wf.confidence || 0).toFixed(2)}</span>
            </div>
          </div>
        `;
      }).join("");

      list.querySelectorAll(".workflow-item").forEach((el) => {
        el.addEventListener("click", () => {
          const wfId = el.getAttribute("data-wf-id");
          if (!wfId) return;
          toggleWorkflowSelection(wfId);
        });
      });

      renderStats(state.workflowSummary || summarizeWorkflows(state.workflows));
    }

    function toggleWorkflowSelection(workflowId) {
      const current = state.selectedWorkflowIds.slice();
      const idx = current.indexOf(workflowId);
      if (idx >= 0) {
        if (current.length === 1) {
          return;
        }
        current.splice(idx, 1);
        setWorkflowSelection(current);
        return;
      }
      current.push(workflowId);
      setWorkflowSelection(current);
    }

    function summarizeWorkflows(workflows) {
      const totalSteps = workflows.reduce((sum, wf) => sum + Number(wf.step_count || 0), 0);
      const avgConfidence = workflows.length
        ? workflows.reduce((sum, wf) => sum + Number(wf.confidence || 0), 0) / workflows.length
        : 0;
      return {
        total_workflows: workflows.length,
        total_steps: totalSteps,
        avg_confidence: avgConfidence
      };
    }

    function normalizeSingleWorkflowData(data, sourceLabel) {
      const label = sourceLabel || "Workflow";
      return {
        cache_key: data.cache_key || null,
        workflows: [{
          id: "single_workflow",
          title: label,
          step_count: data.summary && data.summary.step_count ? data.summary.step_count : 0,
          decision_count: data.summary && data.summary.decision_points ? data.summary.decision_points : 0,
          confidence: 1
        }],
        summary: {
          total_workflows: 1,
          total_steps: data.summary && data.summary.step_count ? data.summary.step_count : 0,
          avg_confidence: 1
        },
        workflow_text: data.workflow_text || ""
      };
    }

    function applyWorkflowDetection(data, sourceLabel) {
      if (!data) return;
      const hasWorkflows = Array.isArray(data.workflows) && data.workflows.length > 0;
      const finalData = hasWorkflows ? data : normalizeSingleWorkflowData(data, sourceLabel);
      if (!finalData.workflows || !finalData.workflows.length) {
        throw new Error("No workflows were detected from this source.");
      }

      clearWorkflowState();
      state.cacheKey = finalData.cache_key || null;
      state.workflows = finalData.workflows.slice();
      state.loadedSourceLabel = sourceLabel || "";
      state.workflowSummary = finalData.summary || summarizeWorkflows(finalData.workflows);
      if (finalData.workflow_text) {
        state.workflowTexts.single_workflow = finalData.workflow_text;
      }

      showWorkflowSection();
      renderWorkflowCards();
      setWorkflowSelection([finalData.workflows[0].id]);
      updateStepper(2);
      const count = finalData.workflows.length;
      toast(`Detected ${count} workflow${count === 1 ? "" : "s"}.`, "good");
    }

    async function readJsonResponse(res) {
      let data = null;
      try {
        data = await res.json();
      } catch (error) {
        data = null;
      }
      if (!res.ok) {
        const detail = data && data.error ? data.error : `Request failed (${res.status})`;
        throw new Error(detail);
      }
      if (data && data.success === false && data.error) {
        throw new Error(data.error);
      }
      return data || {};
    }

    async function postJson(url, payload) {
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload || {})
      });
      return readJsonResponse(res);
    }

    async function loadWorkflowText(workflowId) {
      if (!workflowId) return "";
      if (state.workflowTexts[workflowId]) return state.workflowTexts[workflowId];
      if (workflowId === "single_workflow") {
        const inlineText = $("textInput").value.trim();
        state.workflowTexts[workflowId] = inlineText;
        return inlineText;
      }
      if (!state.cacheKey) return "";
      const res = await fetch(`/api/workflow/${encodeURIComponent(state.cacheKey)}/${encodeURIComponent(workflowId)}`);
      const data = await readJsonResponse(res);
      const text = String(data.workflow_text || "");
      state.workflowTexts[workflowId] = text;
      return text;
    }

    async function runTextDetection(rawText, sourceLabel) {
      const text = String(rawText || "").trim();
      if (!text) {
        throw new Error("Please paste workflow text first.");
      }
      updateProgress(true, 20, "Analyzing pasted workflow text...");
      const data = await postJson("/api/clipboard", { text: text });
      updateProgress(true, 85, "Building detected workflow list...");
      applyWorkflowDetection(data, sourceLabel || "Pasted Text");
      updateProgress(false);
    }

    async function runUrlDetection() {
      const rawUrl = $("urlInput").value.trim();
      if (!rawUrl) {
        throw new Error("Please enter a URL.");
      }
      updateProgress(true, 18, "Fetching process content from URL...");
      const data = await postJson("/api/fetch-url", { url: rawUrl });
      updateProgress(true, 88, "Detecting workflows from fetched content...");
      applyWorkflowDetection(data, data.source || rawUrl);
      if (data.workflow_text) {
        $("textInput").value = data.workflow_text;
      }
      updateProgress(false);
    }

    async function runFileDetection(file) {
      if (!file) {
        throw new Error("Please select a document first.");
      }
      updateProgress(true, 15, `Uploading ${file.name}...`);
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch("/api/upload", { method: "POST", body: formData });
      const data = await readJsonResponse(res);
      updateProgress(true, 90, "Detecting workflows in uploaded file...");
      applyWorkflowDetection(data, file.name);
      updateProgress(false);
    }

    async function loadSelectedSample() {
      const sampleId = $("sampleSelect").value;
      if (!sampleId) {
        throw new Error("Please choose a sample first.");
      }
      updateProgress(true, 15, "Loading sample workflow...");
      const res = await fetch(`/api/samples/${encodeURIComponent(sampleId)}`);
      const data = await readJsonResponse(res);
      const sampleText = String(data.text || "");
      $("textInput").value = sampleText;
      updateProgress(true, 55, "Running workflow detection on sample...");
      await runTextDetection(sampleText, data.title || "Sample Workflow");
      updateProgress(false);
    }

    function getSelectedWorkflowId() {
      if (state.selectedWorkflowIds.length) {
        return state.selectedWorkflowIds[0];
      }
      if (state.workflows.length) {
        return state.workflows[0].id;
      }
      return null;
    }

    function getWorkflowById(workflowId) {
      return state.workflows.find((wf) => wf.id === workflowId) || null;
    }

    function getStylePresetTheme() {
      const preset = $("stylePresetSelect").value;
      if (preset === "clean") return "neutral";
      if (preset === "presentation") return "default";
      return "default";
    }

    function buildStructuredWorkflowSegment(workflowId, workflowText, orderIndex, totalCount) {
      const text = String(workflowText || "").trim();
      if (!text) return "";
      if (totalCount <= 1) return text;

      const workflow = getWorkflowById(workflowId);
      const rawTitle = workflow && workflow.title ? String(workflow.title).trim() : `Phase ${orderIndex + 1}`;
      const heading = /^(phase|stage|section)\b/i.test(rawTitle)
        ? rawTitle
        : `Phase ${orderIndex + 1}: ${rawTitle}`;
      return `${heading}\n${text}`;
    }

    function getCurrentNodeEdits() {
      const workflowId = getSelectedWorkflowId();
      if (!workflowId) return [];
      const editsMap = state.nodeEditsByWorkflow[workflowId] || {};
      return Object.keys(editsMap).map((nodeId) => {
        const item = editsMap[nodeId] || {};
        return {
          id: nodeId,
          type: item.type,
          label: item.label,
          confidence: item.confidence
        };
      });
    }

    function getNodeEditsForWorkflow(workflowId) {
      if (!workflowId) return {};
      if (!state.nodeEditsByWorkflow[workflowId]) {
        state.nodeEditsByWorkflow[workflowId] = {};
      }
      return state.nodeEditsByWorkflow[workflowId];
    }

    function setNodeEdit(workflowId, nodeId, patch) {
      if (!workflowId || !nodeId) return;
      const edits = getNodeEditsForWorkflow(workflowId);
      const current = edits[nodeId] || {};
      edits[nodeId] = {
        type: patch.type !== undefined ? patch.type : current.type,
        label: patch.label !== undefined ? patch.label : current.label,
        confidence: patch.confidence !== undefined ? patch.confidence : current.confidence
      };
    }

    function resetNodeEdits(workflowId) {
      if (!workflowId) return;
      state.nodeEditsByWorkflow[workflowId] = {};
    }

    function getNodeTypeOptions(currentType) {
      const types = [
        "process",
        "decision",
        "io",
        "database",
        "display",
        "document",
        "predefined",
        "manual",
        "connector",
        "terminator"
      ];
      return types.map((type) => {
        const selected = String(type) === String(currentType) ? "selected" : "";
        return `<option value="${type}" ${selected}>${type}</option>`;
      }).join("");
    }

    function renderNodeReview(nodes) {
      const card = $("reviewCard");
      const list = $("reviewList");
      const workflowId = getSelectedWorkflowId();
      const safeNodes = Array.isArray(nodes) ? nodes : [];
      if (!workflowId || !safeNodes.length) {
        card.classList.remove("show");
        list.innerHTML = "";
        return;
      }

      const edits = getNodeEditsForWorkflow(workflowId);
      const editable = safeNodes.filter((node) => {
        const nodeId = String(node.id || "").toLowerCase();
        return nodeId !== "start" && nodeId !== "end";
      });
      if (!editable.length) {
        card.classList.remove("show");
        list.innerHTML = "";
        return;
      }

      list.innerHTML = editable.map((node) => {
        const nodeId = String(node.id || "");
        const edit = edits[nodeId] || {};
        const label = edit.label !== undefined ? edit.label : String(node.label || "");
        const type = edit.type !== undefined ? edit.type : String(node.type || "process");
        const confidence = Math.round((Number(node.confidence || 0)) * 100);
        const needsReview = confidence < 80;
        return `
          <div class="review-item" data-node-id="${escapeHtml(nodeId)}">
            <div class="review-row">
              <input type="text" value="${escapeHtml(label)}" data-role="label" aria-label="Node label ${escapeHtml(nodeId)}">
              <select data-role="type" aria-label="Node type ${escapeHtml(nodeId)}">${getNodeTypeOptions(type)}</select>
              <div class="confidence-chip">${confidence}%</div>
            </div>
            <div style="font-size:11px;color:#334155;">${needsReview ? "Low confidence. Consider editing this node." : "Confidence looks good."}</div>
          </div>
        `;
      }).join("");

      card.classList.add("show");
      list.querySelectorAll(".review-item").forEach((item) => {
        const nodeId = item.getAttribute("data-node-id");
        const labelInput = item.querySelector('input[data-role="label"]');
        const typeSelect = item.querySelector('select[data-role="type"]');
        if (labelInput) {
          labelInput.addEventListener("change", () => {
            setNodeEdit(workflowId, nodeId, { label: labelInput.value.trim() || nodeId, confidence: 1 });
          });
        }
        if (typeSelect) {
          typeSelect.addEventListener("change", () => {
            setNodeEdit(workflowId, nodeId, { type: typeSelect.value, confidence: 1 });
          });
        }
      });
    }

    function normalizeExtractionForApi(value) {
      const raw = String(value || "auto").toLowerCase();
      if (raw === "rules" || raw === "spacy") return "heuristic";
      if (raw === "llm") return "local-llm";
      return raw;
    }

    function buildGeneratePayload(workflowText, workflowId) {
      const selectedWorkflow = getWorkflowById(workflowId);
      const detectionConfidence = selectedWorkflow ? Number(selectedWorkflow.confidence || 0) : null;
      return {
        workflow_text: workflowText,
        title: selectedWorkflow && selectedWorkflow.title ? selectedWorkflow.title : "Workflow",
        theme: $("themeSelect").value || getStylePresetTheme(),
        direction: $("directionSelect").value || "LR",
        validate: true,
        ux_mode: "simple",
        extraction: normalizeExtractionForApi($("extractionSelect").value || "rules"),
        renderer: $("rendererSelect").value || "graphviz",
        quality_mode: $("qualityModeSelect").value || "draft_allowed",
        min_detection_confidence_certified: Number($("certMinInput").value || 0.65),
        model_path: $("modelPathInput").value.trim() || null,
        ollama_base_url: $("ollamaBaseInput").value.trim() || "http://localhost:11434",
        ollama_model: $("ollamaModelSelect").value || null,
        detection_confidence: Number.isFinite(detectionConfidence) ? detectionConfidence : null,
        node_overrides: getCurrentNodeEdits(),
        response_mode: $("twoPassToggle").value || "two_pass",
        request_timeout_ms: Number($("timeoutMsInput").value || 12000)
      };
    }

    function setButtonBusy(button, busy, busyLabel) {
      if (!button) return;
      if (busy) {
        button.setAttribute("data-default-label", button.textContent);
        button.textContent = busyLabel || "Working...";
        button.disabled = true;
        return;
      }
      const label = button.getAttribute("data-default-label");
      if (label) button.textContent = label;
      button.disabled = false;
    }

    function renderValidation(validation) {
      const box = $("validationBox");
      if (!validation) {
        box.className = "alert-card";
        box.textContent = "";
        return;
      }
      const errors = Array.isArray(validation.errors) ? validation.errors : [];
      const warnings = Array.isArray(validation.warnings) ? validation.warnings : [];
      if (errors.length) {
        box.className = "alert-card show bad";
        box.innerHTML = "<strong>Validation issues:</strong><br>" + errors.map(escapeHtml).join("<br>");
        return;
      }
      if (warnings.length) {
        box.className = "alert-card show warn";
        box.innerHTML = "<strong>Validation warnings:</strong><br>" + warnings.map(escapeHtml).join("<br>");
        return;
      }
      if (validation.is_valid) {
        box.className = "alert-card show ok";
        box.textContent = "Validation passed: ISO 5807 checks completed.";
        return;
      }
      box.className = "alert-card";
      box.textContent = "";
    }

    function renderQuality(result) {
      const card = $("qualityCard");
      const title = $("qualityTitle");
      const summary = $("qualitySummary");
      const actions = $("qualityActions");
      card.className = "quality-card";
      actions.innerHTML = "";
      if (!result) {
        summary.textContent = "";
        return;
      }

      const status = result.user_quality_status || "review";
      const readable = status === "ready" ? "Ready to share" : (status === "issues" ? "Needs fixes" : "Needs review");
      title.textContent = "Quality: " + readable;
      summary.textContent = result.user_quality_summary || "Quality guidance is available after generation.";
      const recommended = Array.isArray(result.user_recommended_actions) ? result.user_recommended_actions : [];
      actions.innerHTML = recommended.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
      card.classList.add("show");
      card.classList.add(status);
    }

    async function pollUpgradeResult(jobId, payloadTitle) {
      if (!jobId) return;
      state.activeUpgradeJobId = jobId;
      const started = Date.now();
      while (state.activeUpgradeJobId === jobId) {
        const res = await fetch(`/api/generate/upgrade-status/${encodeURIComponent(jobId)}`);
        const data = await readJsonResponse(res);
        if (!res.ok || !data || !data.success) {
          toast("Quality upgrade check failed.", "warn");
          return;
        }
        if (data.status === "completed" && data.result) {
          const result = data.result;
          state.currentMermaidCode = result.mermaid_code || state.currentMermaidCode;
          state.currentWorkflowTitle = payloadTitle || state.currentWorkflowTitle;
          if (!state.currentWorkflowText) {
            state.currentWorkflowText = $("textInput").value.trim() || state.currentWorkflowText;
          }
          state.currentFlowchartData = result.flowchart_data || null;
          resetManualLayout({ disableEditMode: true });
          state.currentNodeConfidence = Array.isArray(result.node_confidence) ? result.node_confidence : state.currentNodeConfidence;
          $("mermaidEditor").value = state.currentMermaidCode;
          await renderMermaid(state.currentMermaidCode);
          renderValidation(result.validation || null);
          renderQuality(result);
          renderNodeReview(state.currentNodeConfidence);
          addHistory(payloadTitle, result.stats || {});
          toast("Quality upgrade complete.", "good");
          state.activeUpgradeJobId = null;
          return;
        }
        if (data.status === "failed") {
          toast(data.error || "Quality upgrade failed.", "warn");
          state.activeUpgradeJobId = null;
          return;
        }
        if (Date.now() - started > 180000) {
          toast("Quality upgrade timed out.", "warn");
          state.activeUpgradeJobId = null;
          return;
        }
        await new Promise((resolve) => setTimeout(resolve, 1200));
      }
    }

    async function generateSelectedWorkflow() {
      if (!state.workflows.length) {
        throw new Error("Add content first so workflows can be detected.");
      }
      
      // NEW: Get ALL selected workflow IDs instead of just the first one
      const workflowIds = state.selectedWorkflowIds;
      if (!workflowIds.length) {
        throw new Error("Select at least one workflow before generating.");
      }
      
      const btn = $("generateBtn");
      setButtonBusy(btn, true, "Generating...");
      updateProgress(true, 25, "Preparing workflow data...");
      
      try {
        // NEW: Concatenate the text of ALL selected workflows in order
        const workflowSegments = [];
        let primaryTitle = "Combined Workflow";
        
        for (let i = 0; i < workflowIds.length; i++) {
          const wfText = await loadWorkflowText(workflowIds[i]);
          if (wfText) {
            workflowSegments.push(buildStructuredWorkflowSegment(workflowIds[i], wfText, i, workflowIds.length));
          }
          // Use the first selected workflow's title as the base
          if (i === 0) {
            const primaryWf = getWorkflowById(workflowIds[i]);
            primaryTitle = primaryWf && primaryWf.title ? primaryWf.title : "Workflow";
          }
        }

        const combinedWorkflowText = workflowSegments.join("\n\n");

        if (!combinedWorkflowText.trim()) {
          throw new Error("Could not load workflow text. Try reprocessing input.");
        }
        
        // If multiple are selected, append an indicator to the title
        if (workflowIds.length > 1) {
          primaryTitle = `${primaryTitle} (and ${workflowIds.length - 1} more)`;
        }

        updateProgress(true, 55, "Generating combined diagram...");
        
        // Build the payload using the combined text
        const payload = buildGeneratePayload(combinedWorkflowText, workflowIds[0]);
        payload.title = primaryTitle; // Override title
        
        const res = await fetch("/api/generate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        
        let data = null;
        try {
          data = await res.json();
        } catch (error) {
          data = {};
        }

        if (!res.ok || !data.success || !data.mermaid_code) {
          renderValidation(data.validation || null);
          renderQuality(data || null);
          throw new Error((data && data.error) ? data.error : "Generation failed.");
        }

        state.currentMermaidCode = data.mermaid_code;
        state.currentWorkflowText = combinedWorkflowText;
        state.currentWorkflowTitle = payload.title || primaryTitle;
        state.currentFlowchartData = data.flowchart_data || null;
        resetManualLayout({ disableEditMode: true });
        state.currentNodeConfidence = Array.isArray(data.node_confidence) ? data.node_confidence : [];
        $("mermaidEditor").value = state.currentMermaidCode;
        
        updateProgress(true, 88, "Rendering preview...");
        await renderMermaid(state.currentMermaidCode);
        updateStepper(3);
        showTab("diagram");
        renderValidation(data.validation || null);
        renderQuality(data);
        renderNodeReview(state.currentNodeConfidence);

        addHistory(payload.title, data.stats || {});
        const nodes = data.stats && data.stats.nodes ? Number(data.stats.nodes) : 0;
        const links = data.stats && data.stats.connections ? Number(data.stats.connections) : 0;
        
        if (data.provisional && data.upgrade_job_id) {
          toast(`Generated provisional ${nodes} nodes and ${links} connections. Upgrading quality...`, "good");
          pollUpgradeResult(data.upgrade_job_id, payload.title);
        } else {
          toast(`Generated ${nodes} nodes and ${links} connections.`, "good");
        }
      } finally {
        updateProgress(false);
        setButtonBusy(btn, false);
      }
    }

    function downloadBlob(blob, filename) {
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    }

    function ensureMermaidCode() {
      if (!state.currentMermaidCode) {
        throw new Error("Generate a flowchart first.");
      }
      return state.currentMermaidCode;
    }

    async function exportMmd() {
      const code = ensureMermaidCode();
      const blob = new Blob([code], { type: "text/plain;charset=utf-8" });
      downloadBlob(blob, "flowchart.mmd");
      toast("Exported .mmd source.", "good");
    }

    function getCurrentSvgMarkup() {
      const svgEl = $("diagramView").querySelector("svg");
      if (!svgEl) return "";
      return new XMLSerializer().serializeToString(svgEl);
    }

    async function exportSvg() {
      const svg = getCurrentFlowchartSvgMarkup();
      if (!svg) {
        throw new Error("No rendered SVG available yet.");
      }
      const blob = new Blob([svg], { type: "image/svg+xml;charset=utf-8" });
      downloadBlob(blob, "flowchart.svg");
      toast("Exported SVG.", "good");
    }

    async function exportPngClient() {
      const svg = getCurrentFlowchartSvgMarkup();
      const blob = await svgMarkupToPngBlob(svg);
      downloadBlob(blob, "flowchart.png");
      toast("Exported PNG.", "good");
    }

    async function exportPdfFromCurrentView() {
      const svg = getCurrentFlowchartSvgMarkup();
      const pngBlob = await svgMarkupToPngBlob(svg);
      const pngDataUrl = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = () => reject(new Error("Could not prepare PDF export."));
        reader.readAsDataURL(pngBlob);
      });
      const payload = {
        renderer: $("rendererSelect").value || "graphviz",
        format: "pdf",
        profile: $("exportProfileSelect").value || "polished",
        quality_mode: $("qualityModeSelect").value || "draft_allowed",
        png_data_url: pngDataUrl,
      };
      const res = await fetch("/api/render", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (!res.ok) {
        let err = null;
        try {
          err = await res.json();
        } catch (error) {
          err = null;
        }
        throw new Error(err && err.error ? err.error : "Export failed (PDF).");
      }
      const blob = await res.blob();
      downloadBlob(blob, "flowchart.pdf");
      toast("Exported PDF.", "good");
    }

    async function exportViaServer(format) {
      if (state.currentFlowchartData && hasManualLayout()) {
        if (format === "png") {
          return exportPngClient();
        }
        if (format === "pdf") {
          return exportPdfFromCurrentView();
        }
      }
      const code = ensureMermaidCode();
      const selectedRenderer = $("rendererSelect").value || "graphviz";
      const workflowText = (state.currentWorkflowText || "").trim();
      const workflowTitle = (state.currentWorkflowTitle || "").trim() || "Workflow";
      const profile = $("exportProfileSelect").value || "polished";
      const qualityMode = $("qualityModeSelect").value || "draft_allowed";
      const useProfessionalRenderer = Boolean(
        workflowText && profile === "polished" && format !== "html"
      );
      const effectiveRenderer = useProfessionalRenderer ? "graphviz" : selectedRenderer;
      const payload = {
        renderer: effectiveRenderer,
        preferred_renderer: effectiveRenderer,
        format: format,
        theme: $("themeSelect").value || "default",
        profile,
        quality_mode: qualityMode,
        strict_artifact_checks: true
      };
      if (workflowText) {
        payload.workflow_text = workflowText;
        payload.title = workflowTitle;
        payload.direction = ($("directionSelect") && $("directionSelect").value) || "LR";
      } else {
        payload.mermaid_code = code;
      }
      const res = await fetch("/api/render", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (!res.ok) {
        let err = null;
        try {
          err = await res.json();
        } catch (error) {
          err = null;
        }
        throw new Error(err && err.error ? err.error : `Export failed (${format.toUpperCase()}).`);
      }
      const blob = await res.blob();
      downloadBlob(blob, `flowchart.${format}`);
      const resolvedRenderer = res.headers.get("X-Flowchart-Resolved-Renderer") || effectiveRenderer;
      if (!workflowText && effectiveRenderer === "graphviz" && (resolvedRenderer === "mermaid" || resolvedRenderer === "html")) {
        toast("Export fell back to Mermaid because workflow source text was unavailable.", "warn");
      }
      if (useProfessionalRenderer && selectedRenderer !== "graphviz" && resolvedRenderer === "graphviz") {
        toast(`Exported ${format.toUpperCase()} via Graphviz for a polished artifact.`, "good");
        return;
      }
      toast(`Exported ${format.toUpperCase()} via ${resolvedRenderer}.`, "good");
    }

    async function copyMermaidCode() {
      const code = ensureMermaidCode();
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(code);
      } else {
        const temp = document.createElement("textarea");
        temp.value = code;
        document.body.appendChild(temp);
        temp.select();
        document.execCommand("copy");
        temp.remove();
      }
      toast("Copied Mermaid code to clipboard.", "good");
    }

    function setProviderStatus(message, level) {
      const el = $("providerStatus");
      if (!el) return;
      const color = level === "bad" ? "#b91c1c" : (level === "warn" ? "#b45309" : "#334155");
      el.style.color = color;
      el.textContent = message || "";
    }

    function mapExtractorRecommendation(value) {
      const raw = String(value || "").toLowerCase();
      if (raw === "local-llm") return "llm";
      if (raw === "heuristic") return "rules";
      return raw || "auto";
    }

    async function loadCapabilitiesAndRecommendations() {
      const [capsRes, renderersRes] = await Promise.all([
        fetch("/api/capabilities"),
        fetch("/api/renderers")
      ]);
      const capsData = await readJsonResponse(capsRes);
      const rendData = await readJsonResponse(renderersRes);
      state.capabilities = capsData || null;

      if (rendData && rendData.recommended) {
        if (rendData.recommended.renderer) {
          if ([...$("rendererSelect").options].some((o) => o.value === rendData.recommended.renderer)) {
            $("rendererSelect").value = rendData.recommended.renderer;
          }
        }
      }

      const hardware = capsData && capsData.hardware ? capsData.hardware : {};
      const extract = capsData && capsData.extractors ? mapExtractorRecommendation(capsData.extractors.recommended) : "auto";
      const render = capsData && capsData.renderers ? capsData.renderers.recommended : "mermaid";
      const ram = Number(hardware.total_ram_gb || 0).toFixed(1);
      setProviderStatus(`System ready: ${ram} GB RAM. Recommended extraction ${extract}, renderer ${render}.`, "good");
    }

    async function loadOllamaModels() {
      const baseUrl = $("ollamaBaseInput").value.trim() || "http://localhost:11434";
      const res = await fetch(`/api/ollama/models?base_url=${encodeURIComponent(baseUrl)}`);
      const data = await readJsonResponse(res);
      const select = $("ollamaModelSelect");
      const models = Array.isArray(data.models) ? data.models : [];
      const prev = select.value;
      select.innerHTML = `<option value="">Auto</option>` + models.map((model) => {
        const id = typeof model === "string" ? model : (model && model.name ? model.name : "");
        return `<option value="${escapeHtml(id)}">${escapeHtml(id)}</option>`;
      }).join("");
      if (prev && models.some((m) => (typeof m === "string" ? m : m.name) === prev)) {
        select.value = prev;
      }
      setProviderStatus(models.length ? `Ollama available: ${models.length} model(s) detected.` : "No Ollama models detected at the configured base URL.", models.length ? "good" : "warn");
    }

    async function loadLocalModels() {
      const res = await fetch("/api/models");
      const data = await readJsonResponse(res);
      const select = $("localModelSelect");
      const models = Array.isArray(data.models) ? data.models : [];
      select.innerHTML = `<option value="">${models.length ? "Choose local model path" : "None detected"}</option>` + models.map((model) => {
        const path = String(model.path || "");
        const name = model.name ? String(model.name) : path;
        const size = model.size_gb !== undefined ? ` (${Number(model.size_gb).toFixed(2)} GB)` : "";
        return `<option value="${escapeHtml(path)}">${escapeHtml(name)}${escapeHtml(size)}</option>`;
      }).join("");
    }

    async function generateBatchPackage() {
      if (!state.cacheKey) {
        throw new Error("Batch export needs a detected document workflow set.");
      }
      if (state.selectedWorkflowIds.length < 2) {
        throw new Error("Select at least two workflows before generating a package.");
      }
      const btn = $("batchBtn");
      setButtonBusy(btn, true, "Building Package...");
      updateProgress(true, 28, "Preparing batch package...");
      try {
        const payload = {
          cache_key: state.cacheKey,
          split_mode: "none",
          format: "png",
          extraction: $("extractionSelect").value || "rules",
          renderer: $("rendererSelect").value || "graphviz",
          theme: $("themeSelect").value || getStylePresetTheme(),
          direction: $("directionSelect").value || "LR",
          quality_mode: $("qualityModeSelect").value || "draft_allowed",
          min_detection_confidence_certified: Number($("certMinInput").value || 0.65),
          model_path: $("modelPathInput").value.trim() || null,
          ollama_base_url: $("ollamaBaseInput").value.trim() || "http://localhost:11434",
          ollama_model: $("ollamaModelSelect").value || null,
          validate: true,
          include_validation_report: true,
          include_qa_manifest: true
        };
        const res = await fetch("/api/batch-export", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        if (!res.ok) {
          let err = null;
          try {
            err = await res.json();
          } catch (error) {
            err = null;
          }
          throw new Error(err && err.error ? err.error : "Batch export failed.");
        }
        updateProgress(true, 86, "Downloading package...");
        const blob = await res.blob();
        downloadBlob(blob, "workflow_package.zip");
        toast("Batch package downloaded.", "good");
      } finally {
        updateProgress(false);
        setButtonBusy(btn, false);
      }
    }
    function renderHistory() {
      const list = $("historyList");
      if (!state.history.length) {
        list.innerHTML = `<div style="font-size:12px;color:#334155;">No generated flowcharts yet.</div>`;
        return;
      }
      list.innerHTML = state.history.map((item, idx) => `
        <div class="history-item" data-history-index="${idx}">
          <div><strong>${escapeHtml(item.title)}</strong></div>
          <div class="meta">${escapeHtml(item.time)} | ${Number(item.nodes || 0)} nodes</div>
        </div>
      `).join("");
      list.querySelectorAll(".history-item").forEach((el) => {
        el.addEventListener("click", () => {
          const idx = Number(el.getAttribute("data-history-index"));
          const item = state.history[idx];
          if (!item) return;
          state.currentMermaidCode = item.code || "";
          state.currentWorkflowText = item.workflowText || "";
          state.currentWorkflowTitle = item.workflowTitle || item.title || "Workflow";
          state.currentFlowchartData = item.flowchartData || null;
          state.manualLayout = cloneManualLayout(item.manualLayout);
          state.layoutEditMode = false;
          state.selectedLayoutTarget = null;
          syncLayoutButtons();
          $("mermaidEditor").value = state.currentMermaidCode;
          renderMermaid(state.currentMermaidCode);
          showTab("diagram");
          toast("Restored from history", "good");
        });
      });
    }

    function addHistory(title, stats) {
      state.history.unshift({
        title: title || "Workflow",
        nodes: Number((stats && stats.nodes) || 0),
        code: state.currentMermaidCode,
        workflowText: state.currentWorkflowText,
        workflowTitle: state.currentWorkflowTitle,
        flowchartData: state.currentFlowchartData,
        manualLayout: cloneManualLayout(state.manualLayout),
        time: new Date().toLocaleTimeString()
      });
      state.history = state.history.slice(0, 12);
      renderHistory();
    }

    function renderEditableDiagram() {
      const flowchart = state.currentFlowchartData;
      if (!flowchart || !Array.isArray(flowchart.nodes) || !flowchart.nodes.length) {
        return renderMermaid(state.currentMermaidCode);
      }

      const direction = String(flowchart.direction || "LR").toUpperCase();
      const metricsMap = new Map();
      flowchart.nodes.forEach((node) => {
        metricsMap.set(node.id, getLayoutNodeMetrics(node, direction));
      });

      const metricsList = Array.from(metricsMap.values());
      const maxRight = metricsList.reduce((max, item) => Math.max(max, item.x + item.width), 0);
      const maxBottom = metricsList.reduce((max, item) => Math.max(max, item.y + item.height), 0);
      const svg = createSvgEl("svg", {
        viewBox: `0 0 ${Math.max(900, maxRight + 120)} ${Math.max(700, maxBottom + 120)}`,
        xmlns: "http://www.w3.org/2000/svg",
      });
      svg.style.width = "100%";
      svg.style.height = "auto";

      const defs = createSvgEl("defs");
      const marker = createSvgEl("marker", {
        id: "layout-arrowhead",
        markerWidth: 10,
        markerHeight: 8,
        refX: 9,
        refY: 4,
        orient: "auto",
        markerUnits: "strokeWidth",
      });
      marker.appendChild(createSvgEl("path", {
        d: "M 0 0 L 10 4 L 0 8 z",
        fill: "#64748b",
      }));
      defs.appendChild(marker);
      svg.appendChild(defs);

      const groupsLayer = createSvgEl("g", { class: "layout-groups" });
      const edgesLayer = createSvgEl("g", { class: "layout-edges" });
      const nodesLayer = createSvgEl("g", { class: "layout-nodes" });
      const nodeElementMap = new Map();
      const groupElementMap = new Map();
      const edgeElementEntries = [];
      svg.appendChild(groupsLayer);
      svg.appendChild(edgesLayer);
      svg.appendChild(nodesLayer);

      const grouped = new Map();
      metricsList.forEach((item) => {
        if (!item.group) return;
        if (!grouped.has(item.group)) grouped.set(item.group, []);
        grouped.get(item.group).push(item);
      });
      const dragDamping = 0.45;
      const resolveMetrics = (layout = state.manualLayout) => {
        const nextMetrics = new Map();
        flowchart.nodes.forEach((node) => {
          const template = metricsMap.get(node.id);
          if (!template) return;
          const base = getBaseNodePosition(node, direction);
          const manual = layout[node.id] || {};
          nextMetrics.set(node.id, {
            ...template,
            x: (Number.isFinite(manual.x) ? Number(manual.x) : base.x) + 80,
            y: (Number.isFinite(manual.y) ? Number(manual.y) : base.y) + 80,
          });
        });
        return nextMetrics;
      };
      const updatePreviewLayout = (layout = state.manualLayout) => {
        const liveMetrics = resolveMetrics(layout);
        liveMetrics.forEach((item, nodeId) => {
          const nodeEl = nodeElementMap.get(nodeId);
          if (nodeEl) {
            nodeEl.setAttribute("transform", `translate(${item.x} ${item.y})`);
          }
        });
        groupElementMap.forEach((entry, groupName) => {
          const items = Array.from(liveMetrics.values()).filter((item) => item.group === groupName);
          if (!items.length) return;
          const minX = Math.min(...items.map((item) => item.x)) - 28;
          const minY = Math.min(...items.map((item) => item.y)) - 42;
          const maxX = Math.max(...items.map((item) => item.x + item.width)) + 28;
          const maxY = Math.max(...items.map((item) => item.y + item.height)) + 28;
          entry.box.setAttribute("x", String(minX));
          entry.box.setAttribute("y", String(minY));
          entry.box.setAttribute("width", String(maxX - minX));
          entry.box.setAttribute("height", String(maxY - minY));
          entry.label.setAttribute("x", String(minX + 14));
          entry.label.setAttribute("y", String(minY + 22));
        });
        edgeElementEntries.forEach((entry) => {
          const fromMetrics = liveMetrics.get(entry.connection.from);
          const toMetrics = liveMetrics.get(entry.connection.to);
          if (!fromMetrics || !toMetrics) return;
          const pathInfo = connectionPath(fromMetrics, toMetrics);
          entry.path.setAttribute("d", pathInfo.d);
          if (entry.label) {
            entry.label.setAttribute("x", String(pathInfo.midX));
            entry.label.setAttribute("y", String(pathInfo.midY - 8));
          }
        });
      };
      const bindDragTarget = (target, getInitialLayout, onStart, onStop) => {
        return (event) => {
          event.preventDefault();
          event.stopPropagation();
          setSelectedLayoutTarget(target);
          const svgPoint = svg.createSVGPoint();
          const toSvgCoords = (clientX, clientY) => {
            svgPoint.x = clientX;
            svgPoint.y = clientY;
            return svgPoint.matrixTransform(svg.getScreenCTM().inverse());
          };
          const start = toSvgCoords(event.clientX, event.clientY);
          const initialLayout = getInitialLayout();
          if (typeof onStart === "function") onStart();
          const move = (moveEvent) => {
            const current = toSvgCoords(moveEvent.clientX, moveEvent.clientY);
            const deltaX = (current.x - start.x) * dragDamping;
            const deltaY = (current.y - start.y) * dragDamping;
            Object.entries(initialLayout).forEach(([nodeId, basePosition]) => {
              state.manualLayout[nodeId] = {
                x: Math.round(basePosition.x + deltaX),
                y: Math.round(basePosition.y + deltaY),
              };
            });
            updatePreviewLayout();
          };
          const stop = () => {
            window.removeEventListener("pointermove", move);
            window.removeEventListener("pointerup", stop);
            window.removeEventListener("pointercancel", stop);
            syncCurrentHistoryLayout();
            if (typeof onStop === "function") onStop();
            renderEditableDiagram();
          };
          window.addEventListener("pointermove", move);
          window.addEventListener("pointerup", stop);
          window.addEventListener("pointercancel", stop);
        };
      };
      grouped.forEach((items, groupName) => {
        const minX = Math.min(...items.map((item) => item.x)) - 28;
        const minY = Math.min(...items.map((item) => item.y)) - 42;
        const maxX = Math.max(...items.map((item) => item.x + item.width)) + 28;
        const maxY = Math.max(...items.map((item) => item.y + item.height)) + 28;
        const box = createSvgEl("rect", {
          class: `layout-group-box${state.selectedLayoutTarget && state.selectedLayoutTarget.kind === "group" && state.selectedLayoutTarget.id === groupName ? " selected" : ""}`,
          "data-group-name": groupName,
          x: minX,
          y: minY,
          width: maxX - minX,
          height: maxY - minY,
          rx: 16,
          fill: "#f8fbff",
          stroke: "#cbd5e1",
          "stroke-dasharray": "8 6",
          "stroke-width": 1.5,
        });
        const label = createSvgEl("text", {
          class: `layout-group-label${state.selectedLayoutTarget && state.selectedLayoutTarget.kind === "group" && state.selectedLayoutTarget.id === groupName ? " selected" : ""}`,
          "data-group-name": groupName,
          x: minX + 14,
          y: minY + 22,
          fill: "#334155",
          "font-size": 13,
          "font-weight": 700,
          "font-family": "Source Sans 3, Segoe UI, sans-serif",
        });
        label.textContent = groupName;
        if (state.layoutEditMode) {
          const groupNodeIds = items.map((item) => item.id);
          const startDrag = bindDragTarget(
            { kind: "group", id: groupName },
            () => {
              const initial = {};
              groupNodeIds.forEach((nodeId) => {
                const node = flowchart.nodes.find((candidate) => candidate.id === nodeId);
                if (!node) return;
                const base = getBaseNodePosition(node, direction);
                initial[nodeId] = state.manualLayout[nodeId] || { x: base.x, y: base.y };
              });
              return initial;
            },
            () => {
              box.classList.add("selected");
            }
          );
          box.addEventListener("pointerdown", startDrag);
          label.addEventListener("pointerdown", startDrag);
          box.addEventListener("click", (event) => {
            event.stopPropagation();
            setSelectedLayoutTarget({ kind: "group", id: groupName });
            renderEditableDiagram();
          });
          label.addEventListener("click", (event) => {
            event.stopPropagation();
            setSelectedLayoutTarget({ kind: "group", id: groupName });
            renderEditableDiagram();
          });
        }
        groupsLayer.appendChild(box);
        groupsLayer.appendChild(label);
        groupElementMap.set(groupName, { box, label });
      });

      (flowchart.connections || []).forEach((connection, index) => {
        const fromMetrics = metricsMap.get(connection.from);
        const toMetrics = metricsMap.get(connection.to);
        if (!fromMetrics || !toMetrics) return;
        const pathInfo = connectionPath(fromMetrics, toMetrics);
        const path = createSvgEl("path", {
          "data-connection-index": index,
          d: pathInfo.d,
          fill: "none",
          stroke: "#64748b",
          "stroke-width": 2,
          "marker-end": "url(#layout-arrowhead)",
        });
        edgesLayer.appendChild(path);
        let labelEl = null;
        if (connection.label) {
          labelEl = createSvgEl("text", {
            "data-connection-index": index,
            x: pathInfo.midX,
            y: pathInfo.midY - 8,
            "text-anchor": "middle",
            fill: "#475569",
            "font-size": 11,
            "font-weight": 700,
            "font-family": "Source Sans 3, Segoe UI, sans-serif",
          });
          labelEl.textContent = String(connection.label);
          edgesLayer.appendChild(labelEl);
        }
        edgeElementEntries.push({ connection, path, label: labelEl });
      });

      metricsList.forEach((item) => {
        const nodeGroup = createSvgEl("g", {
          class: `layout-node${state.selectedLayoutTarget && state.selectedLayoutTarget.kind === "node" && state.selectedLayoutTarget.id === item.id ? " selected" : ""}`,
          "data-node-id": item.id,
          transform: `translate(${item.x} ${item.y})`,
        });
        let shapeEl;
        if (item.shape === "decision") {
          shapeEl = createSvgEl("polygon", {
            points: `${item.width / 2},0 ${item.width},${item.height / 2} ${item.width / 2},${item.height} 0,${item.height / 2}`,
            fill: "#fff7ed",
            stroke: "#d97706",
            "stroke-width": 1.5,
          });
        } else if (item.shape === "terminator") {
          shapeEl = createSvgEl("rect", {
            x: 0,
            y: 0,
            width: item.width,
            height: item.height,
            rx: item.height / 2,
            fill: "#ecfdf5",
            stroke: "#0f766e",
            "stroke-width": 1.5,
          });
        } else if (item.shape === "io") {
          shapeEl = createSvgEl("polygon", {
            points: `18,0 ${item.width},0 ${item.width - 18},${item.height} 0,${item.height}`,
            fill: "#eef2ff",
            stroke: "#4f46e5",
            "stroke-width": 1.5,
          });
        } else {
          shapeEl = createSvgEl("rect", {
            x: 0,
            y: 0,
            width: item.width,
            height: item.height,
            rx: 14,
            fill: "#ffffff",
            stroke: "#1d4ed8",
            "stroke-width": 1.5,
          });
        }
        nodeGroup.appendChild(shapeEl);
        const textEl = createSvgEl("text", {
          x: item.width / 2,
          y: 24,
          "text-anchor": "middle",
          fill: "#0f172a",
          "font-size": 12,
          "font-weight": 600,
          "font-family": "Source Sans 3, Segoe UI, sans-serif",
        });
        item.lines.forEach((line, index) => {
          const tspan = createSvgEl("tspan", {
            x: item.width / 2,
            dy: index === 0 ? 0 : 16,
          });
          tspan.textContent = line;
          textEl.appendChild(tspan);
        });
        nodeGroup.appendChild(textEl);

        if (state.layoutEditMode) {
          nodeGroup.addEventListener("pointerdown", bindDragTarget(
            { kind: "node", id: item.id },
            () => {
              const node = flowchart.nodes.find((candidate) => candidate.id === item.id);
              if (!node) return {};
              const base = getBaseNodePosition(node, direction);
              return {
                [item.id]: state.manualLayout[item.id] || { x: base.x, y: base.y }
              };
            },
            () => {
              nodeGroup.classList.add("dragging");
            },
            () => {
              nodeGroup.classList.remove("dragging");
            }
          ));
          nodeGroup.addEventListener("click", (event) => {
            event.stopPropagation();
            setSelectedLayoutTarget({ kind: "node", id: item.id });
            renderEditableDiagram();
          });
        } else {
          nodeGroup.style.cursor = "pointer";
          nodeGroup.addEventListener("click", () => {
            const reviewItem = document.querySelector(`.review-item[data-node-id="${item.id}"]`);
            if (reviewItem) {
              reviewItem.scrollIntoView({ behavior: "smooth", block: "center" });
              reviewItem.style.background = "#fff9c4";
              setTimeout(() => { reviewItem.style.background = ""; }, 2000);
            }
          });
        }

        nodesLayer.appendChild(nodeGroup);
        nodeElementMap.set(item.id, nodeGroup);
      });

      $("diagramView").innerHTML = "";
      $("diagramView").appendChild(svg);
      if (state.layoutEditMode) {
        svg.addEventListener("click", () => {
          setSelectedLayoutTarget(null);
          renderEditableDiagram();
        });
      }
      $("diagramView").style.display = "flex";
      $("emptyState").style.display = "none";
      syncLayoutButtons();
    }

    async function renderMermaid(code) {
      if (!code) {
        $("emptyState").style.display = "flex";
        $("diagramView").style.display = "none";
        return;
      }
      if (state.currentFlowchartData && (state.layoutEditMode || hasManualLayout())) {
        renderEditableDiagram();
        return;
      }
      try {
        const id = "flowchart-" + Date.now();
        const { svg, bindFunctions } = await window.mermaidAPI.render(id, code);
        $("diagramView").innerHTML = svg;
        $("diagramView").style.display = "flex";
        $("emptyState").style.display = "none";

        // Add bidirectional UI linking: click a node to scroll to its review item
        const svgEl = $("diagramView").querySelector("svg");
        if (svgEl) {
          svgEl.querySelectorAll(".node").forEach((nodeEl) => {
            nodeEl.style.cursor = "pointer";
            nodeEl.addEventListener("click", () => {
              const nodeId = nodeEl.id.split("-")[0]; // Mermaid IDs are often ID-N
              const reviewItem = document.querySelector(`.review-item[data-node-id="${nodeId}"]`);
              if (reviewItem) {
                reviewItem.scrollIntoView({ behavior: "smooth", block: "center" });
                reviewItem.style.background = "#fff9c4";
                setTimeout(() => { reviewItem.style.background = ""; }, 2000);
              }
            });
          });
        }
      } catch (error) {
        $("diagramView").innerHTML = `<div style="padding:16px;color:#b91c1c;">Mermaid error: ${escapeHtml(error.message || String(error))}</div>`;
        $("diagramView").style.display = "flex";
        $("emptyState").style.display = "none";
      }
    }

    const debouncedRenderMermaid = debounce(async (code) => {
      state.currentMermaidCode = code;
      localStorage.setItem("flowchart_manual_code", code);
      await renderMermaid(code);
    }, 500);

    function bindStaticUi() {
      $("advancedToggleTop").addEventListener("click", toggleAdvanced);
      $("historyToggleTop").addEventListener("click", toggleHistory);
      $("diagramTab").addEventListener("click", () => showTab("diagram"));
      $("codeTab").addEventListener("click", () => showTab("code"));

      $("zoomInBtn").addEventListener("click", () => {
        state.currentZoom = Math.min(3, state.currentZoom + 0.2);
        $("diagramView").style.transform = `scale(${state.currentZoom})`;
      });
      $("zoomOutBtn").addEventListener("click", () => {
        state.currentZoom = Math.max(0.4, state.currentZoom - 0.2);
        $("diagramView").style.transform = `scale(${state.currentZoom})`;
      });
      $("zoomResetBtn").addEventListener("click", () => {
        state.currentZoom = 1;
        $("diagramView").style.transform = "scale(1)";
      });

      $("layoutEditBtn").addEventListener("click", () => {
        if (!state.currentFlowchartData) {
          toast("Generate a flowchart before editing the layout.", "warn");
          return;
        }
        state.layoutEditMode = !state.layoutEditMode;
        if (!state.layoutEditMode) {
          syncCurrentHistoryLayout();
          toast("Layout saved for this chart. Reopen Edit Layout to keep adjusting it.", "good");
        } else {
          toast("Drag nodes or phase headers. Use arrow keys for fine movement.", "good");
        }
        syncLayoutButtons();
        renderMermaid(state.currentMermaidCode);
      });
      $("layoutResetBtn").addEventListener("click", () => {
        if (!state.currentFlowchartData) return;
        resetManualLayout();
        syncCurrentHistoryLayout();
        renderMermaid(state.currentMermaidCode);
        toast("Layout reset to automatic positions.", "good");
      });
      $("layoutPhaseHorizontalBtn").addEventListener("click", () => {
        if (!reflowSelectedPhase("horizontal")) {
          toast("Select a phase with at least two steps to reflow it into a row.", "warn");
          return;
        }
        renderMermaid(state.currentMermaidCode);
        toast("Reflowed the selected phase into a horizontal row.", "good");
      });
      $("layoutPhaseVerticalBtn").addEventListener("click", () => {
        if (!reflowSelectedPhase("vertical")) {
          toast("Select a phase with at least two steps to reflow it into a stack.", "warn");
          return;
        }
        renderMermaid(state.currentMermaidCode);
        toast("Reflowed the selected phase into a vertical stack.", "good");
      });
      $("layoutAllPhasesHorizontalBtn").addEventListener("click", () => {
        if (!reflowAllPhases("horizontal")) {
          toast("Generate a chart with at least two named phases to reflow the phase band.", "warn");
          return;
        }
        renderMermaid(state.currentMermaidCode);
        toast("Reflowed all phases into a horizontal band.", "good");
      });
      $("layoutAllPhasesVerticalBtn").addEventListener("click", () => {
        if (!reflowAllPhases("vertical")) {
          toast("Generate a chart with at least two named phases to reflow the phase band.", "warn");
          return;
        }
        renderMermaid(state.currentMermaidCode);
        toast("Reflowed all phases into a vertical band.", "good");
      });

      $("uploadZone").addEventListener("click", () => $("fileInput").click());
      $("uploadZone").addEventListener("dragover", (event) => {
        event.preventDefault();
        $("uploadZone").classList.add("drag");
      });
      $("uploadZone").addEventListener("dragleave", () => $("uploadZone").classList.remove("drag"));
      $("uploadZone").addEventListener("drop", (event) => {
        event.preventDefault();
        $("uploadZone").classList.remove("drag");
        if (event.dataTransfer && event.dataTransfer.files && event.dataTransfer.files.length) {
          $("fileInput").files = event.dataTransfer.files;
          handleUserAction(() => runFileDetection(event.dataTransfer.files[0]));
        }
      });

      $("fileInput").addEventListener("change", () => {
        const selected = $("fileInput").files && $("fileInput").files[0];
        if (!selected) return;
        handleUserAction(() => runFileDetection(selected));
      });

      $("processTextBtn").addEventListener("click", () => {
        handleUserAction(() => runTextDetection($("textInput").value, "Pasted Text"));
      });

      $("fetchUrlBtn").addEventListener("click", () => {
        handleUserAction(runUrlDetection);
      });

      $("urlInput").addEventListener("keydown", (event) => {
        if (event.key !== "Enter") return;
        event.preventDefault();
        handleUserAction(runUrlDetection);
      });

      $("loadSampleBtn").addEventListener("click", () => {
        handleUserAction(loadSelectedSample);
      });

      $("formatHelperTrigger").addEventListener("click", () => {
        $("formatHelperModal").classList.add("show");
      });

      $("selectAllWorkflowsBtn").addEventListener("click", () => {
        if (!state.workflows.length) return;
        setWorkflowSelection(state.workflows.map((wf) => wf.id));
      });

      $("selectSingleWorkflowBtn").addEventListener("click", () => {
        if (!state.workflows.length) return;
        setWorkflowSelection([state.workflows[0].id]);
      });

      $("exportSvgBtn").addEventListener("click", () => handleUserAction(exportSvg));
      $("exportPdfBtn").addEventListener("click", () => handleUserAction(() => exportViaServer("pdf")));
      $("exportPngBtn").addEventListener("click", () => handleUserAction(() => exportViaServer("png")));
      $("exportMmdBtn").addEventListener("click", () => handleUserAction(exportMmd));
      $("copyCodeBtn").addEventListener("click", () => handleUserAction(copyMermaidCode));
      $("generateBtn").addEventListener("click", () => handleUserAction(generateSelectedWorkflow));
      $("batchBtn").addEventListener("click", () => handleUserAction(generateBatchPackage));
      $("applyEditsBtn").addEventListener("click", () => handleUserAction(generateSelectedWorkflow));
      $("resetEditsBtn").addEventListener("click", () => {
        const workflowId = getSelectedWorkflowId();
        if (!workflowId) return;
        resetNodeEdits(workflowId);
        renderNodeReview(state.currentNodeConfidence);
        toast("Node edits reset.", "good");
      });
      $("refreshOllamaBtn").addEventListener("click", () => handleUserAction(loadOllamaModels));
      $("applyLocalModelBtn").addEventListener("click", () => {
        const selectedPath = $("localModelSelect").value;
        if (!selectedPath) {
          toast("Choose a local model first.", "warn");
          return;
        }
        $("modelPathInput").value = selectedPath;
        toast("Local model path applied.", "good");
      });

      $("mermaidEditor").addEventListener("input", () => {
        if ($("codeTab").classList.contains("active")) {
          state.currentFlowchartData = null;
          resetManualLayout({ disableEditMode: true });
          debouncedRenderMermaid($("mermaidEditor").value);
        }
      });
    }

    function bindKeyboardShortcuts() {
      document.addEventListener("keydown", (event) => {
        if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
          event.preventDefault();
          handleUserAction(generateSelectedWorkflow);
          return;
        }
        if (
          state.currentFlowchartData &&
          state.selectedLayoutTarget &&
          ["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(event.key) &&
          !$("codeTab").classList.contains("active")
        ) {
          event.preventDefault();
          const step = event.shiftKey ? 24 : 8;
          const deltaX = event.key === "ArrowLeft" ? -step : (event.key === "ArrowRight" ? step : 0);
          const deltaY = event.key === "ArrowUp" ? -step : (event.key === "ArrowDown" ? step : 0);
          applyLayoutDelta(state.selectedLayoutTarget, deltaX, deltaY);
          renderMermaid(state.currentMermaidCode);
          return;
        }
        if (event.key === "Escape") {
          if (state.selectedLayoutTarget) {
            state.selectedLayoutTarget = null;
            renderMermaid(state.currentMermaidCode);
            return;
          }
          $("historyDrawer").classList.remove("open");
          $("advancedCard").classList.remove("show");
        }
      });
    }

    async function handleUserAction(actionFn) {
      try {
        await actionFn();
      } catch (error) {
        updateProgress(false);
        toast(error && error.message ? error.message : "Action failed.", "bad");
      }
    }

    async function loadSamples() {
      try {
        const res = await fetch("/api/samples");
        const data = await res.json();
        if (!data.success) return;
        const select = $("sampleSelect");
        select.innerHTML = `<option value="">Choose a sample workflow</option>` + data.samples.map((s) => {
          return `<option value="${escapeHtml(s.id)}">${escapeHtml(s.title)} (${Number(s.step_count || 0)} steps)</option>`;
        }).join("");
      } catch (error) {
        toast("Could not load samples.", "warn");
      }
    }

    function bootstrap() {
      bindStaticUi();
      bindKeyboardShortcuts();
      clearWorkflowState();
      renderHistory();
      showTab("diagram");
      syncLayoutButtons();
      updateProgress(false);
      loadSamples();
      handleUserAction(loadCapabilitiesAndRecommendations);
      handleUserAction(loadLocalModels);
      handleUserAction(loadOllamaModels);

      // Restore manual code if it exists
      const savedCode = localStorage.getItem("flowchart_manual_code");
      if (savedCode) {
        state.currentMermaidCode = savedCode;
        $("mermaidEditor").value = savedCode;
        renderMermaid(savedCode);
        showTab("code");
        toast("Restored your unsaved edits", "good");
      }

      if (!localStorage.getItem("flowchart_onboarded")) {
        $("onboardingOverlay").classList.add("show");
      }
    }

    window.addEventListener("DOMContentLoaded", bootstrap);
  