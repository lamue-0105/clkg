const miniProgramCode = "#小程序://问卷星/Uv3jBvh9JOWVGUA";
const copyButton = document.querySelector("#copy-code");
const status = document.querySelector("#copy-status");

async function copySurveyCode() {
  try {
    await navigator.clipboard.writeText(miniProgramCode);
    status.textContent = "口令已复制。请打开微信粘贴并发送，即可进入问卷。";
  } catch {
    status.textContent = "自动复制未成功，请展开下方内容并手动复制问卷口令。";
  }
}

copyButton?.addEventListener("click", copySurveyCode);
