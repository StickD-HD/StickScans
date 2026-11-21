// Réglages › Catégories.
// Fichier 10/15 : chargé dans l'ordre par index.html ; tous partagent la même portée globale.

const categoryManageList = document.getElementById("category-manage-list");
const newCategoryInput = document.getElementById("new-category-input");
const newCategoryBtn = document.getElementById("new-category-btn");

async function loadCategoryManageList() {
  const res = await fetch("/api/categories");
  const categories = await res.json();
  categoryManageList.innerHTML = "";
  for (const c of categories) {
    const li = document.createElement("li");
    li.className = "category-manage-row";
    li.innerHTML = `
      <input type="text" value="${escapeHtml(c.name)}" data-id="${c.id}">
      <button class="rename-cat-btn" data-id="${c.id}">✓</button>
      <button class="delete-cat-btn" data-id="${c.id}">🗑</button>
    `;
    categoryManageList.appendChild(li);
  }
  categoryManageList.querySelectorAll(".rename-cat-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const input = categoryManageList.querySelector(`input[data-id="${btn.dataset.id}"]`);
      await fetch(`/api/categories/${btn.dataset.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: input.value.trim() }),
      });
      loadCategorySelect();
      if (currentSeriesId) loadSeriesCategories();
    });
  });
  categoryManageList.querySelectorAll(".delete-cat-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (!confirm("Supprimer cette catégorie ?")) return;
      await fetch(`/api/categories/${btn.dataset.id}`, { method: "DELETE" });
      loadCategoryManageList();
      await loadCategorySelect();
      loadLibrary();
    });
  });
}

newCategoryBtn.addEventListener("click", async () => {
  const name = newCategoryInput.value.trim();
  if (!name) return;
  await fetch("/api/categories", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  newCategoryInput.value = "";
  loadCategoryManageList();
  loadCategorySelect();
});
