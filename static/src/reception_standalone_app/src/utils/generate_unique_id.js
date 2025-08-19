// Fonction utilitaire pour générer un ID unique à 3 chiffres
export function generateUniqueId(existingIds = []) {
  let id;
  let attempts = 0;
  do {
    id = Math.floor(100 + Math.random() * 900); // 100–999
    attempts++;
    if (attempts > 1000) throw new Error("Impossible de générer un ID unique.");
  } while (existingIds.includes(id));
  return id;
}
