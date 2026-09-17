document.querySelectorAll('a[href^="#"]').forEach((link) => {
  link.addEventListener("click", (event) => {
    const target = document.querySelector(link.getAttribute("href"));
    if (target) {
      event.preventDefault();
      target.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  });
});
document.querySelectorAll("form.return-form").forEach((form) => {
  form.addEventListener("submit", (event) => {
    if (!window.confirm("Submit this return request for admin approval?")) event.preventDefault();
  });
});
document.querySelectorAll("a.logout-link").forEach((link) => {
  link.addEventListener("click", (event) => {
    if (!window.confirm("Are you sure you want to log out?")) event.preventDefault();
  });
});

const applyTheme = (dark) => {
  document.body.classList.toggle("dark-mode", dark);
  const toggle = document.querySelector("#theme-toggle");
  const status = document.querySelector("#theme-status");
  if (toggle) toggle.checked = dark;
  if (status) status.textContent = dark ? "Dark mode" : "Light mode";
};
const savedTheme = localStorage.getItem("equiptrack-theme") === "dark";
applyTheme(savedTheme);
document.querySelector("#theme-toggle")?.addEventListener("change", (event) => {
  const dark = event.target.checked;
  localStorage.setItem("equiptrack-theme", dark ? "dark" : "light");
  applyTheme(dark);
});

const reportModal = document.querySelector("[data-report-modal]");
document.querySelector("[data-report-print]")?.addEventListener("click", () => {
  if (reportModal) reportModal.hidden = false;
});
document.querySelector("[data-report-close]")?.addEventListener("click", () => {
  if (reportModal) reportModal.hidden = true;
});
document.querySelector("[data-report-print-now]")?.addEventListener("click", () => {
  if (reportModal) reportModal.hidden = true;
  window.print();
});
document.querySelector("[data-date-range]")?.addEventListener("change", (event) => {
  document.querySelectorAll(".custom-date").forEach((field) => {
    field.hidden = event.target.value !== "custom";
  });
});
document.querySelector("[data-date-range]")?.dispatchEvent(new Event("change"));
