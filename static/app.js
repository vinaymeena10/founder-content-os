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
    title.textContent = item ? "Edit content" : "Add content";

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
      if (plannedField) {
        const monthFromPage = new URLSearchParams(window.location.search).get("month");
        plannedField.value = monthFromPage || new Date().toISOString().slice(0, 7);
      }
    }
    modal.hidden = false;
  }

  function closeModal() {
    if (modal) modal.hidden = true;
  }

  document.getElementById("openModal")?.addEventListener("click", () => openModal());
  document.getElementById("closeModal")?.addEventListener("click", closeModal);
  document.getElementById("cancelModal")?.addEventListener("click", closeModal);
  modal?.addEventListener("click", event => {
    if (event.target === modal) closeModal();
  });

  document.querySelectorAll(".edit-btn").forEach(button => {
    button.addEventListener("click", () => {
      try {
        openModal(JSON.parse(button.dataset.item));
      } catch (error) {
        console.error("Could not open record:", error);
        alert("Could not open this record for editing.");
      }
    });
  });

  document.getElementById("tableSearch")?.addEventListener("input", event => {
    const query = event.target.value.toLowerCase().trim();
    document.querySelectorAll("#contentTable tbody tr[data-search]").forEach(row => {
      row.hidden = !row.dataset.search.includes(query);
    });
  });

  document.addEventListener("keydown", event => {
    if (event.key === "Escape") closeModal();
  });

  form?.addEventListener("submit", event => {
    const action = form.getAttribute("action");
    if (!action || action.includes("[object")) {
      event.preventDefault();
      alert("Invalid form URL. Refresh the page and try again.");
      console.error("Invalid form action:", action);
    }
  });
});


document.addEventListener("pointermove", (event) => { const aura = document.getElementById("cursorAura"); if (aura && window.matchMedia("(pointer:fine)").matches) { aura.style.setProperty("--x", `${event.clientX}px`); aura.style.setProperty("--y", `${event.clientY}px`); } });


// Soft spotlight that follows pointer movement across the content canvas.
document.addEventListener("pointermove", (event) => {
  if (!window.matchMedia("(pointer:fine)").matches) return;
  const main = document.querySelector(".main");
  const aura = document.getElementById("cursorAura");
  if (main) {
    const rect = main.getBoundingClientRect();
    const x = Math.max(0, Math.min(100, ((event.clientX - rect.left) / rect.width) * 100));
    const y = Math.max(0, Math.min(100, ((event.clientY - rect.top) / Math.max(rect.height, 1)) * 100));
    main.style.setProperty("--spot-x", `${x}%`);
    main.style.setProperty("--spot-y", `${y}%`);
  }
  if (aura) aura.style.opacity = "1";
});
document.addEventListener("pointerleave", () => { const aura = document.getElementById("cursorAura"); if (aura) aura.style.opacity = "0"; });
