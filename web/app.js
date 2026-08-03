"use strict";

// Deliberately local demo data. Production UI consumes approved, redacted JSON only.
const journey = ["舰桥接令", "航线规划", "远程扫描", "信号解读", "专用设施", "导航校验"];
const facilities = [
  ["航迹叠加仪", "Trajectory Overlay", "trajectory_overlay"],
  ["条件差分舱", "Condition Differential Chamber", "condition_differential"],
  ["反证探测器", "Counterevidence Detector", "counterevidence_detector"],
];

function renderJourney() {
  const list = document.querySelector("#stations-list");
  list.replaceChildren(...journey.map((name, index) => {
    const item = document.createElement("li");
    item.textContent = name;
    item.className = index < 2 ? "done" : index === 2 ? "active" : "";
    return item;
  }));
}

function renderFacilities() {
  const list = document.querySelector("#facilities-list");
  list.replaceChildren(...facilities.map(([zh, en, id]) => {
    const card = document.createElement("article");
    card.className = "facility";
    card.innerHTML = `<strong>${zh}</strong><small>${en}</small><code>${id}</code>`;
    return card;
  }));
}

function updatePreview(event) {
  event.preventDefault();
  const question = document.querySelector("#question").value.trim();
  const material = document.querySelector("#material").value.trim();
  const message = document.querySelector("#form-message");
  if (!question || !material) {
    message.textContent = "请填写研究问题和材料体系；此操作只更新本地预览。";
    return;
  }
  document.querySelector("#dispatch-reason").textContent = "本地预览已更新；实际分派由 Python 的 mission dispatcher 产生。";
  message.textContent = `已更新 ${material} 的静态预览，未发送任何网络请求。`;
}

document.addEventListener("DOMContentLoaded", () => {
  renderJourney();
  renderFacilities();
  document.querySelector("#mission-form").addEventListener("submit", updatePreview);
});
