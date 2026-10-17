document.addEventListener("DOMContentLoaded", () => {
  const modal = document.getElementById("contentModal");
  const form = document.getElementById("contentForm");
  const title = document.getElementById("modalTitle");
  const addUrl = "/add";

  function openModal(item = null) {
    if (!modal || !form) return;
    form.reset();
    form.setAttribute("action", item ? `/edit/${encodeURIComponent(item.id)}` : addUrl);
    form.setAttribute("method", "post");
    if (title) title.textContent = item ? "Edit content" : "Add content";
    if (item) {
      Object.entries(item).forEach(([key, value]) => {
        const field = form.elements.namedItem(key);
        if (!field || typeof field.value === "undefined") return;
        if (field.type === "checkbox") field.checked = Boolean(value);
        else field.value = value ?? "";
      });
    } else {
      const dateField = form.elements.namedItem("date");
      const plannedField = form.elements.namedItem("planned_month");
      if (dateField) dateField.value = new Date().toISOString().slice(0, 10);
      if (plannedField) plannedField.value = new URLSearchParams(window.location.search).get("month") || new Date().toISOString().slice(0, 7);
    }
    modal.hidden = false;
  }
  function closeModal() { if (modal) modal.hidden = true; }
  document.getElementById("openModal")?.addEventListener("click", () => openModal());
  document.getElementById("closeModal")?.addEventListener("click", closeModal);
  document.getElementById("cancelModal")?.addEventListener("click", closeModal);
  modal?.addEventListener("click", event => { if (event.target === modal) closeModal(); });
  document.querySelectorAll(".edit-btn").forEach(button => button.addEventListener("click", () => {
    try { openModal(JSON.parse(button.dataset.item)); }
    catch (error) { console.error("Could not open record:", error); alert("Could not open this record for editing."); }
  }));
  document.getElementById("tableSearch")?.addEventListener("input", event => {
    const query = event.target.value.toLowerCase().trim();
    document.querySelectorAll("#contentTable tbody tr[data-search]").forEach(row => { row.hidden = !row.dataset.search.includes(query); });
  });
  document.addEventListener("keydown", event => { if (event.key === "Escape") closeModal(); });
  form?.addEventListener("submit", event => {
    const action = form.getAttribute("action");
    if (!action || action.includes("[object")) { event.preventDefault(); alert("Invalid form URL. Refresh the page and try again."); console.error("Invalid form action:", action); }
  });

  // Futuristic cursor halo, enabled only on mouse/trackpad devices.
  const aura = document.getElementById("cursorAura");
  const finePointer = window.matchMedia && window.matchMedia("(pointer: fine)").matches;
  const reducedMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (aura && finePointer && !reducedMotion) {
    let visible = false;
    window.addEventListener("pointermove", event => {
      aura.style.left = `${event.clientX}px`;
      aura.style.top = `${event.clientY}px`;
      if (!visible) { aura.style.opacity = "1"; visible = true; }
    }, {passive:true});
    document.addEventListener("pointerover", event => {
      aura.classList.toggle("hovering", Boolean(event.target.closest("a,button,input,select,textarea,[role='button']")));
    }, {passive:true});
    document.addEventListener("pointerleave", () => { aura.style.opacity = "0"; visible = false; });
    document.addEventListener("pointerenter", () => { if (visible) aura.style.opacity = "1"; });
  }
});
